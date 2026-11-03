"""Trajeto simulado do veículo, rodando no servidor.

Antes a simulação vivia no navegador do socorrista: fechar/recarregar a
página ou trocar de usuário na mesma janela matava o trajeto e o hospital
ficava sem posição nova. Agora o servidor move o veículo por conta própria,
em velocidade constante ao longo do traçado completo da rota, e transmite
cada posição pra sala da ocorrência (mesmo evento do rastreamento real).

A posição é função pura de (trajeto_iniciado_em, trajeto_duracao_s,
geometria), então nada se perde num reinício do servidor: a tarefa é
retomada na próxima vez que alguém abrir a ocorrência (garantir_em_execucao).
Uma tarefa por processo — se o app um dia rodar com vários workers, isto
precisa de um lock compartilhado (ex: Redis) pra não duplicar a simulação.
"""

import bisect
import json
import threading
from datetime import datetime

from flask import current_app

from app import db, socketio
from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum
from app.services import ocorrencia_service, rota_service
from app.services.ocorrencia_service import OcorrenciaError

TICK_SEGUNDOS = 2
# Rota muito curta ainda precisa durar o bastante pra dar pra ver.
DURACAO_MIN_S = 30
DURACAO_PADRAO_S = 40

MENSAGEM_SEM_ROTA = "Gere a rota antes de iniciar o trajeto."
MENSAGEM_TRAJETO_INDISPONIVEL = "O trajeto só pode ser iniciado durante o transporte."

_em_execucao = set()
_lock = threading.Lock()


def _sala(ocorrencia_id):
    return f"ocorrencia_{ocorrencia_id}"


def estado(ocorrencia):
    """'nao_iniciado' | 'em_andamento' | 'concluido'"""
    if ocorrencia.trajeto_iniciado_em is None:
        return "nao_iniciado"
    decorrido = (datetime.utcnow() - ocorrencia.trajeto_iniciado_em).total_seconds()
    if decorrido >= (ocorrencia.trajeto_duracao_s or DURACAO_PADRAO_S):
        return "concluido"
    return "em_andamento"


def _percurso(geometria_json):
    """Geometria GeoJSON -> (coordenadas, distância acumulada em km)."""
    coords = json.loads(geometria_json)["coordinates"]  # [[lng, lat], ...]
    acumulado = [0.0]
    for i in range(1, len(coords)):
        acumulado.append(
            acumulado[-1]
            + rota_service.distancia_km(
                coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0]
            )
        )
    return coords, acumulado


def _posicao_em(coords, acumulado, distancia):
    if distancia >= acumulado[-1]:
        lng, lat = coords[-1]
        return lat, lng
    i = max(1, bisect.bisect_left(acumulado, distancia))
    trecho = acumulado[i] - acumulado[i - 1]
    t = 0 if trecho == 0 else (distancia - acumulado[i - 1]) / trecho
    lng1, lat1 = coords[i - 1]
    lng2, lat2 = coords[i]
    return lat1 + (lat2 - lat1) * t, lng1 + (lng2 - lng1) * t


def iniciar_trajeto(ocorrencia_id, usuario_atual):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    ocorrencia_service.verificar_dono_ocorrencia(ocorrencia, usuario_atual)

    if (
        ocorrencia.status != StatusOcorrenciaEnum.em_transporte
        or ocorrencia.chegada_confirmada_em is not None
    ):
        raise OcorrenciaError(MENSAGEM_TRAJETO_INDISPONIVEL)
    if not ocorrencia.rota_geometria:
        raise OcorrenciaError(MENSAGEM_SEM_ROTA)

    # Idempotente: um segundo clique (ou uma aba duplicada) não reinicia.
    if ocorrencia.trajeto_iniciado_em is None:
        duracao = (
            ocorrencia.tempo_estimado_min * 60
            if ocorrencia.tempo_estimado_min
            else DURACAO_PADRAO_S
        )
        ocorrencia.trajeto_iniciado_em = datetime.utcnow()
        ocorrencia.trajeto_duracao_s = max(DURACAO_MIN_S, duracao)
        db.session.commit()

    garantir_em_execucao(ocorrencia)
    return ocorrencia


