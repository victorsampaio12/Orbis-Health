"""Cliente isolado para o Nominatim (geocodificação OpenStreetMap).

Servidor público por padrão (NOMINATIM_BASE_URL), sem chave de API, mas com
política de uso justo — por isso o timeout curto e o User-Agent
identificável. Qualquer erro de rede/formato retorna None em vez de
propagar exceção: quem chama decide o que fazer (nunca deve travar um
cadastro por causa disso).
"""

import urllib.error
import urllib.parse
import urllib.request

from flask import current_app

TIMEOUT_SEGUNDOS = 5


def _get_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": current_app.config["MAPS_USER_AGENT"]}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEGUNDOS) as resposta:
            import json

            return json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def geocodificar_endereco(endereco):
    """Endereço -> (latitude, longitude), ou None se não achar/der erro."""
    base_url = current_app.config["NOMINATIM_BASE_URL"]
    query = urllib.parse.urlencode({"q": endereco, "format": "json", "limit": 1})
    dados = _get_json(f"{base_url}/search?{query}")

    if not dados:
        return None

    try:
        primeiro = dados[0]
        return float(primeiro["lat"]), float(primeiro["lon"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def sugerir_enderecos(texto, limite=5):
    """Texto parcial -> lista de candidatos [(display_name, lat, lon), ...].

    Usado pro autocomplete do formulário de hospital: em vez de tentar
    geocodificar o texto exato que o admin digitou (e falhar por causa de
    uma abreviação que o Nominatim não reconhece, por exemplo), mostra as
    variações que ele realmente tem indexadas pra escolher — muito mais
    confiável, porque o admin está confirmando um endereço real, não
    torcendo pra busca por texto livre acertar.
    """
    base_url = current_app.config["NOMINATIM_BASE_URL"]
    query = urllib.parse.urlencode({"q": texto, "format": "json", "limit": limite})
    dados = _get_json(f"{base_url}/search?{query}")

    if not dados:
        return []

    sugestoes = []
    for item in dados:
        try:
            sugestoes.append(
                {
                    "display_name": item["display_name"],
                    "latitude": float(item["lat"]),
                    "longitude": float(item["lon"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sugestoes


def geocodificar_reverso(latitude, longitude):
    """Coordenadas -> endereço legível, ou None se não achar/der erro."""
    base_url = current_app.config["NOMINATIM_BASE_URL"]
    query = urllib.parse.urlencode(
        {"lat": latitude, "lon": longitude, "format": "json"}
    )
    dados = _get_json(f"{base_url}/reverse?{query}")

    if not dados:
        return None

    return dados.get("display_name")
