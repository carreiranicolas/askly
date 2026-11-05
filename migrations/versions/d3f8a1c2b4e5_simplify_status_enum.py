"""simplify status enum to four lifecycle states

Revision ID: d3f8a1c2b4e5
Revises: c2d4e7f1a8b9
Create Date: 2026-06-03 12:00:00.000000

"""
from alembic import op


revision = "d3f8a1c2b4e5"
down_revision = "c2d4e7f1a8b9"
branch_labels = None
depends_on = None

_OLD_TO_NEW = {
    "ABERTO": "EM_ATENDIMENTO",
    "EM_ANALISE": "EM_ATENDIMENTO",
    "EM_ATENDIMENTO": "EM_ATENDIMENTO",
    "AGUARDANDO_CLIENTE": "EM_ESPERA",
    "AGUARDANDO_TECNICO": "EM_ESPERA",
    "AGUARDANDO_PECA": "EM_ESPERA",
    "ATENDIMENTO_AGENDADO": "EM_ESPERA",
    "AGUARDANDO_APROVACAO": "AGUARDANDO_APROVACAO",
    "FECHADO": "FECHADO",
    "CANCELADO": "FECHADO",
}

_NEW_VALUES = (
    "EM_ATENDIMENTO",
    "EM_ESPERA",
    "AGUARDANDO_APROVACAO",
    "FECHADO",
)

_OLD_VALUES = tuple(_OLD_TO_NEW.keys())


def upgrade():
    op.execute("ALTER TABLE chamados ALTER COLUMN status TYPE varchar USING status::text")

    for old, new in _OLD_TO_NEW.items():
        if old != new:
            op.execute(f"UPDATE chamados SET status = '{new}' WHERE status = '{old}'")

    op.execute("DROP TYPE statusenum")
    new_values = ", ".join(f"'{v}'" for v in _NEW_VALUES)
    op.execute(f"CREATE TYPE statusenum AS ENUM ({new_values})")
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum "
        "USING status::statusenum"
    )


def downgrade():
    op.execute("ALTER TABLE chamados ALTER COLUMN status TYPE varchar USING status::text")

    op.execute(
        "UPDATE chamados SET status = 'ABERTO' "
        "WHERE status IN ('EM_ATENDIMENTO', 'EM_ESPERA')"
    )
    op.execute(
        "UPDATE chamados SET status = 'AGUARDANDO_CLIENTE' "
        "WHERE status = 'EM_ESPERA'"
    )

    op.execute("DROP TYPE statusenum")
    old_values = ", ".join(f"'{v}'" for v in _OLD_VALUES)
    op.execute(f"CREATE TYPE statusenum AS ENUM ({old_values})")
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum "
        "USING status::statusenum"
    )
