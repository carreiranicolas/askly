"""Testes da camada de catálogo (`app/services/catalog_service.py`).

O catálogo é o CRUD das entidades de apoio: Cargos, Categorias (áreas) e
Prioridades. Aqui validamos diretamente a camada de serviço (sem passar pela
API/HTTP), garantindo as regras de negócio:
  - criação com nome único (conflito gera ConflictError);
  - busca de inexistente gera NotFoundError;
  - atualização parcial (só altera o que foi informado);
  - "delete" de categoria/prioridade é SOFT (apenas desativa), porque elas têm
    FK em chamados e o hard delete quebraria o histórico.

Como o serviço fala direto com o banco via SQLAlchemy, cada teste roda dentro
de um `app.app_context()` para ter a sessão do banco ativa.
"""

import pytest

from app.services import catalog_service
from app.services.exceptions import ConflictError, NotFoundError


# ------------------------------- Cargos -------------------------------
def test_create_cargo_persiste_e_lista(app):
    """Criar um cargo deve persisti-lo e fazê-lo aparecer na listagem."""
    with app.app_context():
        novo = catalog_service.create_cargo("Supervisor", "Coordena a equipe")
        assert novo.id is not None
        nomes = [c.name for c in catalog_service.list_cargos()]
        assert "Supervisor" in nomes


def test_create_cargo_nome_duplicado_gera_conflito(app):
    """Nome de cargo é único: recriar "Admin" (já existe no seed) deve falhar."""
    with app.app_context():
        with pytest.raises(ConflictError):
            catalog_service.create_cargo("Admin", "duplicado")


def test_get_cargo_inexistente_gera_not_found(app):
    """Buscar um id que não existe deve levantar NotFoundError."""
    with app.app_context():
        with pytest.raises(NotFoundError):
            catalog_service.get_cargo(999999)


def test_update_cargo_altera_apenas_campos_informados(app):
    """Update parcial: passar só `description` não deve mexer no `name`."""
    with app.app_context():
        cargo = catalog_service.create_cargo("Auditor", "desc antiga")
        atualizado = catalog_service.update_cargo(cargo.id, description="desc nova")
        assert atualizado.name == "Auditor"  # nome preservado
        assert atualizado.description == "desc nova"


# ----------------------------- Categorias -----------------------------
def test_list_categorias_only_active_filtra_inativas(app):
    """`only_active=True` (uso operacional) não deve trazer áreas desativadas."""
    with app.app_context():
        criada = catalog_service.create_categoria("Marketing", "x")
        catalog_service.delete_categoria(criada.id)  # soft delete => is_active=False

        ativas = [c.name for c in catalog_service.list_categorias(only_active=True)]
        todas = [c.name for c in catalog_service.list_categorias()]
        assert "Marketing" not in ativas  # some das telas operacionais
        assert "Marketing" in todas  # mas o admin ainda enxerga para reativar


def test_delete_categoria_e_soft_delete(app):
    """ "Excluir" uma categoria apenas a desativa (preserva FK/histórico)."""
    with app.app_context():
        criada = catalog_service.create_categoria("Compras", "x")
        catalog_service.delete_categoria(criada.id)
        # O registro continua existindo, só que inativo.
        ainda_existe = catalog_service.get_categoria(criada.id)
        assert ainda_existe.is_active is False


def test_create_categoria_nome_duplicado_gera_conflito(app):
    """Nome de área é único: recriar "RH" (do seed) deve falhar."""
    with app.app_context():
        with pytest.raises(ConflictError):
            catalog_service.create_categoria("RH", "duplicada")


# ---------------------------- Prioridades ----------------------------
def test_list_prioridades_ordena_por_sla(app):
    """Prioridades são listadas por SLA crescente (mais urgente => menor SLA)."""
    with app.app_context():
        # "Alta" do seed tem sla_hours=8. Criamos uma com SLA menor e outra maior.
        catalog_service.create_prioridade("Crítica", "x", sla_hours=2)
        catalog_service.create_prioridade("Baixa", "x", sla_hours=72)
        slas = [p.sla_hours for p in catalog_service.list_prioridades()]
        assert slas == sorted(slas)  # ordem crescente garantida pelo serviço


def test_update_prioridade_altera_sla(app):
    """Atualizar o SLA de uma prioridade deve refletir no objeto retornado."""
    with app.app_context():
        p = catalog_service.create_prioridade("Urgente", "x", sla_hours=4)
        atualizada = catalog_service.update_prioridade(p.id, sla_hours=1)
        assert atualizada.sla_hours == 1


def test_delete_prioridade_e_soft_delete(app):
    """Assim como categorias, "excluir" prioridade só desativa (FK em chamados)."""
    with app.app_context():
        p = catalog_service.create_prioridade("Temporária", "x", sla_hours=12)
        catalog_service.delete_prioridade(p.id)
        assert catalog_service.get_prioridade(p.id).is_active is False
