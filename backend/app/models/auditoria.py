import enum
from datetime import datetime

from app import db


class TipoOperacaoEnum(enum.Enum):
    criacao = "criacao"
    edicao = "edicao"
    desativacao = "desativacao"
    exclusao = "exclusao"
    relatorio_gerado = "relatorio_gerado"


class EntidadeAuditoriaEnum(enum.Enum):
    """Tipos de entidade que podem ser auditados.

    Começou como um reaproveitamento do PapelEnum (socorrista/hospital/
    admin), mas RN-023 precisa auditar geração de relatório de Ocorrencia,
    que não é um papel de usuário — por isso um enum próprio agora, pra não
    poluir o domínio válido de Usuario.papel com um valor que nunca é um
    papel de fato.
    """

    socorrista = "socorrista"
    hospital = "hospital"
    admin = "admin"
    ocorrencia = "ocorrencia"


class Auditoria(db.Model):
    """RN-017: todo cadastro/edição/desativação/exclusão feito por um admin
    (e a geração de relatório final, RN-023) gera um registro aqui.
    Registros de auditoria são somente-leitura: não existe rota de edição
    ou exclusão para esta tabela.
    """

    __tablename__ = "auditoria"

    id = db.Column(db.Integer, primary_key=True)
    tipo_operacao = db.Column(
        db.Enum(TipoOperacaoEnum, name="tipo_operacao_enum"), nullable=False
    )
    entidade_tipo = db.Column(
        db.Enum(EntidadeAuditoriaEnum, name="entidade_auditoria_enum"), nullable=False
    )
    entidade_id = db.Column(db.Integer, nullable=False)
    # Nullable + SET NULL: se o admin autor for excluído fisicamente depois,
    # o registro de auditoria permanece para sempre, só perde essa referência.
    admin_id = db.Column(
        db.Integer, db.ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True
    )
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    admin = db.relationship("Usuario")
