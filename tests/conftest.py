"""Configuração compartilhada do pytest (fixtures).

Este arquivo é carregado automaticamente pelo pytest antes dos testes. Tudo
o que é definido aqui como `@pytest.fixture` fica disponível, por nome, em
qualquer teste do diretório `tests/`.

A estratégia de banco é:
  - sobe UMA vez o schema completo (`create_all`) por sessão de teste (caro);
  - antes de CADA teste, faz um reset completo dos dados e re-semeia o
    "catálogo" (cargos, áreas, prioridades). Recriar só os dados (e não o
    schema) a cada teste dá isolamento total a baixo custo: nenhum teste vê
    resíduo de outro, mesmo os que criam/desativam itens de catálogo.
"""

import os

# IMPORTANTE: estas variáveis precisam estar definidas ANTES de importar a app,
# porque `create_app()` lê o ambiente no momento do import/instanciação.
# `setdefault` => não sobrescreve o que o CI já tiver exportado (ver ci.yml).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://askly:askly_dev_password@localhost:5435/askly_test_db",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest

from app import create_app
from app.extensions import db as _db
from app.extensions import limiter as _limiter
from app.models.category import Categoria
from app.models.commentary import Comentario
from app.models.history import HistoricoStatus
from app.models.priority import Prioridade
from app.models.role import Cargo
from app.models.ticket import Chamado
from app.models.user import Usuario
from app.services import auth_service


def _seed_catalog():
    """Insere os dados de catálogo que os testes assumem existir.

    São os mesmos cargos/áreas/prioridades que o comando `flask seed` cria em
    produção, mas em versão mínima. Ficam fixos durante toda a sessão de teste.
    """
    _db.session.add_all(
        [
            # Os três cargos do RBAC (Solicitante < Atendente < Admin).
            Cargo(name="Solicitante", description="x", is_active=True),
            Cargo(name="Atendente", description="x", is_active=True),
            Cargo(name="Admin", description="x", is_active=True),
            # Duas áreas para exercitar o isolamento por área (RBAC de atendente).
            Categoria(name="RH", description="x", is_active=True),
            Categoria(name="Infraestrutura", description="x", is_active=True),
            # Uma prioridade com SLA de 8h (usada nos testes de SLA).
            Prioridade(name="Alta", description="x", sla_hours=8, is_active=True),
        ]
    )
    _db.session.commit()


@pytest.fixture(scope="session")
def app():
    """Instância única da aplicação Flask para toda a sessão de teste.

    `scope="session"` => criada uma só vez (cara: cria a app e o schema).
    Liga o modo TESTING e desliga CSRF e rate limiting, que só atrapalhariam
    os testes (CSRF exigiria token em cada POST; o rate limit poderia barrar
    testes que fazem muitos logins seguidos).
    """
    flask_app = create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    # Desliga o rate limiter de fato. Só setar RATELIMIT_ENABLED no config NÃO
    # basta: o Flask-Limiter lê esse valor durante `init_app()` (já executado
    # dentro de create_app), então precisamos mexer no atributo `.enabled`.
    # Sem isso, o limite de "10 logins por minuto" estoura (429) quando vários
    # testes fazem login em sequência.
    _limiter.enabled = False
    # Cria o schema do zero dentro do contexto da app (o catálogo é semeado por
    # teste no fixture `_clean_dynamic`, garantindo isolamento total).
    with flask_app.app_context():
        _db.drop_all()
        _db.create_all()
    yield flask_app
    # Teardown da sessão: fecha a sessão do SQLAlchemy e derruba o schema.
    with flask_app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def _clean_dynamic(app):
    """Reseta o banco para um estado conhecido antes de CADA teste.

    `autouse=True` => roda automaticamente em TODO teste, sem precisar pedir.

    Fazemos um reset COMPLETO (inclusive catálogo) e re-semeamos. Isso garante
    isolamento total: testes que criam/desativam cargos, áreas ou prioridades
    (ex.: `test_catalog_service.py`) não vazam estado para os demais — caso
    contrário, uma área desativada por um teste quebraria o `catalog` fixture
    de outro.

    A ordem de deleção respeita as FKs: primeiro os dependentes
    (histórico/comentário/chamado), depois usuários, e por fim o catálogo
    (prioridade/categoria/cargo), do qual usuários e chamados dependem.
    """
    with app.app_context():
        for model in (
            HistoricoStatus,
            Comentario,
            Chamado,
            Usuario,
            Prioridade,
            Categoria,
            Cargo,
        ):
            _db.session.query(model).delete()
        _db.session.commit()
        _seed_catalog()
    yield


@pytest.fixture
def client(app):
    """Cliente de teste HTTP do Flask (faz requests sem subir servidor real).

    O mesmo cliente preserva cookies entre chamadas, então depois de um
    POST /login ele continua autenticado nos GETs seguintes (sessão web).
    """
    return app.test_client()


@pytest.fixture
def cargo_ids(app):
    """Mapa nome-do-cargo -> id, para criar usuários com o cargo certo."""
    with app.app_context():
        return {c.name: c.id for c in Cargo.query.all()}


@pytest.fixture
def catalog(app):
    """IDs prontos de uma categoria e uma prioridade (atalho para abrir chamado).

    Pega a 1ª categoria em ordem alfabética ("Infraestrutura") e a 1ª
    prioridade — suficiente para a maioria dos testes que só precisam de um
    par válido categoria/prioridade.
    """
    with app.app_context():
        return {
            "categoria": Categoria.query.order_by(Categoria.name).first().id,
            "prioridade": Prioridade.query.first().id,
        }


@pytest.fixture
def areas(app):
    """Mapa nome-da-área -> id, para testar isolamento entre áreas (RH x Infra)."""
    with app.app_context():
        return {c.name: c.id for c in Categoria.query.all()}


@pytest.fixture
def make_user(app, cargo_ids):
    """Fábrica de usuários: chama `_make(...)` dentro do teste para criar um.

    Retorna uma FUNÇÃO (factory pattern) para que o teste crie quantos
    usuários quiser, com cargo/área/email à escolha. Devolve `(email, senha)`
    já prontos para autenticar via `api_login`/`web_login`.
    """

    def _make(role="Solicitante", email=None, password="Senha123", name="Teste", area=None):
        email = email or f"{role.lower()}@test.com"
        with app.app_context():
            # Converte o nome da área no id correspondente (ou None se não passou).
            area_id = Categoria.query.filter_by(name=area).first().id if area else None
            # register() faz hash da senha e persiste o usuário.
            auth_service.register(name, email, password, cargo_ids[role], area_id=area_id)
        return email, password

    return _make


@pytest.fixture
def api_login(client):
    """Helper de autenticação na API REST (JWT).

    Faz POST /api/v1/auth/login e devolve o header `Authorization: Bearer
    <token>` pronto para ser passado nas próximas chamadas de API.
    """

    def _login(email, password="Senha123"):
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = resp.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login


@pytest.fixture
def web_login(client):
    """Helper de autenticação na interface WEB (sessão por cookie).

    Diferente da API (que usa JWT no header), o front web usa Flask-Login com
    cookie de sessão. Como o `client` guarda os cookies, basta fazer o POST
    /login uma vez e os requests seguintes do mesmo client já vão autenticados.
    Retorna a própria resposta do login para quem quiser inspecionar o status.
    """

    def _login(email, password="Senha123"):
        return client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )

    return _login
