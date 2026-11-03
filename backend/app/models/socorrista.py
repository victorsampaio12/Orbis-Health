from app import db


class Socorrista(db.Model):
    __tablename__ = "socorrista"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=False
    )
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    # Opcional: aparece no card/painel de contato do hospital (ligar).
    telefone = db.Column(db.String(30), nullable=True)
    # Status ativo/inativo reaproveita Usuario.ativo (RN-014): socorrista
    # inativo consegue logar normalmente; isso só bloqueia ações operacionais
    # em etapas futuras, não o login.

    usuario = db.relationship("Usuario", back_populates="socorrista")
