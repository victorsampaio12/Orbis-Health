"""Cliente isolado para o OSRM (roteamento terrestre OpenStreetMap).

Servidor público por padrão (OSRM_BASE_URL), sem chave de API, sem SLA —
por isso o timeout curto e o User-Agent identificável. Qualquer erro de
rede, timeout, ou resposta sem rota retorna None; quem chama decide a
mensagem de erro (RN: bloquear e permitir tentar de novo).
"""

import json
import urllib.error
import urllib.request

from flask import current_app

TIMEOUT_SEGUNDOS = 8


def obter_rota_terrestre(lat_origem, lng_origem, lat_destino, lng_destino):
    """Rota terrestre entre dois pontos via OSRM.

    Retorna um dict {distancia_km, tempo_min, geometria_geojson} ou None se
    o OSRM não encontrar rota, der erro, ou timeout.
    """
    base_url = current_app.config["OSRM_BASE_URL"]
    coordenadas = f"{lng_origem},{lat_origem};{lng_destino},{lat_destino}"
    url = f"{base_url}/route/v1/driving/{coordenadas}?overview=full&geometries=geojson"

    request = urllib.request.Request(
        url, headers={"User-Agent": current_app.config["MAPS_USER_AGENT"]}
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEGUNDOS) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    # OSRM pode responder 200 com code != "Ok" (ex: "NoRoute", "NoSegment")
    # quando não existe via mapeada entre os pontos.
    if dados.get("code") != "Ok" or not dados.get("routes"):
        return None

    rota = dados["routes"][0]
    return {
        "distancia_km": rota["distance"] / 1000,
        "tempo_min": rota["duration"] / 60,
        "geometria_geojson": rota["geometry"],
    }
