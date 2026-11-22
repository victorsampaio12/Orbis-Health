"""API JSON do app mobile do socorrista (pasta mobile/, React Native + Expo).

Mesmas regras da versão web: cada rota chama os MESMOS serviços
(ocorrencia_service, chat_service, trajeto_service...) e emite os MESMOS
eventos Socket.IO — o hospital, na web, recebe a emergência criada pelo app
sem saber de onde ela veio.

Autenticação por token (cabeçalho "Authorization: Bearer <token>") em vez do
cookie de sessão: o token é o id do usuário assinado com a SECRET_KEY
(itsdangerous), válido por 7 dias. Só socorristas usam o app.
"""
import json
import math
from functools import wraps

from flask import Blueprint, abort, current_app, g, jsonify, request, send_file
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import db, socketio
from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum
from app.models.usuario import PapelEnum, Usuario
from app.services import (
    anexo_service,
    chat_service,
    demo_service,
    ocorrencia_service,
    rota_service,
    trajeto_service,
)
from app.services.auth_service import AuthError, acesso_revogado, autenticar
from app.services.chat_service import ChatError
from app.services.ocorrencia_service import AcessoNaoAutorizadoError, OcorrenciaError
from app.services.rota_service import RotaError

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

VALIDADE_TOKEN_S = 7 * 24 * 3600
MENSAGEM_SO_SOCORRISTA = "O app OrbisHealth é para socorristas. Hospitais e administradores usam a versão web."


# ------------------------------------------------------------------ token

def _serializador():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="orbis-api-mobile")


def gerar_token(usuario):
    return _serializador().dumps({"uid": usuario.id})


def usuario_do_token(token):
    """Usuário dono do token, ou None (inválido, expirado ou conta revogada)."""
    try:
        dados = _serializador().loads(token, max_age=VALIDADE_TOKEN_S)
    except (BadSignature, SignatureExpired):
        return None
    usuario = db.session.get(Usuario, dados.get("uid"))
    if usuario is None or acesso_revogado(usuario) or usuario.papel != PapelEnum.socorrista:
        return None
    return usuario


