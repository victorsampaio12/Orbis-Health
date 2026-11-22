"""regiões da lesão do paciente (boneco 3D)

Coluna nova e opcional: pacientes já cadastrados ficam com NULL (nenhuma
região marcada). Não altera nem apaga nenhum dado existente.

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-11-10 19:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = 'd1e2f3a4b5c6'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('paciente', sa.Column('regioes_lesao', sa.String(length=200), nullable=True))


def downgrade():
    op.drop_column('paciente', 'regioes_lesao')
