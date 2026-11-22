"""índices das chaves estrangeiras mais consultadas

O PostgreSQL não cria índice para chave estrangeira sozinho. Sem eles, o
painel, o histórico e o inbox varriam as tabelas inteiras a cada abertura —
achado do teste de volume (Plano de Testes, 7.2.8), com 20 mil ocorrências.

Revision ID: c7d8e9f0a1b2
Revises: b3f1c2d4e5a6
Create Date: 2026-11-09 14:00:00.000000

"""
from alembic import op


revision = 'c7d8e9f0a1b2'
down_revision = 'b3f1c2d4e5a6'
branch_labels = None
depends_on = None

INDICES = [
    ('ix_ocorrencia_hospital_id', 'ocorrencia', 'hospital_id'),
    ('ix_ocorrencia_socorrista_id', 'ocorrencia', 'socorrista_id'),
    ('ix_mensagem_ocorrencia_id', 'mensagem', 'ocorrencia_id'),
    ('ix_paciente_ocorrencia_id', 'paciente', 'ocorrencia_id'),
]


def upgrade():
    for nome, tabela, coluna in INDICES:
        op.create_index(nome, tabela, [coluna], unique=False)


def downgrade():
    for nome, tabela, _ in INDICES:
        op.drop_index(nome, table_name=tabela)
