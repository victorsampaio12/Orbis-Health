from app.extensions import db

class Socorrista(db.Model):
    __tablename__ = 'socorristas'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    registro = db.Column(db.String(50), nullable=False)
    especialidade = db.Column(db.String(50), nullable=False)
    turno = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f'<Socorrista {self.nome}>'
