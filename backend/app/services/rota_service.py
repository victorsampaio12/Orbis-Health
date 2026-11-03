"""RN-005: decide entre linha reta (helicóptero) e OSRM (ambulância).

Isolado do ocorrencia_service porque tem uma responsabilidade bem
diferente (cálculo geométrico / chamada externa) e um motivo de mudança
próprio (trocar de provedor de rotas não deve mexer em nada relacionado a
paciente/hospital).
"""

import json
import math
from datetime import datetime

from app import db
from app.models.ocorrencia import VeiculoEnum
from app.services import osrm_client

MENSAGEM_SEM_LOCALIZACAO = (
    "É preciso ativar a localização antes de gerar a rota."
)
MENSAGEM_SEM_HOSPITAL = "Selecione o hospital de destino antes de gerar a rota."
MENSAGEM_OSRM_FALHOU = (
    "Não foi possível calcular a rota terrestre agora. Tente novamente em instantes."
)

RAIO_TERRA_KM = 6371
# Não temos dado real de velocidade de cruzeiro do helicóptero em lugar
# nenhum do sistema; assumido como constante só para estimar um tempo
# plausível. Fácil de ajustar depois se surgir um valor oficial.
VELOCIDADE_HELICOPTERO_KMH = 220
# HU-022: usada só pra recalcular o ETA em tempo real a cada posição nova
# (não pra gerar a rota em si, isso continua vindo do OSRM). Chamar o OSRM
# a cada atualização de posição — que chega a cada 2s por ambulância —
# estouraria a política de uso justo do servidor público na hora.
VELOCIDADE_AMBULANCIA_KMH_MEDIA = 40

# Raio de tolerância pra liberar "Notificar chegada" (HU-021): dá margem
# pro erro de GPS em área urbana e pro fato de que "chegar" pode significar
# entrar no pátio do hospital, não acertar o pino exato do geocoding.
RAIO_CHEGADA_KM = 0.2


class RotaError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def distancia_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return RAIO_TERRA_KM * 2 * math.asin(math.sqrt(a))


def gerar_rota(ocorrencia):
    if ocorrencia.latitude_atual is None or ocorrencia.longitude_atual is None:
        raise RotaError(MENSAGEM_SEM_LOCALIZACAO)

    if ocorrencia.hospital_id is None or ocorrencia.hospital is None:
        raise RotaError(MENSAGEM_SEM_HOSPITAL)

    # Usa a posição travada na seleção (ver comentário no model), não
    # ocorrencia.hospital.latitude/longitude ao vivo — o hospital pode ter
    # sido editado depois que virou o destino desta ocorrência.
    destino_lat = ocorrencia.destino_latitude
    destino_lng = ocorrencia.destino_longitude
    if destino_lat is None or destino_lng is None:
        raise RotaError(
            "O hospital de destino não tem localização no mapa cadastrada."
        )

    if ocorrencia.veiculo == VeiculoEnum.helicoptero:
        distancia = distancia_km(
            ocorrencia.latitude_atual,
            ocorrencia.longitude_atual,
            destino_lat,
            destino_lng,
        )
        tempo_min = (distancia / VELOCIDADE_HELICOPTERO_KMH) * 60
        geometria = {
            "type": "LineString",
            "coordinates": [
                [ocorrencia.longitude_atual, ocorrencia.latitude_atual],
                [destino_lng, destino_lat],
            ],
        }
    else:
        resultado = osrm_client.obter_rota_terrestre(
            ocorrencia.latitude_atual,
            ocorrencia.longitude_atual,
            destino_lat,
            destino_lng,
        )
        if resultado is None:
            raise RotaError(MENSAGEM_OSRM_FALHOU)

        distancia = resultado["distancia_km"]
        tempo_min = resultado["tempo_min"]
        geometria = resultado["geometria_geojson"]

    ocorrencia.distancia_estimada_km = round(distancia, 2)
    ocorrencia.tempo_estimado_min = round(tempo_min, 1)
    ocorrencia.rota_geometria = json.dumps(geometria)
    ocorrencia.rota_gerada_em = datetime.utcnow()
    db.session.commit()
    return ocorrencia


def recalcular_eta(ocorrencia):
    """HU-022: recalcula distância/tempo restante a partir da posição atual,
    sem tocar em rota_geometria (o traçado desenhado no mapa continua o
    mesmo — só o número do ETA muda). Não commita; quem chama decide
    quando persistir."""
    if (
        ocorrencia.latitude_atual is None
        or ocorrencia.longitude_atual is None
        or ocorrencia.destino_latitude is None
        or ocorrencia.destino_longitude is None
    ):
        return

    distancia = distancia_km(
        ocorrencia.latitude_atual,
        ocorrencia.longitude_atual,
        ocorrencia.destino_latitude,
        ocorrencia.destino_longitude,
    )
    velocidade = (
        VELOCIDADE_HELICOPTERO_KMH
        if ocorrencia.veiculo == VeiculoEnum.helicoptero
        else VELOCIDADE_AMBULANCIA_KMH_MEDIA
    )

    ocorrencia.distancia_estimada_km = round(distancia, 2)
    ocorrencia.tempo_estimado_min = round((distancia / velocidade) * 60, 1)


def distancia_ate_hospital_km(ocorrencia):
    """HU-021: distância atual do socorrista até o hospital de destino."""
    if (
        ocorrencia.latitude_atual is None
        or ocorrencia.longitude_atual is None
        or ocorrencia.destino_latitude is None
        or ocorrencia.destino_longitude is None
    ):
        return None

    return distancia_km(
        ocorrencia.latitude_atual,
        ocorrencia.longitude_atual,
        ocorrencia.destino_latitude,
        ocorrencia.destino_longitude,
    )


def progresso_na_rota(ocorrencia):
    """Fração (0..1) do traçado da rota já percorrida, projetando a posição
    atual sobre a geometria. Vale tanto pra GPS real quanto pra simulação
    (que anda exatamente sobre o traçado). 0 se ainda não há rota/posição."""
    if (
        not ocorrencia.rota_geometria
        or ocorrencia.latitude_atual is None
        or ocorrencia.longitude_atual is None
    ):
        return 0.0

    coords = json.loads(ocorrencia.rota_geometria)["coordinates"]  # [[lng, lat], ...]
    if len(coords) < 2:
        return 0.0

    acumulado = [0.0]
    for i in range(1, len(coords)):
        acumulado.append(
            acumulado[-1]
            + distancia_km(coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0])
        )
    total = acumulado[-1]
    if total == 0:
        return 0.0

    # Projeção plana local (suficiente pra escolher o trecho mais próximo).
    fator = math.cos(math.radians(ocorrencia.latitude_atual))
    px, py = ocorrencia.longitude_atual * fator, ocorrencia.latitude_atual
    melhor_d2, melhor_dist = None, 0.0
    for i in range(1, len(coords)):
        ax, ay = coords[i - 1][0] * fator, coords[i - 1][1]
        bx, by = coords[i][0] * fator, coords[i][1]
        dx, dy = bx - ax, by - ay
        comprimento2 = dx * dx + dy * dy
        t = 0.0 if comprimento2 == 0 else max(
            0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / comprimento2)
        )
        d2 = (px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2
        if melhor_d2 is None or d2 < melhor_d2:
            melhor_d2 = d2
            melhor_dist = acumulado[i - 1] + t * (acumulado[i] - acumulado[i - 1])
    return max(0.0, min(1.0, melhor_dist / total))
