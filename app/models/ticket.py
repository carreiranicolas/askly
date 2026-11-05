import enum
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.category import Categoria
    from app.models.priority import Prioridade
    from app.models.user import Usuario


class StatusEnum(enum.Enum):
    EM_ABERTO = "Em aberto"
    EM_ANDAMENTO = "Em andamento"
    FINALIZADO = "Finalizado"


class Chamado(db.Model):
    __tablename__ = "chamados"
    __table_args__ = (
        db.Index("ix_chamados_status", "status"),
        db.Index("ix_chamados_category_status", "category_id", "status"),
        db.Index("ix_chamados_requester", "requester_id"),
        db.Index("ix_chamados_assignee", "assignee_id"),
        db.Index("ix_chamados_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    title: Mapped[str] = mapped_column(db.String(150), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)
    item_name: Mapped[str] = mapped_column(db.String(150), nullable=False)
    equipment_tag: Mapped[str] = mapped_column(db.String(100), nullable=False)
    reported_date: Mapped[date] = mapped_column(db.Date, nullable=False)
    priority_id: Mapped[int] = mapped_column(
        db.Integer, db.ForeignKey("prioridades.id"), nullable=False
    )
    status: Mapped[StatusEnum] = mapped_column(db.Enum(StatusEnum), default=StatusEnum.EM_ABERTO)
    requester_id: Mapped[int] = mapped_column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    assignee_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True
    )
    category_id: Mapped[int] = mapped_column(
        db.Integer, db.ForeignKey("categorias.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    requester: Mapped["Usuario"] = relationship(
        "Usuario",
        foreign_keys=[requester_id],
    )
    assignee: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[assignee_id],
    )

    category: Mapped["Categoria"] = relationship(
        "Categoria", backref="chamados", foreign_keys=[category_id]
    )

    priority: Mapped["Prioridade"] = relationship(
        "Prioridade", backref="chamados", foreign_keys=[priority_id]
    )
