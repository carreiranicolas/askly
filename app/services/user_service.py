from app.extensions import db
from app.models.category import Categoria
from app.models.role import Cargo
from app.models.user import Usuario

from . import ROLE_ADMIN, ROLE_SOLICITANTE, STAFF_ROLES
from .exceptions import NotFoundError, ValidationError


def list_users():
    return Usuario.query.order_by(Usuario.name).all()


def list_staff():
    return (
        Usuario.query.join(Cargo).filter(Cargo.name.in_(STAFF_ROLES)).order_by(Usuario.name).all()
    )


def list_staff_for_area(area_id):
    """Usuários ativos da área — alvos válidos de atribuição de chamados."""
    if area_id is None:
        return []
    return (
        Usuario.query.filter(
            Usuario.area_id == area_id,
            Usuario.is_active.is_(True),
        )
        .order_by(Usuario.name)
        .all()
    )


def get_user(user_id):
    user = db.session.get(Usuario, user_id)
    if user is None:
        raise NotFoundError("Usuário não encontrado.")
    return user


def update_user(user_id, name=None, role_id=None, area_id=None, is_active=None):
    user = get_user(user_id)
    if name is not None:
        user.name = name
    if role_id is not None:
        cargo = db.session.get(Cargo, role_id)
        if cargo is None:
            raise ValidationError("Cargo informado não existe.")
        if cargo.name not in (ROLE_SOLICITANTE, ROLE_ADMIN):
            raise ValidationError("Selecione Solicitante ou Admin.")
        if user.cargo.name == ROLE_ADMIN and cargo.name != ROLE_ADMIN:
            admins = (
                Usuario.query.join(Cargo)
                .filter(Cargo.name == ROLE_ADMIN, Usuario.is_active.is_(True))
                .count()
            )
            if admins <= 1:
                raise ValidationError("O último administrador não pode ser rebaixado.")
        user.role_id = role_id
    if area_id is not None:
        if db.session.get(Categoria, area_id) is None:
            raise ValidationError("Área informada não existe.")
        user.area_id = area_id
    if is_active is not None:
        user.is_active = is_active
    db.session.commit()
    return user


def toggle_user_active(actor, user_id):
    """Ativa ou desativa a conta de um usuário (admin não pode desativar a si)."""
    if actor.id == user_id:
        raise ValidationError("Você não pode desativar a própria conta.")
    user = get_user(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    return user
