from flask import Flask
from flask_migrate import Migrate
from config import Config
from app.extensions import db
from app.routes.telainicial import telainicial_bp  
from app.routes.socorrista import socorrista_bp
from app.routes.hospital import hospital_bp
from app.routes.veiculo import veiculo_bp
from app.routes.menu import menu_bp
from app.routes.emergencia import emergencia_bp
from app.routes.lista_hospitais import lista_hospitais_bp
from app.routes.rota import rota_bp


migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    app.register_blueprint(hospital_bp)
    app.register_blueprint(telainicial_bp)
    app.register_blueprint(socorrista_bp)
    app.register_blueprint(veiculo_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(emergencia_bp)
    app.register_blueprint(lista_hospitais_bp)
    app.register_blueprint(rota_bp)
    
    return app
