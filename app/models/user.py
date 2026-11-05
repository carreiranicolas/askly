from datetime import datetime
from typing import TYPE_CHECKING, Optional

from flask_login import UserMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

if TYPE_CHECKING:
    from .category import Categoria
    from .role import Cargo


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    __table_args__ = (
        db.Index("ix_usuarios_role_area", "role_id", "area_id"),
        db.Index("ix_usuarios_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(db.String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("cargos.id"), nullable=False)
    area_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("categorias.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.now)

    cargo: Mapped["Cargo"] = relationship(
        "Cargo",
        foreign_keys=[role_id],
    )
    area: Mapped[Optional["Categoria"]] = relationship(
        "Categoria",
        foreign_keys=[area_id],
    )

    def set_password(self, password_puro: str) -> None:
        """Criptografa a senha text-pleno e salva no campo password."""
        self.password = generate_password_hash(password_puro)

    def check_password(self, password_puro: str) -> bool:
        """Valida se a senha digitada bate com o hash do banco."""
        return check_password_hash(self.password, password_puro)
