import json

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app import socketio
from app.controllers.decorators import socorrista_required
from app.models.ocorrencia import StatusOcorrenciaEnum
from app.services import (
    anexo_service,
    chat_service,
    nominatim_client,
    ocorrencia_service,
    rota_service,
    trajeto_service,
)
from app.services.ocorrencia_service import AcessoNaoAutorizadoError, OcorrenciaError
from app.services.rota_service import RotaError

ocorrencia_bp = Blueprint("ocorrencia", __name__, url_prefix="/ocorrencias")


@ocorrencia_bp.route("/novo", methods=["GET", "POST"])
@login_required
@socorrista_required
def nova():
    ativa = ocorrencia_service.obter_ocorrencia_ativa_do_socorrista(current_user)
    if ativa:
        if request.method == "POST":
            # O formulário pode ter sido aberto antes de outra ocorrência
            # surgir (ex.: criada pelo app). Sem este aviso, o socorrista
            # escolhia helicóptero e "caía" na ocorrência de ambulância.
            veiculo = "Ambulância" if ativa.veiculo.value == "ambulancia" else "Helicóptero"
            flash(
                f"Você já tem uma ocorrência em andamento (EMG-{ativa.id:04d}, {veiculo}). "
                "Finalize-a antes de abrir outra.",
                "error",
            )
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ativa.id))

    if request.method == "POST":
        try:
            ocorrencia = ocorrencia_service.criar_ocorrencia(request.form, current_user)
        except OcorrenciaError as erro:
            flash(erro.message, "error")
            return render_template("ocorrencias/form.html", dados=request.form)

        flash("Ocorrência Salva com Sucesso!", "success")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia.id))

    return render_template("ocorrencias/form.html", dados={})


@ocorrencia_bp.route("/<int:ocorrencia_id>")
@login_required
def ver(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))

    # Retoma o trajeto simulado se o servidor foi reiniciado no meio dele.
    trajeto_service.garantir_em_execucao(ocorrencia)

    pacientes = ocorrencia_service.listar_pacientes_ordenados(ocorrencia)
    eh_dono = (
        current_user.papel.value == "socorrista"
        and current_user.socorrista is not None
        and ocorrencia.socorrista_id == current_user.socorrista.id
    )

    mapa_dados = {
        "posicao_socorrista": (
            [ocorrencia.latitude_atual, ocorrencia.longitude_atual]
            if ocorrencia.latitude_atual is not None
            else None
        ),
        # Posição travada na seleção do hospital (ver comentário no model
        # Ocorrencia), não a posição ao vivo do cadastro — o pino de destino
        # não pode "pular" no mapa se o endereço do hospital for editado
        # depois que o transporte já começou.
        "destino": (
            [ocorrencia.destino_latitude, ocorrencia.destino_longitude]
            if ocorrencia.destino_latitude is not None
            else None
        ),
        "rota_geometria": (
            json.loads(ocorrencia.rota_geometria) if ocorrencia.rota_geometria else None
        ),
        "veiculo": ocorrencia.veiculo.value,
        "raio_chegada_km": rota_service.RAIO_CHEGADA_KM,
        "distancia_atual_km": ocorrencia.distancia_estimada_km,
        "tempo_estimado_min": ocorrencia.tempo_estimado_min,
        "trajeto_estado": trajeto_service.estado(ocorrencia),
        # fração já percorrida da rota (barra de progresso do painel ao vivo)
        "progresso": (
            1.0 if ocorrencia.chegada_confirmada_em or ocorrencia.status.value == "finalizada"
            else rota_service.progresso_na_rota(ocorrencia)
        ),
    }

    return render_template(
        "ocorrencias/detalhe.html",
        progresso=mapa_dados["progresso"],
        ocorrencia=ocorrencia,
        trajeto_estado=mapa_dados["trajeto_estado"],
        pacientes=pacientes,
        eh_dono=eh_dono,
        mapa_dados_json=json.dumps(mapa_dados).replace("<", "\\u003c"),  # dentro de <script>: "</script>" num nome não fecha a tag
    )


@ocorrencia_bp.route("/<int:ocorrencia_id>/prontuario")
@login_required
def prontuario(ocorrencia_id):
    """Pré-prontuário completo, só leitura — pro hospital destino acompanhar
    o quadro de cada paciente (o socorrista dono edita em /pacientes)."""
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))

    return render_template(
        "ocorrencias/prontuario.html",
        ocorrencia=ocorrencia,
        pacientes=ocorrencia_service.listar_pacientes_ordenados(ocorrencia),
    )


