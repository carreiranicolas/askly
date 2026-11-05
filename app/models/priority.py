from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Prioridade(db.Model):
    __tablename__ = "prioridades"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    name: Mapped[str] = mapped_column(db.String(25), nullable=False)
    description: Mapped[str] = mapped_column(db.Text)
    sla_hours: Mapped[int] = mapped_column(db.Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
