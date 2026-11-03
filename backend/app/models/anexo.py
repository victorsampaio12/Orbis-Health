from datetime import datetime

from app import db


class AnexoPaciente(db.Model):
    """Foto anexada ao pré-prontuário de um paciente pelo socorrista, para o
    hospital de destino ver antes da chegada. O arquivo fica em disco
    (UPLOAD_FOLDER) e só é servido pela rota protegida da ocorrência — mesma
    regra de acesso do prontuário (RN-007)."""

    __tablename__ = "anexo_paciente"

    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(
        db.Integer, db.ForeignKey("paciente.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enviado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    # caminho relativo ao UPLOAD_FOLDER; a miniatura fica ao lado, com sufixo
    arquivo = db.Column(db.String(255), nullable=False, unique=True)
    largura = db.Column(db.Integer, nullable=False)
    altura = db.Column(db.Integer, nullable=False)
    tamanho_bytes = db.Column(db.Integer, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    paciente = db.relationship("Paciente", back_populates="anexos")
    enviado_por = db.relationship("Usuario")
