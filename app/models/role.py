from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Cargo(db.Model):
    __tablename__ = "cargos"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    name: Mapped[str] = mapped_column(db.String(60), nullable=False)
    description: Mapped[str] = mapped_column(db.Text)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