def token_obrigatorio(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        cabecalho = request.headers.get("Authorization", "")
        token = cabecalho[7:] if cabecalho.startswith("Bearer ") else None
        usuario = usuario_do_token(token) if token else None
        if usuario is None:
            return jsonify({"erro": "Sessão expirada. Entre novamente."}), 401
        g.usuario = usuario
        return view(*args, **kwargs)

    return wrapper


def _erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status


@api_bp.errorhandler(404)
def _nao_encontrado(_e):
    return _erro("Não encontrado.", 404)


@api_bp.errorhandler(403)
def _proibido(_e):
    return _erro(ocorrencia_service.MENSAGEM_ACESSO_NAO_AUTORIZADO, 403)


@api_bp.errorhandler(413)
def _grande_demais(_e):
    return _erro("Fotos grandes demais: envie no máximo 60 MB por vez (até 10 MB por foto).", 413)


# --------------------------------------------------------- serialização

def _iso(momento):
    """UTC com milissegundos e "Z": o motor JavaScript do celular (Hermes)
    não entende os 6 dígitos de microssegundos do isoformat() padrão."""
    return momento.isoformat(timespec="milliseconds") + "Z" if momento else None


def _codigo(ocorrencia_id):
    return f"EMG-{ocorrencia_id:04d}"


def _paciente_json(paciente, completo=False):
    dados = {
        "id": paciente.id,
        "nome": paciente.nome,
        "idade": paciente.idade,
        "motivo_chamado": paciente.motivo_chamado,
        "prioridade": paciente.prioridade.value,
        "total_fotos": len(paciente.anexos),
        "criado_em": _iso(paciente.criado_em),
    }
    if completo:
        dados.update({
            "cpf": paciente.cpf,
            "documentos_em_maos": paciente.documentos_em_maos,
            "pressao_arterial": paciente.pressao_arterial,
            "frequencia_cardiaca": paciente.frequencia_cardiaca,
            "frequencia_respiratoria": paciente.frequencia_respiratoria,
            "saturacao_o2": paciente.saturacao_o2,
            "temperatura": paciente.temperatura,
            "nivel_consciencia": paciente.nivel_consciencia,
            "glasgow": paciente.glasgow,
            "estavel": paciente.estavel,
            "agravamento_registrado": paciente.agravamento_registrado,
            "melhorando": paciente.melhorando,
            "parada_cardiorrespiratoria": paciente.parada_cardiorrespiratoria,
            "observacao": paciente.observacao,
            "diagnostico": paciente.diagnostico,
            "regioes_lesao": paciente.regioes_lesao_lista,
            "anexos": [
                {
                    "id": a.id,
                    "url": f"/api/v1/ocorrencias/{paciente.ocorrencia_id}/anexos/{a.id}",
                    "miniatura": f"/api/v1/ocorrencias/{paciente.ocorrencia_id}/anexos/{a.id}?miniatura=1",
                    "largura": a.largura,
                    "altura": a.altura,
                }
                for a in paciente.anexos
            ],
        })
    return dados


def _rota_coordenadas(ocorrencia):
    """GeoJSON [lng, lat] -> [{latitude, longitude}] (formato do react-native-maps)."""
    if not ocorrencia.rota_geometria:
        return None
    coords = json.loads(ocorrencia.rota_geometria).get("coordinates", [])
    return [{"latitude": lat, "longitude": lng} for lng, lat in coords]


def _ponto(lat, lng):
    return {"latitude": lat, "longitude": lng} if lat is not None and lng is not None else None


def _ocorrencia_json(ocorrencia):
    hospital = ocorrencia.hospital
    em_transporte = ocorrencia.status == StatusOcorrenciaEnum.em_transporte
    return {
        "id": ocorrencia.id,
        "codigo": _codigo(ocorrencia.id),
        "status": ocorrencia.status.value,
        "veiculo": ocorrencia.veiculo.value,
        "local": ocorrencia.local,
        "comentarios": ocorrencia.comentarios,
        "criado_em": _iso(ocorrencia.criado_em),
        "posicao": _ponto(ocorrencia.latitude_atual, ocorrencia.longitude_atual),
        "destino": _ponto(ocorrencia.destino_latitude, ocorrencia.destino_longitude),
        "hospital": {
            "id": hospital.id,
            "nome": hospital.nome,
            "endereco": hospital.endereco,
        } if hospital else None,
        "rota": _rota_coordenadas(ocorrencia),
        "tipo_rota": ocorrencia.tipo_rota.value if ocorrencia.tipo_rota else None,
        "distancia_km": ocorrencia.distancia_estimada_km,
        "tempo_min": ocorrencia.tempo_estimado_min,
        "distancia_ate_hospital_km": rota_service.distancia_ate_hospital_km(ocorrencia) if hospital else None,
        "raio_chegada_km": rota_service.RAIO_CHEGADA_KM,
        "trajeto_estado": trajeto_service.estado(ocorrencia),
        "progresso": rota_service.progresso_na_rota(ocorrencia) if em_transporte else None,
        "chegada_confirmada_em": _iso(ocorrencia.chegada_confirmada_em),
        "finalizado_em": _iso(ocorrencia.finalizado_em),
        "desfecho": ocorrencia.desfecho,
        "chat_encerrado": ocorrencia.chat_encerrado_em is not None,
        "pode_trocar_hospital": em_transporte and ocorrencia.trajeto_iniciado_em is None
        and ocorrencia.chegada_confirmada_em is None,
        "pacientes": [_paciente_json(p) for p in ocorrencia_service.listar_pacientes_ordenados(ocorrencia)],
    }


def _ocorrencia_do_dono(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    ocorrencia_service.verificar_dono_ocorrencia(ocorrencia, g.usuario)
    return ocorrencia


def _distancia_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def _executar(funcao):
    """Traduz os erros dos serviços para respostas JSON."""
    try:
        return funcao()
    except AcessoNaoAutorizadoError as erro:
        return _erro(erro.message, 403)
    except (OcorrenciaError, RotaError, ChatError) as erro:
        return _erro(erro.message, 400)


# ---------------------------------------------------------------- conta

@api_bp.route("/login", methods=["POST"])
def login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""
    try:
        usuario = autenticar(email, senha)
    except AuthError as erro:
        return _erro(erro.message, 401)
    if usuario.papel != PapelEnum.socorrista:
        return _erro(MENSAGEM_SO_SOCORRISTA, 403)
    return jsonify({"token": gerar_token(usuario), "usuario": _usuario_json(usuario)})


def _usuario_json(usuario):
    socorrista = usuario.socorrista
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "ativo": usuario.ativo,
        "matricula": socorrista.matricula if socorrista else None,
        "telefone": socorrista.telefone if socorrista else None,
    }


@api_bp.route("/eu")
@token_obrigatorio
def eu():
    ativa = ocorrencia_service.obter_ocorrencia_ativa_do_socorrista(g.usuario)
    socorrista = g.usuario.socorrista
    finalizadas = Ocorrencia.query.filter_by(
        socorrista_id=socorrista.id, status=StatusOcorrenciaEnum.finalizada
    ).count() if socorrista else 0
    return jsonify({
        "usuario": _usuario_json(g.usuario),
        "ocorrencia_ativa": _ocorrencia_json(ativa) if ativa else None,
        "atendimentos_finalizados": finalizadas,
        "chat_nao_lidas": chat_service.contar_nao_lidas(g.usuario),
    })


# ------------------------------------------------------------ ocorrência

@api_bp.route("/ocorrencias", methods=["POST"])
@token_obrigatorio
def criar_ocorrencia():
    if ocorrencia_service.obter_ocorrencia_ativa_do_socorrista(g.usuario):
        return _erro("Você já tem uma ocorrência em andamento.", 409)
    dados = request.get_json(silent=True) or {}
    formulario = {k: ("" if v is None else str(v)) for k, v in dados.items()}

    def acao():
        ocorrencia = ocorrencia_service.criar_ocorrencia(formulario, g.usuario)
        return jsonify(_ocorrencia_json(ocorrencia)), 201

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>")
@token_obrigatorio
def ver_ocorrencia(ocorrencia_id):
    def acao():
        ocorrencia = _ocorrencia_do_dono(ocorrencia_id)
        trajeto_service.garantir_em_execucao(ocorrencia)
        return jsonify(_ocorrencia_json(ocorrencia))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/localizacao", methods=["POST"])
@token_obrigatorio
def localizacao(ocorrencia_id):
    dados = request.get_json(silent=True) or {}

    def acao():
        ocorrencia = ocorrencia_service.salvar_localizacao(
            ocorrencia_id, dados.get("lat"), dados.get("lng"), g.usuario
        )
        return jsonify(_ocorrencia_json(ocorrencia))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/hospitais")
@token_obrigatorio
def hospitais(ocorrencia_id):
    def acao():
        ocorrencia = _ocorrencia_do_dono(ocorrencia_id)
        if ocorrencia.status != StatusOcorrenciaEnum.aberta:
            return _erro("Esta ocorrência já tem um hospital de destino selecionado.", 409)
        ordem_status = {"disponivel": 0, "critico": 1, "lotado": 2}
        lista = []
        for hospital, status, ocupados in ocorrencia_service.listar_hospitais_disponiveis(ocorrencia):
            lista.append({
                "id": hospital.id,
                "nome": hospital.nome,
                "endereco": hospital.endereco,
                "status": status,
                "leitos_ocupados": ocupados,
                "leitos_total": hospital.capacidade_maxima,
                "tem_heliponto": hospital.tem_heliponto,
                "posicao": _ponto(hospital.latitude, hospital.longitude),
                "distancia_km": _distancia_km(ocorrencia.latitude_atual, ocorrencia.longitude_atual,
                                              hospital.latitude, hospital.longitude),
            })
        lista.sort(key=lambda h: (ordem_status[h["status"]], h["distancia_km"] if h["distancia_km"] is not None else 1e9))
        return jsonify({"posicao": _ponto(ocorrencia.latitude_atual, ocorrencia.longitude_atual),
                        "veiculo": ocorrencia.veiculo.value, "hospitais": lista})

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/hospital", methods=["POST"])
@token_obrigatorio
def selecionar_hospital(ocorrencia_id):
    dados = request.get_json(silent=True) or {}

    def acao():
        ocorrencia = ocorrencia_service.selecionar_hospital(ocorrencia_id, dados.get("hospital_id"), g.usuario)
        socketio.emit(
            "nova_emergencia",
            {"ocorrencia_id": ocorrencia.id, "mensagem": f"Nova emergência a caminho: {_codigo(ocorrencia.id)}"},
            room=f"hospital_{ocorrencia.hospital_id}",
        )
        # rota já pronta para o mapa (se o OSRM falhar, o app oferece tentar de novo)
        try:
            rota_service.gerar_rota(ocorrencia)
        except RotaError:
            pass
        return jsonify(_ocorrencia_json(ocorrencia))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/trocar-hospital", methods=["POST"])
@token_obrigatorio
def trocar_hospital(ocorrencia_id):
    def acao():
        anterior = ocorrencia_service.desfazer_selecao_hospital(ocorrencia_id, g.usuario)
        aviso = {
            "ocorrencia_id": ocorrencia_id,
            "mensagem": f"A emergência {_codigo(ocorrencia_id)} não vem mais para este hospital "
                        "(o socorrista escolheu outro destino).",
        }
        socketio.emit("emergencia_cancelada", aviso, to=[f"hospital_{anterior}", f"ocorrencia_{ocorrencia_id}"])
        socketio.close_room(f"ocorrencia_{ocorrencia_id}")
        return jsonify(_ocorrencia_json(ocorrencia_service.obter_ocorrencia(ocorrencia_id)))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/rota", methods=["POST"])
@token_obrigatorio
def gerar_rota(ocorrencia_id):
    def acao():
        ocorrencia = _ocorrencia_do_dono(ocorrencia_id)
        ocorrencia_service.verificar_operacao(ocorrencia, g.usuario, *ocorrencia_service.ATIVAS)
        rota_service.gerar_rota(ocorrencia)
        return jsonify(_ocorrencia_json(ocorrencia))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/iniciar-trajeto", methods=["POST"])
@token_obrigatorio
def iniciar_trajeto(ocorrencia_id):
    def acao():
        ocorrencia = trajeto_service.iniciar_trajeto(ocorrencia_id, g.usuario)
        return jsonify(_ocorrencia_json(ocorrencia))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/chegada", methods=["POST"])
@token_obrigatorio
def marcar_chegada(ocorrencia_id):
    def acao():
        ocorrencia = ocorrencia_service.marcar_chegada(ocorrencia_id, g.usuario)
        socketio.emit(
            "socorrista_chegou",
            {"ocorrencia_id": ocorrencia.id, "mensagem": "O socorrista já chegou ao seu destino!"},
            room=f"ocorrencia_{ocorrencia.id}",
        )
        return jsonify(_ocorrencia_json(ocorrencia))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/finalizar", methods=["POST"])
@token_obrigatorio
def finalizar(ocorrencia_id):
    dados = request.get_json(silent=True) or {}

    def acao():
        ocorrencia = ocorrencia_service.finalizar_ocorrencia(ocorrencia_id, dados.get("desfecho"), g.usuario)
        try:
            relatorio = ocorrencia_service.gerar_relatorio(ocorrencia_id, g.usuario)
            relatorio["finalizado_em"] = _iso(relatorio["finalizado_em"])
        except OcorrenciaError:
            relatorio = None
        socketio.emit("ocorrencia_finalizada", {"ocorrencia_id": ocorrencia.id},
                      room=f"ocorrencia_{ocorrencia.id}")
        return jsonify({"ocorrencia": _ocorrencia_json(ocorrencia), "relatorio": relatorio})

    return _executar(acao)


@api_bp.route("/historico")
@token_obrigatorio
def historico():
    socorrista = g.usuario.socorrista
    ocorrencias = (
        Ocorrencia.query.filter_by(socorrista_id=socorrista.id, status=StatusOcorrenciaEnum.finalizada)
        .order_by(Ocorrencia.finalizado_em.desc())
        .limit(50)
        .all()
    )
    return jsonify([
        {
            "id": o.id,
            "codigo": _codigo(o.id),
            "local": o.local,
            "veiculo": o.veiculo.value,
            "hospital": o.hospital.nome if o.hospital else None,
            "criado_em": _iso(o.criado_em),
            "finalizado_em": _iso(o.finalizado_em),
            "desfecho": o.desfecho,
            "pacientes": len(o.pacientes),
            "tempo_atendimento_min": round((o.finalizado_em - o.criado_em).total_seconds() / 60)
            if o.finalizado_em else None,
        }
        for o in ocorrencias
    ])


# -------------------------------------------------------------- pacientes

@api_bp.route("/ocorrencias/<int:ocorrencia_id>/pacientes", methods=["POST"])
@token_obrigatorio
def novo_paciente(ocorrencia_id):
    def acao():
        paciente = ocorrencia_service.adicionar_paciente(
            ocorrencia_id, request.form, g.usuario, arquivos=request.files.getlist("anexos")
        )
        return jsonify(_paciente_json(paciente, completo=True)), 201

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/pacientes/<int:paciente_id>", methods=["GET", "POST"])
@token_obrigatorio
def paciente(ocorrencia_id, paciente_id):
    def acao():
        _ocorrencia_do_dono(ocorrencia_id)
        if request.method == "GET":
            return jsonify(_paciente_json(ocorrencia_service.obter_paciente(ocorrencia_id, paciente_id), completo=True))
        atualizado = ocorrencia_service.atualizar_paciente(
            ocorrencia_id, paciente_id, request.form, g.usuario,
            arquivos=request.files.getlist("anexos"),
            remover_ids=request.form.getlist("remover_anexo"),
        )
        return jsonify(_paciente_json(atualizado, completo=True))

    return _executar(acao)


@api_bp.route("/ocorrencias/<int:ocorrencia_id>/anexos/<int:anexo_id>")
@token_obrigatorio
def anexo(ocorrencia_id, anexo_id):
    from app.models.anexo import AnexoPaciente

    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    try:
        ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, g.usuario)
    except AcessoNaoAutorizadoError:
        abort(403)
    registro = db.session.get(AnexoPaciente, anexo_id)
    if registro is None or registro.paciente.ocorrencia_id != ocorrencia.id:
        abort(404)
    caminho = anexo_service.caminho_absoluto(registro, miniatura=request.args.get("miniatura") == "1")
    try:
        resposta = send_file(caminho, mimetype="image/jpeg")
    except FileNotFoundError:
        abort(404)
    resposta.headers["Cache-Control"] = "private, max-age=3600"
    return resposta


