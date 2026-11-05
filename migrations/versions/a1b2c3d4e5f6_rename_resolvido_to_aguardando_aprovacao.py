"""rename status RESOLVIDO to AGUARDANDO_APROVACAO

O antigo status "Resolvido" passa a ser "Aguardando Aprovação": o técnico
conclui o atendimento e o chamado fica pendente da aprovação de quem o abriu,
sendo fechado automaticamente na aprovação.

Revision ID: a1b2c3d4e5f6
Revises: 00feff76f2e8
Create Date: 2026-05-27 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '00feff76f2e8'
branch_labels = None
depends_on = None


def upgrade():
    # Renomeia o rótulo do tipo ENUM nativo do Postgres (transaction-safe, PG 10+).
    op.execute("ALTER TYPE statusenum RENAME VALUE 'RESOLVIDO' TO 'AGUARDANDO_APROVACAO'")
    # Atualiza os valores legíveis já gravados na auditoria.
    op.execute(
        "UPDATE historico_status SET new_status = 'Aguardando Aprovação' "
        "WHERE new_status = 'Resolvido'"
    )
    op.execute(
        "UPDATE historico_status SET previous_status = 'Aguardando Aprovação' "
        "WHERE previous_status = 'Resolvido'"
    )


def downgrade():
    op.execute(
        "UPDATE historico_status SET new_status = 'Resolvido' "
        "WHERE new_status = 'Aguardando Aprovação'"
    )
    op.execute(
        "UPDATE historico_status SET previous_status = 'Resolvido' "
        "WHERE previous_status = 'Aguardando Aprovação'"
    )
    op.execute("ALTER TYPE statusenum RENAME VALUE 'AGUARDANDO_APROVACAO' TO 'RESOLVIDO'")
