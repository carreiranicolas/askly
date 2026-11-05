import logging
import re

from email_validator import EmailNotValidError, validate_email

from app.extensions import db
from app.models.category import Categoria
from app.models.role import Cargo
from app.models.user import Usuario

from . import ROLE_ADMIN, ROLE_SOLICITANTE
from .exceptions import AuthError, ConflictError, ValidationError

logger = logging.getLogger(__name__)

PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$")


def _validate_password(password):
    """Valida força da senha: mínimo 8 caracteres, maiúscula, minúscula e número."""
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise ValidationError(f"A senha deve ter ao menos {PASSWORD_MIN_LENGTH} caracteres.")
    if not PASSWORD_PATTERN.match(password):
        raise ValidationError(
            "A senha deve conter pelo menos uma letra maiúscula, "
            "uma letra minúscula e um número."
        )


def _ensure_user_area_active(user):
    """Bloqueia login de não-admins vinculados a uma área desativada."""
    if user.cargo is not None and user.cargo.name == ROLE_ADMIN:
        return
    if user.area_id is None:
        return
    area = db.session.get(Categoria, user.area_id)
    if area is not None and not area.is_active:
        raise AuthError("Sua área está desativada. Procure um administrador.")


def _default_role_id():
    """Cargo do cadastro público: Solicitante.

    Quem se cadastra abre e acompanha os próprios chamados. A promoção a
    Admin é feita por um administrador no painel `/admin/usuarios`.
    """
    cargo = Cargo.query.filter_by(name=ROLE_SOLICITANTE).first()
    if cargo is None:
        raise ValidationError("Cargo padrão indisponível. Rode o seed para popular os cargos.")
    return cargo.id


def _validate_registration(name, email, password):
    if not name or len(name.strip()) < 2:
        raise ValidationError("Nome deve ter ao menos 2 caracteres.")
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        raise ValidationError("E-mail inválido.")
    _validate_password(password)


def authenticate(email, password):
    user = Usuario.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        logger.warning("Tentativa de login falha para email: %s", email)
        raise AuthError("E-mail ou senha incorretos.")
    if not user.is_active:
        logger.warning("Tentativa de login em conta desativada: %s (user_id=%s)", email, user.id)
        raise AuthError("Sua conta está desativada. Procure um administrador.")
    _ensure_user_area_active(user)
    logger.info("Login bem-sucedido: %s (user_id=%s)", email, user.id)
    return user


def register(name, email, password, role_id=None, area_id=None):
    _validate_registration(name, email, password)
    if Usuario.query.filter_by(email=email).first():
        raise ConflictError("Este e-mail já está cadastrado no sistema.")
    if role_id is None:
        role_id = _default_role_id()
    elif db.session.get(Cargo, role_id) is None:
        raise ValidationError("Cargo informado não existe.")
    if area_id is not None and db.session.get(Categoria, area_id) is None:
        raise ValidationError("Área informada não existe.")

    user = Usuario(name=name, email=email, role_id=role_id, area_id=area_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def change_password(user, current_password, new_password):
    if not user.check_password(current_password):
        raise AuthError("Senha atual incorreta.")
    _validate_password(new_password)
    user.set_password(new_password)
    db.session.commit()
    return user
