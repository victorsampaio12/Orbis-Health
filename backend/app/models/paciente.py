import enum
from datetime import datetime

from app import db


class PrioridadeEnum(enum.Enum):
    critica = "critica"
    alta = "alta"
    media = "media"


# código -> rótulo, na ordem em que aparecem (de cima para baixo)
REGIOES_LESAO = {
    "cabeca": "Cabeça",
    "pescoco": "Pescoço",
    "torax": "Tórax",
    "abdome": "Abdome",
    "pelve": "Pelve",
    "coluna": "Coluna",
    "braco_direito": "Braço direito",
    "braco_esquerdo": "Braço esquerdo",
    "perna_direita": "Perna direita",
    "perna_esquerda": "Perna esquerda",
}


class Paciente(db.Model):
    __tablename__ = "paciente"

    id = db.Column(db.Integer, primary_key=True)
    ocorrencia_id = db.Column(
        db.Integer, db.ForeignKey("ocorrencia.id"), nullable=False, index=True
    )

    # Dados do paciente
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(14), nullable=True)
    idade = db.Column(db.String(20), nullable=True)
    documentos_em_maos = db.Column(db.Boolean, nullable=True)

    # Causa socorro
    motivo_chamado = db.Column(db.Text, nullable=False)

    # Sinais vitais
    pressao_arterial = db.Column(db.String(20), nullable=True)
    frequencia_cardiaca = db.Column(db.Integer, nullable=True)
    frequencia_respiratoria = db.Column(db.Integer, nullable=True)
    saturacao_o2 = db.Column(db.Integer, nullable=True)
    temperatura = db.Column(db.Float, nullable=True)
    nivel_consciencia = db.Column(db.String(100), nullable=True)
    glasgow = db.Column(db.Integer, nullable=True)

    # Evolução no transporte (RN-010 usa agravamento_registrado e
    # parada_cardiorrespiratoria; estavel/melhorando são só informativos)
    estavel = db.Column(db.Boolean, nullable=False, default=False)
    agravamento_registrado = db.Column(db.Boolean, nullable=False, default=False)
    melhorando = db.Column(db.Boolean, nullable=False, default=False)
    parada_cardiorrespiratoria = db.Column(db.Boolean, nullable=False, default=False)
    observacao = db.Column(db.Text, nullable=True)

    diagnostico = db.Column(db.Text, nullable=True)

    # Regiões do corpo com lesão, marcadas no boneco 3D do cadastro e
    # destacadas para o hospital no pré-prontuário. Lista separada por
    # vírgula com os códigos de REGIOES_LESAO (ordem canônica).
    regioes_lesao = db.Column(db.String(200), nullable=True)

    # RN-010: calculada em toda criação/atualização, nunca digitada.
    prioridade = db.Column(
        db.Enum(PrioridadeEnum, name="prioridade_enum"),
        nullable=False,
        default=PrioridadeEnum.media,
    )

    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    ocorrencia = db.relationship("Ocorrencia", back_populates="pacientes")
    anexos = db.relationship(
        "AnexoPaciente",
        back_populates="paciente",
        cascade="all, delete-orphan",
        order_by="AnexoPaciente.criado_em",
    )

    @property
    def regioes_lesao_lista(self):
        return [r for r in (self.regioes_lesao or "").split(",") if r in REGIOES_LESAO]