@ocorrencia_bp.route("/<int:ocorrencia_id>/anexos/<int:anexo_id>")
@login_required
def anexo(ocorrencia_id, anexo_id):
    """Foto do prontuário. Mesma regra de leitura da ocorrência (RN-007):
    só o socorrista dono e o hospital de destino. ?miniatura=1 devolve a
    versão reduzida usada na galeria."""
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    try:
        ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError:
        abort(403)

    registro = next(
        (a for p in ocorrencia.pacientes for a in p.anexos if a.id == anexo_id), None
    )
    if registro is None:
        abort(404)

    resposta = send_file(
        anexo_service.caminho_absoluto(registro, miniatura=request.args.get("miniatura") == "1"),
        mimetype="image/jpeg",
        download_name=registro.nome_original if request.args.get("baixar") == "1" else None,
        as_attachment=request.args.get("baixar") == "1",
        conditional=True,
        max_age=0,
    )
    # dado de saúde: nada de cache compartilhado (proxy etc.)
    resposta.headers["Cache-Control"] = "private, no-store"
    return resposta


@ocorrencia_bp.route("/<int:ocorrencia_id>/pacientes")
@login_required
@socorrista_required
def pacientes(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_dono_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))

    pacientes = ocorrencia_service.listar_pacientes_ordenados(ocorrencia)
    return render_template(
        "ocorrencias/pacientes.html", ocorrencia=ocorrencia, pacientes=pacientes
    )


@ocorrencia_bp.route("/<int:ocorrencia_id>/pacientes/novo", methods=["GET", "POST"])
@login_required
@socorrista_required
def novo_paciente(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_dono_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        try:
            ocorrencia_service.adicionar_paciente(
                ocorrencia_id, request.form, current_user, arquivos=request.files.getlist("anexos")
            )
        except AcessoNaoAutorizadoError as erro:
            flash(erro.message, "error")
            return redirect(url_for("auth.dashboard"))
        except OcorrenciaError as erro:
            flash(erro.message, "error")
            return render_template(
                "ocorrencias/paciente_form.html", ocorrencia=ocorrencia, dados=request.form
            )

        flash("Prontuário Salvo com Sucesso!", "success")
        return redirect(url_for("ocorrencia.pacientes", ocorrencia_id=ocorrencia_id))

    return render_template(
        "ocorrencias/paciente_form.html", ocorrencia=ocorrencia, dados={}
    )


@ocorrencia_bp.route(
    "/<int:ocorrencia_id>/pacientes/<int:paciente_id>/editar", methods=["GET", "POST"]
)
@login_required
@socorrista_required
def editar_paciente(ocorrencia_id, paciente_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    paciente = ocorrencia_service.obter_paciente(ocorrencia_id, paciente_id)

    try:
        ocorrencia_service.verificar_dono_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        try:
            ocorrencia_service.atualizar_paciente(
                ocorrencia_id, paciente_id, request.form, current_user,
                arquivos=request.files.getlist("anexos"),
                remover_ids=request.form.getlist("remover_anexo"),
            )
        except AcessoNaoAutorizadoError as erro:
            flash(erro.message, "error")
            return redirect(url_for("auth.dashboard"))
        except OcorrenciaError as erro:
            flash(erro.message, "error")
            return render_template(
                "ocorrencias/paciente_form.html",
                ocorrencia=ocorrencia,
                dados=request.form,
                paciente=paciente,
            )

        flash("Prontuário Atualizado com Sucesso!", "success")
        return redirect(url_for("ocorrencia.pacientes", ocorrencia_id=ocorrencia_id))

    dados = {
        "nome": paciente.nome,
        "cpf": paciente.cpf,
        "idade": paciente.idade,
        "documentos_em_maos": "sim" if paciente.documentos_em_maos else (
            "nao" if paciente.documentos_em_maos is False else ""
        ),
        "motivo_chamado": paciente.motivo_chamado,
        "pressao_arterial": paciente.pressao_arterial,
        "frequencia_cardiaca": paciente.frequencia_cardiaca,
        "frequencia_respiratoria": paciente.frequencia_respiratoria,
        "saturacao_o2": paciente.saturacao_o2,
        "temperatura": paciente.temperatura,
        "nivel_consciencia": paciente.nivel_consciencia,
        "glasgow": paciente.glasgow,
        "estavel": "on" if paciente.estavel else "",
        "agravamento_registrado": "on" if paciente.agravamento_registrado else "",
        "melhorando": "on" if paciente.melhorando else "",
        "parada_cardiorrespiratoria": "on" if paciente.parada_cardiorrespiratoria else "",
        "observacao": paciente.observacao,
        "diagnostico": paciente.diagnostico,
        "regioes_lesao": paciente.regioes_lesao,
    }
    # campos opcionais ficam None quando nunca preenchidos — sem isso, o
    # template renderiza o texto literal "None" no value="" do input.
    dados = {chave: ("" if valor is None else valor) for chave, valor in dados.items()}
    return render_template(
        "ocorrencias/paciente_form.html",
        ocorrencia=ocorrencia,
        dados=dados,
        paciente=paciente,
    )


@ocorrencia_bp.route("/<int:ocorrencia_id>/hospitais")
@login_required
@socorrista_required
def hospitais(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_dono_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))

    if ocorrencia.status != StatusOcorrenciaEnum.aberta:
        flash("Esta ocorrência já tem um hospital de destino selecionado.", "error")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    lista = ocorrencia_service.listar_hospitais_disponiveis(ocorrencia)

    mapa_dados = {
        "posicao_socorrista": (
            [ocorrencia.latitude_atual, ocorrencia.longitude_atual]
            if ocorrencia.latitude_atual is not None
            else None
        ),
        "hospitais": [
            {
                "id": hospital.id,
                "nome": hospital.nome,
                "status": status,
                "leitos_ocupados": ocupados,
                "leitos_total": hospital.capacidade_maxima,
                "posicao": [hospital.latitude, hospital.longitude]
                if hospital.latitude is not None
                else None,
            }
            for hospital, status, ocupados in lista
        ],
    }

    return render_template(
        "ocorrencias/hospitais.html",
        ocorrencia=ocorrencia,
        hospitais=lista,
        mapa_dados_json=json.dumps(mapa_dados).replace("<", "\\u003c"),  # dentro de <script>: "</script>" num nome não fecha a tag
    )


@ocorrencia_bp.route("/<int:ocorrencia_id>/selecionar-hospital", methods=["POST"])
@login_required
@socorrista_required
def selecionar_hospital(ocorrencia_id):
    hospital_id = request.form.get("hospital_id")

    try:
        ocorrencia_service.selecionar_hospital(ocorrencia_id, hospital_id, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))
    except OcorrenciaError as erro:
        flash(erro.message, "error")
        return redirect(url_for("ocorrencia.hospitais", ocorrencia_id=ocorrencia_id))

    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    socketio.emit(
        "nova_emergencia",
        {
            "ocorrencia_id": ocorrencia.id,
            "mensagem": f"Nova emergência a caminho: EMG-{ocorrencia.id:04d}",
        },
        room=f"hospital_{ocorrencia.hospital_id}",
    )

    flash("Hospital de destino confirmado!", "success")
    return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))


