import enum
from datetime import datetime

from flask_login import UserMixin

from app import db


class PapelEnum(enum.Enum):
    socorrista = "socorrista"
    hospital = "hospital"
    admin = "admin"


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    # RN-001: todo usuário tem exatamente um papel; não existe usuário sem papel.
    papel = db.Column(db.Enum(PapelEnum, name="papel_enum"), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    # Preferências da própria conta (tela Preferências). Só guarda o que o
    # usuário mudou; o que falta cai no padrão (conta_service.PREFERENCIAS_PADRAO).
    preferencias = db.Column(db.JSON, nullable=True)
    tentativas_falhas = db.Column(db.Integer, nullable=False, default=0)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    hospital = db.relationship("Hospital", back_populates="usuario", uselist=False)
    socorrista = db.relationship("Socorrista", back_populates="usuario", uselist=False)
