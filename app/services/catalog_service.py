from app.extensions import db
from app.models.category import Categoria
from app.models.priority import Prioridade
from app.models.role import Cargo

from .exceptions import ConflictError, NotFoundError


# ----------------------------- Cargos -----------------------------
def list_cargos():
    return Cargo.query.order_by(Cargo.name).all()


def get_cargo(cargo_id):
    obj = db.session.get(Cargo, cargo_id)
    if obj is None:
        raise NotFoundError("Cargo não encontrado.")
    return obj


def create_cargo(name, description, is_active=True):
    if Cargo.query.filter_by(name=name).first():
        raise ConflictError("Já existe um cargo com esse nome.")
    obj = Cargo(name=name, description=description, is_active=is_active)
    db.session.add(obj)
    db.session.commit()
    return obj


def update_cargo(cargo_id, name=None, description=None, is_active=None):
    obj = get_cargo(cargo_id)
    if name is not None:
        obj.name = name
    if description is not None:
        obj.description = description
    if is_active is not None:
        obj.is_active = is_active
    db.session.commit()
    return obj


def delete_cargo(cargo_id):
    obj = get_cargo(cargo_id)
    db.session.delete(obj)
    db.session.commit()


# --------------------------- Categorias ---------------------------
def list_categorias(only_active=False):
    """Lista áreas. Use ``only_active=True`` para uso operacional (abrir
    chamado, atribuir responsável); o admin precisa enxergar todas para
    poder reativar inativas."""
    query = Categoria.query
    if only_active:
        query = query.filter_by(is_active=True)
    return query.order_by(Categoria.name).all()


def get_categoria(categoria_id):
    obj = db.session.get(Categoria, categoria_id)
    if obj is None:
        raise NotFoundError("Categoria não encontrada.")
    return obj


def create_categoria(name, description, is_active=True):
    if Categoria.query.filter_by(name=name).first():
        raise ConflictError("Já existe uma categoria com esse nome.")
    obj = Categoria(name=name, description=description, is_active=is_active)
    db.session.add(obj)
    db.session.commit()
    return obj


def update_categoria(categoria_id, name=None, description=None, is_active=None):
    obj = get_categoria(categoria_id)
    if name is not None:
        obj.name = name
    if description is not None:
        obj.description = description
    if is_active is not None:
        obj.is_active = is_active
    db.session.commit()
    return obj


def delete_categoria(categoria_id):
    """Desativa a categoria (soft delete).

    Categorias têm FK em chamados e usuários, então o hard delete quebraria
    histórico. A desativação garante que ela some das telas operacionais
    (abrir chamado, atribuir responsável) sem perder o rastro nos registros
    antigos.
    """
    obj = get_categoria(categoria_id)
    if obj.is_active:
        obj.is_active = False
        db.session.commit()
    return obj


# --------------------------- Prioridades --------------------------
def list_prioridades(only_active=False):
    """Lista prioridades. Use ``only_active=True`` para uso operacional."""
    query = Prioridade.query
    if only_active:
        query = query.filter_by(is_active=True)
    return query.order_by(Prioridade.sla_hours).all()


def get_prioridade(prioridade_id):
    obj = db.session.get(Prioridade, prioridade_id)
    if obj is None:
        raise NotFoundError("Prioridade não encontrada.")
    return obj


def create_prioridade(name, description, sla_hours, is_active=True):
    if Prioridade.query.filter_by(name=name).first():
        raise ConflictError("Já existe uma prioridade com esse nome.")
    obj = Prioridade(name=name, description=description, sla_hours=sla_hours, is_active=is_active)
    db.session.add(obj)
    db.session.commit()
    return obj


def update_prioridade(prioridade_id, name=None, description=None, sla_hours=None, is_active=None):
    obj = get_prioridade(prioridade_id)
    if name is not None:
        obj.name = name
    if description is not None:
        obj.description = description
    if sla_hours is not None:
        obj.sla_hours = sla_hours
    if is_active is not None:
        obj.is_active = is_active
    db.session.commit()
    return obj


def delete_prioridade(prioridade_id):
    """Desativa a prioridade (soft delete).

    Análogo a ``delete_categoria``: prioridades têm FK em chamados e o hard
    delete quebraria histórico/SLA.
    """
    obj = get_prioridade(prioridade_id)
    if obj.is_active:
        obj.is_active = False
        db.session.commit()
    return obj