@ocorrencia_bp.route("/<int:ocorrencia_id>/trocar-hospital", methods=["POST"])
@login_required
@socorrista_required
def trocar_hospital(ocorrencia_id):
    """Botão "Voltar" da ocorrência: desfaz a escolha do hospital (enquanto o
    trajeto não começou) e volta para a lista de hospitais."""
    try:
        hospital_anterior_id = ocorrencia_service.desfazer_selecao_hospital(ocorrencia_id, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))
    except OcorrenciaError as erro:
        flash(erro.message, "error")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    aviso = {
        "ocorrencia_id": ocorrencia_id,
        "mensagem": f"A emergência EMG-{ocorrencia_id:04d} não vem mais para este hospital "
                    "(o socorrista escolheu outro destino).",
    }
    # numa emissão só: quem está nas duas salas (o painel do hospital) recebe uma vez
    socketio.emit(
        "emergencia_cancelada", aviso,
        to=[f"hospital_{hospital_anterior_id}", f"ocorrencia_{ocorrencia_id}"],
    )
    # Esvazia a sala da ocorrência: o hospital abandonado não pode continuar
    # recebendo a posição da viatura nem o chat com o novo destino (RN-007 /
    # RN-016). Quem tem acesso entra de novo ao carregar a página.
    socketio.close_room(f"ocorrencia_{ocorrencia_id}")

    flash("Seleção desfeita. Escolha outro hospital de destino.", "success")
    return redirect(url_for("ocorrencia.hospitais", ocorrencia_id=ocorrencia_id))


@ocorrencia_bp.route("/geocodificar-reverso")
@login_required
@socorrista_required
def geocodificar_reverso():
    """Usado por fetch() na tela de criar ocorrência pra preencher o campo
    Local a partir da localização capturada pelo navegador."""
    try:
        lat = float(request.args.get("lat", ""))
        lng = float(request.args.get("lng", ""))
    except ValueError:
        return jsonify({"endereco": None}), 400

    endereco = nominatim_client.geocodificar_reverso(lat, lng)
    return jsonify({"endereco": endereco})


