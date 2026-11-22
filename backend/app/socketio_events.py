"""HU-022/HU-023: eventos de rastreamento em tempo real.

Cada ocorrência tem sua própria "sala" (room) no Socket.IO, nomeada
f"ocorrencia_{id}". Só o socorrista dono ou o hospital destino podem
entrar nela — a mesma regra de acesso da RN-007, verificada de novo aqui
porque WebSocket é uma porta de entrada separada do HTTP.
"""

from flask_login import current_user, login_user
from flask_socketio import emit, join_room

from app import db, socketio
from app.models.ocorrencia import Ocorrencia
from app.services import chat_service, demo_service, ocorrencia_service, rota_service
from app.services.chat_service import ChatError
from app.services.ocorrencia_service import AcessoNaoAutorizadoError, OcorrenciaError


def _sala(ocorrencia_id):
    return f"ocorrencia_{ocorrencia_id}"


def sala_hospital(hospital_id):
    """Sala do hospital inteiro (não de uma ocorrência): avisa a lista de
    emergência quando uma nova ocorrência passa a ter este hospital de destino."""
    return f"hospital_{hospital_id}"


def _dados_validos(dados):
    """Eventos vêm direto do cliente: só aceita um objeto JSON."""
    return dados if isinstance(dados, dict) else {}


def _ocorrencia_ou_none(ocorrencia_id):
    """Como obter_ocorrencia, mas sem abort(404) — num evento de WebSocket não
    há página de erro; id inexistente ou malformado só é ignorado."""
    if not isinstance(ocorrencia_id, int) or isinstance(ocorrencia_id, bool):
        try:
            ocorrencia_id = int(ocorrencia_id)
        except (TypeError, ValueError):
            return None
    if not 0 < ocorrencia_id < 2**31:
        return None
    return db.session.get(Ocorrencia, ocorrencia_id)


@socketio.on("connect")
def ao_conectar(auth=None):
    """O navegador entra com o cookie de sessão. O app mobile não tem cookie:
    manda o token da API em `auth` e a conexão passa a valer como aquele
    socorrista (as mesmas checagens de sala e de chat abaixo continuam)."""
    if current_user.is_authenticated or not isinstance(auth, dict) or not auth.get("token"):
        return
    from app.controllers.api_controller import usuario_do_token

    usuario = usuario_do_token(str(auth["token"]))
    if usuario is not None:
        login_user(usuario)


@socketio.on("entrar_sala_hospital")
def ao_entrar_sala_hospital(dados):
    dados = _dados_validos(dados)
    hospital = getattr(current_user, "hospital", None)
    if (
        not current_user.is_authenticated
        or hospital is None
        or dados.get("hospital_id") != hospital.id
    ):
        return
    join_room(sala_hospital(hospital.id))


@socketio.on("entrar_sala_ocorrencia")
def ao_entrar_sala(dados):
    ocorrencia_id = _dados_validos(dados).get("ocorrencia_id")
    if not current_user.is_authenticated or not ocorrencia_id:
        return

    ocorrencia = _ocorrencia_ou_none(ocorrencia_id)
    if ocorrencia is None:
        return
    ocorrencia_id = ocorrencia.id
    try:
        ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError:
        return

    join_room(_sala(ocorrencia_id))


@socketio.on("atualizar_localizacao")
def ao_atualizar_localizacao(dados):
    """HU-022: recebe a posição do socorrista, salva, recalcula o tempo
    estimado (haversine, sem chamar OSRM a cada evento — ver rota_service)
    e retransmite pra sala (o hospital ouvindo essa ocorrência)."""
    dados = _dados_validos(dados)
    ocorrencia_id = dados.get("ocorrencia_id")
    lat = dados.get("lat")
    lng = dados.get("lng")

    if not current_user.is_authenticated or lat is None or lng is None:
        return
    if _ocorrencia_ou_none(ocorrencia_id) is None:
        return
    ocorrencia_id = int(ocorrencia_id)

    try:
        ocorrencia = ocorrencia_service.salvar_localizacao(
            ocorrencia_id, lat, lng, current_user
        )
    except (AcessoNaoAutorizadoError, OcorrenciaError):
        return

    emit(
        "localizacao_atualizada",
        {
            "ocorrencia_id": ocorrencia.id,
            "lat": ocorrencia.latitude_atual,
            "lng": ocorrencia.longitude_atual,
            "distancia_estimada_km": ocorrencia.distancia_estimada_km,
            "tempo_estimado_min": ocorrencia.tempo_estimado_min,
            "progresso": rota_service.progresso_na_rota(ocorrencia),
        },
        room=_sala(ocorrencia_id),
    )


@socketio.on("enviar_mensagem")
def ao_enviar_mensagem(dados):
    """HU-018/HU-019: RN-016 é reforçada dentro de chat_service (mesma
    checagem de acesso do rastreamento — admin nunca passa) e RN-022
    (chat encerrado) também é validada lá, não só escondida no frontend."""
    dados = _dados_validos(dados)
    ocorrencia_id = dados.get("ocorrencia_id")
    conteudo = dados.get("conteudo")

    if not current_user.is_authenticated or _ocorrencia_ou_none(ocorrencia_id) is None:
        return
    ocorrencia_id = int(ocorrencia_id)
    if not isinstance(conteudo, str):
        conteudo = ""

    try:
        mensagem = chat_service.enviar_mensagem(ocorrencia_id, conteudo, current_user)
    except (AcessoNaoAutorizadoError, ChatError) as erro:
        emit("erro_mensagem", {"erro": erro.message})
        return

    emit(
        "mensagem_recebida",
        {
            "id": mensagem.id,
            "ocorrencia_id": mensagem.ocorrencia_id,
            "remetente_id": mensagem.remetente_id,
            "remetente_nome": mensagem.remetente.nome,
            "conteudo": mensagem.conteudo,
            "enviado_em": mensagem.enviado_em.isoformat(),
        },
        room=_sala(ocorrencia_id),
    )
    demo_service.agendar_resposta_do_hospital(ocorrencia_id, current_user)