# ------------------------------------------------------------------- chat

@api_bp.route("/ocorrencias/<int:ocorrencia_id>/mensagens", methods=["GET", "POST"])
@token_obrigatorio
def mensagens(ocorrencia_id):
    def acao():
        if request.method == "POST":
            conteudo = (request.get_json(silent=True) or {}).get("conteudo")
            m = chat_service.enviar_mensagem(ocorrencia_id, conteudo if isinstance(conteudo, str) else "", g.usuario)
            payload = {
                "id": m.id,
                "ocorrencia_id": m.ocorrencia_id,
                "remetente_id": m.remetente_id,
                "remetente_nome": m.remetente.nome,
                "conteudo": m.conteudo,
                "enviado_em": _iso(m.enviado_em),
            }
            socketio.emit("mensagem_recebida", payload, room=f"ocorrencia_{ocorrencia_id}")
            demo_service.agendar_resposta_do_hospital(ocorrencia_id, g.usuario)
            return jsonify(payload), 201
        historico_msgs, encerrado = chat_service.listar_mensagens(ocorrencia_id, g.usuario)
        chat_service.marcar_como_lidas(ocorrencia_id, g.usuario)
        return jsonify({
            "chat_encerrado": encerrado,
            "eu": g.usuario.id,
            "mensagens": [
                {
                    "id": m.id,
                    "remetente_id": m.remetente_id,
                    "remetente_nome": m.remetente.nome,
                    "conteudo": m.conteudo,
                    "enviado_em": _iso(m.enviado_em),
                    "lida": m.lida,
                }
                for m in historico_msgs
            ],
        })

    return _executar(acao)
