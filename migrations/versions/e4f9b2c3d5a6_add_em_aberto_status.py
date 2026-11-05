"""add EM_ABERTO status for unassigned tickets

Revision ID: e4f9b2c3d5a6
Revises: d3f8a1c2b4e5
Create Date: 2026-06-03 20:00:00.000000

"""
from alembic import op


revision = "e4f9b2c3d5a6"
down_revision = "d3f8a1c2b4e5"
branch_labels = None
depends_on = None

_NEW_VALUES = (
    "EM_ABERTO",
    "EM_ATENDIMENTO",
    "EM_ESPERA",
    "AGUARDANDO_APROVACAO",
    "FECHADO",
)

_OLD_VALUES = (
    "EM_ATENDIMENTO",
    "EM_ESPERA",
    "AGUARDANDO_APROVACAO",
    "FECHADO",
)


def upgrade():
    op.execute("ALTER TABLE chamados ALTER COLUMN status TYPE varchar USING status::text")

    op.execute(
        "UPDATE chamados SET status = 'EM_ABERTO' "
        "WHERE status = 'EM_ATENDIMENTO' AND assignee_id IS NULL"
    )

    op.execute("DROP TYPE statusenum")
    new_values = ", ".join(f"'{v}'" for v in _NEW_VALUES)
    op.execute(f"CREATE TYPE statusenum AS ENUM ({new_values})")
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum "
        "USING status::statusenum"
    )


def downgrade():
    op.execute("ALTER TABLE chamados ALTER COLUMN status TYPE varchar USING status::text")

    op.execute("UPDATE chamados SET status = 'EM_ATENDIMENTO' WHERE status = 'EM_ABERTO'")

    op.execute("DROP TYPE statusenum")
    old_values = ", ".join(f"'{v}'" for v in _OLD_VALUES)
    op.execute(f"CREATE TYPE statusenum AS ENUM ({old_values})")
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum "
        "USING status::statusenum"
    )
