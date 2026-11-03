"""anexos (fotos) do paciente

Revision ID: b3f1c2d4e5a6
Revises: 5559a20b65a8
Create Date: 2026-10-20 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3f1c2d4e5a6'
down_revision = '5559a20b65a8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'anexo_paciente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('paciente_id', sa.Integer(), nullable=False),
        sa.Column('enviado_por_id', sa.Integer(), nullable=False),
        sa.Column('nome_original', sa.String(length=255), nullable=False),
        sa.Column('arquivo', sa.String(length=255), nullable=False),
        sa.Column('largura', sa.Integer(), nullable=False),
        sa.Column('altura', sa.Integer(), nullable=False),
        sa.Column('tamanho_bytes', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['paciente_id'], ['paciente.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['enviado_por_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('arquivo'),
    )
    with op.batch_alter_table('anexo_paciente', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_anexo_paciente_paciente_id'), ['paciente_id'], unique=False)


def downgrade():
    with op.batch_alter_table('anexo_paciente', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_anexo_paciente_paciente_id'))
    op.drop_table('anexo_paciente')