@ocorrencia_bp.route("/<int:ocorrencia_id>/localizacao", methods=["POST"])
@login_required
@socorrista_required
def salvar_localizacao(ocorrencia_id):
    """Usado por fetch() na tela de detalhe quando a localização não foi
    capturada na criação (ex: permissão negada na hora, concedida depois)."""
    dados = request.get_json(silent=True) or {}
    try:
        lat = float(dados.get("lat"))
        lng = float(dados.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Coordenadas inválidas."}), 400

    try:
        ocorrencia_service.salvar_localizacao(ocorrencia_id, lat, lng, current_user)
    except AcessoNaoAutorizadoError:
        return jsonify({"ok": False, "erro": ocorrencia_service.MENSAGEM_ACESSO_NAO_AUTORIZADO}), 403
    except OcorrenciaError as erro:
        return jsonify({"ok": False, "erro": erro.message}), 400

    return jsonify({"ok": True})


@ocorrencia_bp.route("/<int:ocorrencia_id>/gerar-rota", methods=["POST"])
@login_required
@socorrista_required
def gerar_rota(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_operacao(ocorrencia, current_user, *ocorrencia_service.ATIVAS)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))
    except OcorrenciaError as erro:
        flash(erro.message, "error")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    try:
        rota_service.gerar_rota(ocorrencia)
    except RotaError as erro:
        flash(erro.message, "error")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    flash("Rota gerada com sucesso!", "success")
    return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))


@ocorrencia_bp.route("/<int:ocorrencia_id>/iniciar-trajeto", methods=["POST"])
@login_required
@socorrista_required
def iniciar_trajeto(ocorrencia_id):
    try:
        trajeto_service.iniciar_trajeto(ocorrencia_id, current_user)
    except AcessoNaoAutorizadoError as erro:
        return jsonify({"ok": False, "erro": erro.message}), 403
    except OcorrenciaError as erro:
        return jsonify({"ok": False, "erro": erro.message}), 400

    return jsonify({"ok": True})


@ocorrencia_bp.route("/<int:ocorrencia_id>/marcar-chegada", methods=["POST"])
@login_required
@socorrista_required
def marcar_chegada(ocorrencia_id):
    try:
        ocorrencia = ocorrencia_service.marcar_chegada(ocorrencia_id, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))
    except OcorrenciaError as erro:
        flash(erro.message, "error")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    # HU-021: notifica o hospital em tempo real.
    socketio.emit(
        "socorrista_chegou",
        {
            "ocorrencia_id": ocorrencia.id,
            "mensagem": "O socorrista já chegou ao seu destino!",
        },
        room=f"ocorrencia_{ocorrencia.id}",
    )

    flash("Chegada notificada com sucesso!", "success")
    return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))


@ocorrencia_bp.route("/<int:ocorrencia_id>/finalizar", methods=["POST"])
@login_required
@socorrista_required
def finalizar(ocorrencia_id):
    desfecho = request.form.get("desfecho", "")

    try:
        ocorrencia = ocorrencia_service.finalizar_ocorrencia(
            ocorrencia_id, desfecho, current_user
        )
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))
    except OcorrenciaError as erro:
        flash(erro.message, "error")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    # RN-023: a finalização já está garantida nesse ponto — uma falha aqui
    # não desfaz nada, só avisa que o relatório precisa ser gerado de novo.
    try:
        ocorrencia_service.gerar_relatorio(ocorrencia_id, current_user)
    except OcorrenciaError:
        flash("Erro ao gerar relatório — tente novamente", "warning")

    socketio.emit(
        "ocorrencia_finalizada",
        {"ocorrencia_id": ocorrencia.id},
        room=f"ocorrencia_{ocorrencia.id}",
    )

    flash("Ocorrência finalizada com sucesso!", "success")
    return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))


@ocorrencia_bp.route("/<int:ocorrencia_id>/relatorio")
@login_required
def relatorio(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("auth.dashboard"))

    try:
        dados_relatorio = ocorrencia_service.gerar_relatorio(ocorrencia_id, current_user)
    except OcorrenciaError as erro:
        flash(erro.message, "error")
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    return render_template(
        "ocorrencias/relatorio.html", ocorrencia=ocorrencia, relatorio=dados_relatorio
    )


@ocorrencia_bp.route("/<int:ocorrencia_id>/mensagens")
@login_required
def mensagens(ocorrencia_id):
    """HU-019. RN-016 é validada dentro de chat_service — admin nunca
    passa (não é dono nem hospital destino), então cai no 403 abaixo."""
    try:
        historico, chat_encerrado = chat_service.listar_mensagens(ocorrencia_id, current_user)
    except AcessoNaoAutorizadoError:
        return jsonify({"erro": ocorrencia_service.MENSAGEM_ACESSO_NAO_AUTORIZADO}), 403
    except Exception:
        return jsonify(
            {"erro": "Falha ao visualizar histórico de conversas, tente novamente mais tarde"}
        ), 500

    return jsonify(
        {
            "chat_encerrado": chat_encerrado,
            "mensagens": [
                {
                    "id": m.id,
                    "remetente_id": m.remetente_id,
                    "remetente_nome": m.remetente.nome,
                    "conteudo": m.conteudo,
                    "enviado_em": m.enviado_em.isoformat(),
                    "lida": m.lida,
                }
                for m in historico
            ],
        }
    )
