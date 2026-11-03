import enum
from datetime import datetime

from app import db


class VeiculoEnum(enum.Enum):
    ambulancia = "ambulancia"
    helicoptero = "helicoptero"


class StatusOcorrenciaEnum(enum.Enum):
    aberta = "aberta"
    em_transporte = "em_transporte"
    finalizada = "finalizada"


class TipoRotaEnum(enum.Enum):
    linha_reta = "linha_reta"
    terrestre = "terrestre"


class Ocorrencia(db.Model):
    __tablename__ = "ocorrencia"

    id = db.Column(db.Integer, primary_key=True)
    socorrista_id = db.Column(
        db.Integer, db.ForeignKey("socorrista.id"), nullable=False
    )
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospital.id"), nullable=True)
    # Snapshot da posição do hospital no momento em que ele foi selecionado
    # como destino (RN-004/005). Não usamos hospital.latitude/longitude
    # diretamente em nenhum cálculo de rota/chegada porque, se o endereço do
    # hospital for editado DEPOIS (ex: correção de cadastro) enquanto uma
    # ocorrência já está em transporte pra lá, o destino não pode "se mover"
    # embaixo do socorrista — a rota já gerada e a checagem de chegada
    # continuam valendo pro lugar combinado na hora da seleção.
    destino_latitude = db.Column(db.Float, nullable=True)
    destino_longitude = db.Column(db.Float, nullable=True)
    veiculo = db.Column(db.Enum(VeiculoEnum, name="veiculo_enum"), nullable=False)
    status = db.Column(
        db.Enum(StatusOcorrenciaEnum, name="status_ocorrencia_enum"),
        nullable=False,
        default=StatusOcorrenciaEnum.aberta,
    )
    # RN-005: preenchido automaticamente ao selecionar o hospital destino,
    # nunca escolhido pelo usuário. Nulo enquanto a ocorrência está aberta.
    tipo_rota = db.Column(db.Enum(TipoRotaEnum, name="tipo_rota_enum"), nullable=True)
    local = db.Column(db.String(255), nullable=False)
    comentarios = db.Column(db.Text, nullable=True)

    # Posição atual do veículo (HU-013 na criação, HU-022 atualiza em tempo
    # real via WebSocket durante o transporte). Nula até o navegador
    # conseguir capturar a primeira vez.
    latitude_atual = db.Column(db.Float, nullable=True)
    longitude_atual = db.Column(db.Float, nullable=True)

    # Dados da rota gerada (HU-009). rota_geometria guarda o GeoJSON como
    # texto pra desenhar no Leaflet sem chamar a API de novo a cada reload.
    # tempo_estimado_min é recalculado a cada posição nova (HU-022), mas a
    # geometria em si não muda depois de gerada.
    distancia_estimada_km = db.Column(db.Float, nullable=True)
    tempo_estimado_min = db.Column(db.Float, nullable=True)
    rota_geometria = db.Column(db.Text, nullable=True)
    rota_gerada_em = db.Column(db.DateTime, nullable=True)

    # Trajeto simulado (trajeto_service): quando começou e quanto dura. A
    # posição do veículo é função pura destes dois valores + a geometria da
    # rota, então dá pra retomar a simulação depois de reiniciar o servidor.
    trajeto_iniciado_em = db.Column(db.DateTime, nullable=True)
    trajeto_duracao_s = db.Column(db.Float, nullable=True)

    # HU-021: quando o socorrista confirma ter chegado (RN de distância
    # verificada em rota_service). Separado de "finalizada" porque a
    # ocorrência continua em_transporte até o socorrista finalizar de fato.
    chegada_confirmada_em = db.Column(db.DateTime, nullable=True)

    # HU-020/RN-023: preenchidos só na finalização.
    finalizado_em = db.Column(db.DateTime, nullable=True)
    desfecho = db.Column(db.Text, nullable=True)

    # RN-022: encerrado na mesma transação da finalização — depois disso
    # nenhuma mensagem nova pode ser enviada no chat desta ocorrência
    # (histórico continua acessível, só leitura).
    chat_encerrado_em = db.Column(db.DateTime, nullable=True)

    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    socorrista = db.relationship("Socorrista")
    hospital = db.relationship("Hospital")
    pacientes = db.relationship(
        "Paciente", back_populates="ocorrencia", cascade="all, delete-orphan"
    )
    mensagens = db.relationship(
        "Mensagem",
        back_populates="ocorrencia",
        cascade="all, delete-orphan",
        order_by="Mensagem.enviado_em",
    )