def garantir_em_execucao(ocorrencia):
    """Sobe a tarefa de fundo se o trajeto deveria estar rodando e não está
    (ex: servidor reiniciado). Barato o bastante pra chamar a cada page view."""
    if (
        ocorrencia.trajeto_iniciado_em is None
        or ocorrencia.status != StatusOcorrenciaEnum.em_transporte
        or ocorrencia.chegada_confirmada_em is not None
        or not ocorrencia.rota_geometria
    ):
        return

    if estado(ocorrencia) == "concluido":
        # Já chegou ao fim: só precisa de tarefa se a última posição não
        # chegou a ser gravada (servidor caiu no meio).
        coords, _ = _percurso(ocorrencia.rota_geometria)
        lng, lat = coords[-1]
        if (
            ocorrencia.latitude_atual is not None
            and rota_service.distancia_km(
                ocorrencia.latitude_atual, ocorrencia.longitude_atual, lat, lng
            )
            < 0.001
        ):
            return

    with _lock:
        if ocorrencia.id in _em_execucao:
            return
        _em_execucao.add(ocorrencia.id)

    try:
        coords, acumulado = _percurso(ocorrencia.rota_geometria)
        # Já grava a posição de agora, antes da página renderizar: quem abriu
        # a tela depois de um reinício não pode ver a posição velha do banco
        # (o primeiro evento da tarefa sairia antes de o navegador entrar na
        # sala e ninguém o receberia).
        if _passo(ocorrencia.id, coords, acumulado):
            _liberar(ocorrencia.id)
            return
    except Exception:
        _liberar(ocorrencia.id)
        raise

    socketio.start_background_task(
        _executar, current_app._get_current_object(), ocorrencia.id, coords, acumulado
    )


def _liberar(ocorrencia_id):
    with _lock:
        _em_execucao.discard(ocorrencia_id)


def _executar(app, ocorrencia_id, coords, acumulado):
    try:
        with app.app_context():
            while True:
                socketio.sleep(TICK_SEGUNDOS)
                terminou = _passo(ocorrencia_id, coords, acumulado)
                db.session.remove()
                if terminou:
                    break
    finally:
        _liberar(ocorrencia_id)


def _passo(ocorrencia_id, coords, acumulado):
    """Avança uma posição. Retorna True quando a tarefa deve parar."""
    ocorrencia = db.session.get(Ocorrencia, ocorrencia_id)
    if (
        ocorrencia is None
        or ocorrencia.trajeto_iniciado_em is None
        or ocorrencia.status != StatusOcorrenciaEnum.em_transporte
        or ocorrencia.chegada_confirmada_em is not None
    ):
        return True

    decorrido = (datetime.utcnow() - ocorrencia.trajeto_iniciado_em).total_seconds()
    fracao = min(1.0, decorrido / ocorrencia.trajeto_duracao_s)
    lat, lng = _posicao_em(coords, acumulado, fracao * acumulado[-1])

    ocorrencia.latitude_atual = lat
    ocorrencia.longitude_atual = lng
    rota_service.recalcular_eta(ocorrencia)
    db.session.commit()

    socketio.emit(
        "localizacao_atualizada",
        {
            "ocorrencia_id": ocorrencia.id,
            "lat": ocorrencia.latitude_atual,
            "lng": ocorrencia.longitude_atual,
            "distancia_estimada_km": ocorrencia.distancia_estimada_km,
            "tempo_estimado_min": ocorrencia.tempo_estimado_min,
            "progresso": fracao,
        },
        room=_sala(ocorrencia.id),
    )

    if fracao >= 1.0:
        socketio.emit(
            "trajeto_concluido",
            {"ocorrencia_id": ocorrencia.id},
            room=_sala(ocorrencia.id),
        )
        return True
    return False
