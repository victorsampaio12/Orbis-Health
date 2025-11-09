from flask import Blueprint, request, jsonify
import requests

rota_bp = Blueprint('rota_bp', __name__)

@rota_bp.route('/rota', methods=['POST'])
def rota():
    dados = request.get_json()
    origem = dados['origem']
    destino = dados['destino']

    url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson'
    headers = {
        'Authorization': '5b3ce3597851110001cf6248ce7dacbf89e4464ab7983c7394f7eac3',
        'Content-Type': 'application/json'
    }
    body = {
        "coordinates": [
            [origem['lng'], origem['lat']],
            [destino['lng'], destino['lat']]
        ]
    }

    resposta = requests.post(url, json=body, headers=headers)
    if resposta.status_code != 200:
        return jsonify({'error': 'Erro ao buscar rota'}), 500
    return jsonify(resposta.json())
