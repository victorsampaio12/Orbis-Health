from app.extensions import db

class Veiculo(db.Model):
    __tablename__ = 'veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    identificacao = db.Column(db.String(50), nullable=False, unique=True)
