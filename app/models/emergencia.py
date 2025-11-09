from datetime import datetime
from app.extensions import db
from sqlalchemy.sql import func

class Emergencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='rascunho')
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    hospital = db.relationship('Hospital', backref='emergencias')
    data_hora = db.Column(db.DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)  
    unidade = db.Column(db.String(100), nullable=True)
    profissional_id = db.Column(db.Integer, db.ForeignKey('socorristas.id'), nullable=True)
    profissional = db.relationship('Socorrista', lazy='joined')
    nome_paciente = db.Column(db.String(120), nullable=True)
    idade_aparente = db.Column(db.String(50), nullable=True)
    documento_em_maos = db.Column(db.Boolean, default=False)
    motivo_chamado = db.Column(db.Text, nullable=True)
    pressao_arterial = db.Column(db.String(50), nullable=True)
    frequencia_cardiaca = db.Column(db.String(50), nullable=True)
    frequencia_respiratoria = db.Column(db.String(50), nullable=True)
    saturacao = db.Column(db.String(50), nullable=True)
    temperatura = db.Column(db.String(50), nullable=True)
    nivel_consciencia = db.Column(db.String(100), nullable=True)
    glasgow = db.Column(db.String(50), nullable=True)
    estavel = db.Column(db.Boolean, default=False)
    agravamento = db.Column(db.Boolean, default=False)
    melhorando = db.Column(db.Boolean, default=False)
    parada_cardiorrespiratoria = db.Column(db.Boolean, default=False)
    observacoes = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float)  
    longitude = db.Column(db.Float)  
    tipo_veiculo = db.Column(db.String(20))
    caminho_pdf = db.Column(db.String(200), nullable=True)


