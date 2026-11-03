"""HU-022/HU-023: eventos de rastreamento em tempo real.

Cada ocorrência tem sua própria "sala" (room) no Socket.IO, nomeada
f"ocorrencia_{id}". Só o socorrista dono ou o hospital destino podem
entrar nela — a mesma regra de acesso da RN-007, verificada de novo aqui
porque WebSocket é uma porta de entrada separada do HTTP.
"""

from flask_login import current_user
from flask_socketio import emit, join_room

from app import socketio
from app.services import chat_service, ocorrencia_service, rota_service
from app.services.chat_service import ChatError
from app.services.ocorrencia_service import AcessoNaoAutorizadoError


def _sala(ocorrencia_id):
    return f"ocorrencia_{ocorrencia_id}"


def sala_hospital(hospital_id):
    """Sala do hospital inteiro (não de uma ocorrência): avisa a lista de
    emergência quando uma nova ocorrência passa a ter este hospital de destino."""
    return f"hospital_{hospital_id}"


@socketio.on("entrar_sala_hospital")
def ao_entrar_sala_hospital(dados):
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
    ocorrencia_id = dados.get("ocorrencia_id")
    if not current_user.is_authenticated or not ocorrencia_id:
        return

    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
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
    ocorrencia_id = dados.get("ocorrencia_id")
    lat = dados.get("lat")
    lng = dados.get("lng")

    if not current_user.is_authenticated or not ocorrencia_id or lat is None or lng is None:
        return

    try:
        ocorrencia = ocorrencia_service.salvar_localizacao(
            ocorrencia_id, lat, lng, current_user
        )
    except AcessoNaoAutorizadoError:
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
    ocorrencia_id = dados.get("ocorrencia_id")
    conteudo = dados.get("conteudo")

    if not current_user.is_authenticated or not ocorrencia_id:
        return

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
