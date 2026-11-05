from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from .ticket import Chamado
    from .user import Usuario


class HistoricoStatus(db.Model):
    __tablename__ = "historico_status"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("chamados.id"), nullable=False)
    previous_status: Mapped[str] = mapped_column(db.String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(db.String(30), nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    changed_by_id: Mapped[int] = mapped_column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    chamado: Mapped["Chamado"] = relationship(
        "Chamado",
        foreign_keys=[ticket_id],
    )
    changed_by: Mapped["Usuario"] = relationship(
        "Usuario",
        foreign_keys=[changed_by_id],
    )
