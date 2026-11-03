from app import db


class Hospital(db.Model):
    __tablename__ = "hospital"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    tem_heliponto = db.Column(db.Boolean, nullable=False, default=False)
    tem_garagem = db.Column(db.Boolean, nullable=False, default=False)
    capacidade_maxima = db.Column(db.Integer, nullable=True)
    # Não estava na lista original de campos, mas é necessário para a RN-015
    # (login bloqueado para usuário vinculado a hospital desativado).
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=False
    )

    # Preenchidos via geocodificação do endereço (Nominatim) ao criar/editar
    # o hospital. Nulos se a geocodificação falhar — isso nunca bloqueia o
    # cadastro, só impede o hospital de aparecer no mapa até ser corrigido.
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    usuario = db.relationship("Usuario", back_populates="hospital")
