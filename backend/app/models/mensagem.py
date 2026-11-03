from datetime import datetime

from app import db


class Mensagem(db.Model):
    """HU-018/HU-019: chat entre o socorrista dono e o hospital destino de
    uma ocorrência (RN-016). Toda mensagem passa pelo WebSocket, mas é
    sempre persistida aqui — inclusive as em tempo real — pra existir
    histórico depois (inclusive após o chat ser encerrado, RN-022)."""

    __tablename__ = "mensagem"

    id = db.Column(db.Integer, primary_key=True)
    ocorrencia_id = db.Column(
        db.Integer, db.ForeignKey("ocorrencia.id"), nullable=False
    )
    remetente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    enviado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lida = db.Column(db.Boolean, nullable=False, default=False)

    ocorrencia = db.relationship("Ocorrencia", back_populates="mensagens")
    remetente = db.relationship("Usuario")
