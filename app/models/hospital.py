from app.extensions import db

class Hospital(db.Model):
    __tablename__ = 'hospital'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    longitude = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'latitude': self.latitude,
            'longitude': self.longitude
        }