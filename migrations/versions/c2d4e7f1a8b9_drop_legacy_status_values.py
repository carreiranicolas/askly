"""drop legacy status values (ATRIBUIR_TECNICO, MUDAR_CATEGORIA, MUDAR_PRIORIDADE)

Esses valores eram ações operacionais (atribuir responsável, mudar área/
prioridade) representadas erroneamente como status do ciclo de vida do
chamado. Eles passam a ser apenas operações com endpoints próprios; o
enum só descreve estados reais do chamado.

Qualquer chamado ainda gravado com algum desses valores é migrado para
``ABERTO`` (estado seguro para o time retomar o trabalho); o histórico de
auditoria é preservado integralmente.

Revision ID: c2d4e7f1a8b9
Revises: a1b2c3d4e5f6
Create Date: 2026-05-27 20:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c2d4e7f1a8b9'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


_LEGACY_VALUES = ('ATRIBUIR_TECNICO', 'MUDAR_CATEGORIA', 'MUDAR_PRIORIDADE')

_NEW_VALUES = (
    'ABERTO',
    'EM_ANALISE',
    'EM_ATENDIMENTO',
    'AGUARDANDO_CLIENTE',
    'AGUARDANDO_TECNICO',
    'AGUARDANDO_PECA',
    'ATENDIMENTO_AGENDADO',
    'AGUARDANDO_APROVACAO',
    'FECHADO',
    'CANCELADO',
)


def upgrade():
    # 1) Drena chamados parados em status legados para ABERTO (estado seguro).
    placeholders = ', '.join(f"'{v}'" for v in _LEGACY_VALUES)
    op.execute(
        f"UPDATE chamados SET status = 'ABERTO' WHERE status::text IN ({placeholders})"
    )

    # 2) Recria o tipo ENUM sem os valores legados (Postgres não permite
    # `DROP VALUE` antes da versão 17 — recriamos o tipo e fazemos cast).
    new_values = ', '.join(f"'{v}'" for v in _NEW_VALUES)
    op.execute(f"CREATE TYPE statusenum_new AS ENUM ({new_values})")
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum_new "
        "USING status::text::statusenum_new"
    )
    op.execute("DROP TYPE statusenum")
    op.execute("ALTER TYPE statusenum_new RENAME TO statusenum")


def downgrade():
    # Recria o enum antigo (com os três valores legados) e migra de volta.
    full = _NEW_VALUES + _LEGACY_VALUES
    full_values = ', '.join(f"'{v}'" for v in full)
    op.execute(f"CREATE TYPE statusenum_old AS ENUM ({full_values})")
    op.execute(
        "ALTER TABLE chamados ALTER COLUMN status TYPE statusenum_old "
        "USING status::text::statusenum_old"
    )
    op.execute("DROP TYPE statusenum")
    op.execute("ALTER TYPE statusenum_old RENAME TO statusenum")
