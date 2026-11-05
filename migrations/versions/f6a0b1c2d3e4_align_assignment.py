"""Align tickets and roles with the help desk assignment.

Revision ID: f6a0b1c2d3e4
Revises: e4f9b2c3d5a6
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a0b1c2d3e4"
down_revision = "e4f9b2c3d5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chamados", sa.Column("item_name", sa.String(150)))
    op.add_column("chamados", sa.Column("equipment_tag", sa.String(100)))
    op.add_column("chamados", sa.Column("reported_date", sa.Date()))
    # shortcut: etiquetas antigas ficam sem número real; preencha quando forem recuperadas.
    op.execute(
        "UPDATE chamados SET item_name = title, equipment_tag = 'Não informado', "
        "reported_date = (created_at AT TIME ZONE 'America/Sao_Paulo')::date"
    )
    for column in ("item_name", "equipment_tag", "reported_date"):
        op.alter_column("chamados", column, nullable=False)

    op.execute("ALTER TABLE chamados ALTER COLUMN status TYPE varchar USING status::text")
    op.execute(
        "UPDATE chamados SET status = CASE "
        "WHEN status IN ('EM_ATENDIMENTO', 'EM_ESPERA', 'AGUARDANDO_APROVACAO') "
        "THEN 'EM_ANDAMENTO' "
        "WHEN status = 'FECHADO' THEN 'FINALIZADO' "
        "ELSE status END"
    )
    op.execute("DROP TYPE statusenum")
    op.execute("CREATE TYPE statusenum AS ENUM ('EM_ABERTO', 'EM_ANDAMENTO', 'FINALIZADO')")
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum " "USING status::statusenum"
    )


def downgrade():
    op.execute("ALTER TABLE chamados ALTER COLUMN status TYPE varchar USING status::text")
    op.execute(
        "UPDATE chamados SET status = CASE "
        "WHEN status = 'EM_ANDAMENTO' THEN 'EM_ATENDIMENTO' "
        "WHEN status = 'FINALIZADO' THEN 'FECHADO' ELSE status END"
    )
    op.execute("DROP TYPE statusenum")
    op.execute(
        "CREATE TYPE statusenum AS ENUM ('EM_ABERTO', 'EM_ATENDIMENTO', 'EM_ESPERA', "
        "'AGUARDANDO_APROVACAO', 'FECHADO')"
    )
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum " "USING status::statusenum"
    )
    for column in ("reported_date", "equipment_tag", "item_name"):
        op.drop_column("chamados", column)
