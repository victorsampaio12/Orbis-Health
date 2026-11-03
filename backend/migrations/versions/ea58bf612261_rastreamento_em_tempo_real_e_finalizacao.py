"""rastreamento em tempo real e finalizacao

Revision ID: ea58bf612261
Revises: 371368e6e22b
Create Date: 2026-09-14 16:42:00.070239

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ea58bf612261'
down_revision = '371368e6e22b'
branch_labels = None
depends_on = None


def upgrade():
    # Auditoria.entidade_tipo reaproveitava o papel_enum (socorrista/
    # hospital/admin). RN-023 precisa auditar geração de relatório de
    # Ocorrencia, que não é um papel de usuário — daí um enum próprio,
    # separado do papel_enum (que continua existindo, só pra Usuario.papel).
    op.execute(
        "CREATE TYPE entidade_auditoria_enum AS ENUM "
        "('socorrista', 'hospital', 'admin', 'ocorrencia')"
    )
    op.execute(
        "ALTER TABLE auditoria "
        "ALTER COLUMN entidade_tipo TYPE entidade_auditoria_enum "
        "USING entidade_tipo::text::entidade_auditoria_enum"
    )

    # RN-023: novo tipo de operação auditada.
    op.execute("ALTER TYPE tipo_operacao_enum ADD VALUE IF NOT EXISTS 'relatorio_gerado'")

    with op.batch_alter_table('ocorrencia', schema=None) as batch_op:
        # Rename (preserva dados) em vez de drop+add: o campo virou
        # "posição atual" de verdade agora que existe rastreamento em
        # tempo real (HU-022), não só a localização de origem.
        batch_op.alter_column('latitude_origem', new_column_name='latitude_atual')
        batch_op.alter_column('longitude_origem', new_column_name='longitude_atual')
        batch_op.add_column(sa.Column('chegada_confirmada_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('finalizado_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('desfecho', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('ocorrencia', schema=None) as batch_op:
        batch_op.drop_column('desfecho')
        batch_op.drop_column('finalizado_em')
        batch_op.drop_column('chegada_confirmada_em')
        batch_op.alter_column('longitude_atual', new_column_name='longitude_origem')
        batch_op.alter_column('latitude_atual', new_column_name='latitude_origem')

    # Postgres não permite remover um valor de enum facilmente; o
    # downgrade do tipo_operacao_enum fica só documentado, não revertido.
    # Se alguma linha já tiver entidade_tipo='ocorrencia', este cast falha
    # de propósito — não existe um papel_enum correspondente pra ela.
    op.execute(
        "ALTER TABLE auditoria "
        "ALTER COLUMN entidade_tipo TYPE papel_enum "
        "USING entidade_tipo::text::papel_enum"
    )
    op.execute("DROP TYPE entidade_auditoria_enum")
