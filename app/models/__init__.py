from app.extensions import db

from .category import Categoria
from .commentary import Comentario
from .history import HistoricoStatus
from .priority import Prioridade
from .role import Cargo
from .ticket import Chamado
from .user import Usuario

__all__ = [
    "db",
    "Usuario",
    "Cargo",
    "Categoria",
    "Chamado",
    "Prioridade",
    "Comentario",
    "HistoricoStatus",
]
