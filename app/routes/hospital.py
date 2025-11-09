from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.forms import CadastroHospitalForm
from app.models.hospital import Hospital
from app.models.emergencia import Emergencia
from app.extensions import db
from datetime import datetime
import requests
import json

hospital_bp = Blueprint('hospital_bp', __name__)

@hospital_bp.route('/cadastrar-hospital', methods=['GET', 'POST'])
def cadastrar_hospital():
    form = CadastroHospitalForm()
    if form.validate_on_submit():
        novo = Hospital(
            nome=form.nome.data,
            longitude=form.longitude.data,
            latitude=form.latitude.data
        )
        db.session.add(novo)
        db.session.commit()
        flash('Hospital cadastrado com sucesso!', 'success')
        return redirect(url_for('telainicial.telainicial'))
    return render_template('cadastrohospital.html', form=form)

@hospital_bp.route('/hospital/selecionar', methods=['GET', 'POST'])
def selecionar_hospital():
    hospitais = Hospital.query.all()
    if request.method == 'POST':
        session['perfil'] = 'hospital'
        session['hospital_id'] = request.form['hospital_id']
        return redirect(url_for('hospital_bp.menu_hospital'))
    return render_template('selecionar_hospital.html', hospitais=hospitais)

@hospital_bp.route('/hospital/menu')
def menu_hospital():
    if 'hospital_id' not in session:
        return redirect(url_for('hospital_bp.selecionar_hospital'))
    
    hospital = Hospital.query.get(session['hospital_id'])
    return render_template('menuhospital.html', hospital=hospital)

@hospital_bp.route('/hospital/emergencias')
def emergencias_a_caminho():
    if 'hospital_id' not in session:
        return redirect(url_for('hospital_bp.selecionar_hospital'))

    hospital = Hospital.query.get(session['hospital_id'])
    emergencia = Emergencia.query.filter(
    Emergencia.hospital_id == hospital.id,
    Emergencia.latitude.isnot(None),
    Emergencia.longitude.isnot(None)
        ).order_by(Emergencia.data_hora.desc()).first()

    if not emergencia:
        flash('Nenhuma emergência com localização encontrada para este hospital.', 'warning')
        return render_template('emergencias_a_caminho.html', emergencia=None, hospital=hospital)

    if hasattr(emergencia, 'latitude') and emergencia.latitude and emergencia.longitude:
        lat_emergencia = emergencia.latitude
        lng_emergencia = emergencia.longitude
    else:
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        if not lat or not lng:
            return "Localização da emergência não foi fornecida.", 400
        try:
            lat_emergencia = float(lat)
            lng_emergencia = float(lng)
        except ValueError:
            return "Coordenadas inválidas.", 400

    origem = [lat_emergencia, lng_emergencia]
    destino = [hospital.latitude, hospital.longitude]

    tipo_veiculo = getattr(emergencia, 'tipo_veiculo', 'Ambulância')  
    print(f"Tipo de veículo usado na emergência: {tipo_veiculo}")

    rota = []

    if tipo_veiculo == 'Helicóptero':
        rota = [origem, destino]
    else:
        api_key = '5b3ce3597851110001cf6248ce7dacbf89e4464ab7983c7394f7eac3'
        url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson'
        body = {
            "coordinates": [
                [origem[1], origem[0]],
                [destino[1], destino[0]]
            ]
        }

        try:
            res = requests.post(url, json=body, headers={'Authorization': api_key})
            res.raise_for_status()
            data = res.json()
            coords = data['features'][0]['geometry']['coordinates']
            rota = [[c[1], c[0]] for c in coords]  
        except Exception as e:
            print(f"Erro ao buscar rota para ambulância: {e}")

    return render_template(
        'emergencias_a_caminho.html',
        emergencia=emergencia,
        hospital=hospital,
        lat_emergencia=lat_emergencia,
        lng_emergencia=lng_emergencia,
        rota=rota,
        origem=origem,
        destino=destino,
        tipo_veiculo=tipo_veiculo
    )

@hospital_bp.route('/hospital/monitoramento/<int:hospital_id>')
def monitoramento_hospital(hospital_id):
    hospital = Hospital.query.get(hospital_id)
    lat = request.args.get('lat')
    lng = request.args.get('lng')

    if lat is None or lng is None:
        return "Localização da emergência não fornecida.", 400

    try:
        lat = float(lat)
        lng = float(lng)
    except ValueError:
        return "Coordenadas inválidas.", 400

    return render_template('emergencias_a_caminho.html', hospital=hospital, lat_emergencia=lat, lng_emergencia=lng)

@hospital_bp.route('/salvar_emergencia', methods=['POST'])
def salvar_emergencia():
    data = request.get_json()
    hospital_id = data.get('hospital_id')
    lat = data.get('lat')
    lng = data.get('lng')
    tipo_veiculo = data.get('tipo_veiculo')

    if not hospital_id or not lat or not lng:
        return jsonify({'error': 'Hospital e localização são obrigatórios.'}), 400

    try:
        emergencia = Emergencia(
            hospital_id=hospital_id,
            latitude=float(lat),
            longitude=float(lng),
            tipo_veiculo=tipo_veiculo,
        )
        db.session.add(emergencia)
        db.session.commit()
        return jsonify({'emergencia_id': emergencia.id}), 200
    except Exception as e:
        print(f"Erro ao salvar emergência: {e}")
        return jsonify({'error': 'Erro interno ao salvar emergência.'}), 500

@hospital_bp.route('/hospital/historico')
def historico_emergencias():
    if 'hospital_id' not in session:
        return redirect(url_for('hospital_bp.selecionar_hospital'))

    emergencias = Emergencia.query.order_by(Emergencia.data_hora.desc()).all()
    return render_template('historico_emergencias.html', emergencias=emergencias)