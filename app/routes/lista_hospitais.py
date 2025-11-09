from flask import Blueprint, render_template, request
from app.models.hospital import Hospital
import folium
from folium.plugins import MarkerCluster

lista_hospitais_bp = Blueprint('lista_hospitais_bp', __name__)

@lista_hospitais_bp.route('/hospitais')
def lista_hospitais():
    hospitais = Hospital.query.all()
    hospitais_dict = [h.to_dict() for h in hospitais]  
    return render_template('lista_hospitais.html', hospitais=hospitais_dict)
