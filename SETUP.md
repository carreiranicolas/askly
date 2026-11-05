# Como rodar o Askly localmente

Guia rápido para subir a aplicação na sua máquina. Há dois caminhos: **local
(dev)** e **tudo via Docker**.

## Pré-requisitos

- **Docker** + **Docker Compose** (para o banco PostgreSQL).
- **Python 3.11+** (apenas para o caminho local/dev).

---

## Opção A — Local (recomendado para desenvolver)

O banco roda em container; a aplicação roda no seu host com `flask run`.

```bash
# 1) Subir só o banco
docker compose up -d db

# 2) Ambiente Python
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install ".[dev,test]"

# 3) Variáveis de ambiente
cp .env.example .env
# Gere uma SECRET_KEY e cole no .env:
python -c "import secrets; print(secrets.token_hex(32))"
# Defina também ASKLY_ADMIN_PASSWORD e ASKLY_USER_PASSWORD no .env.
# Se a porta 5432 estiver ocupada, ajuste POSTGRES_PORT no .env.

# 4) Subir a aplicação (aplica as migrations automaticamente no boot)
flask run

# 5) Em outro terminal (venv ativo): popular dados e duas contas iniciais
flask seed
```

Acesse **http://127.0.0.1:5000** com uma das contas definidas no `.env`.
Documentação da API (Swagger): **http://127.0.0.1:5000/api/v1/docs**.

---

## Opção B — Tudo via Docker (mais próximo de produção)

Sobe o banco **e** a aplicação (gunicorn). O `entrypoint` aplica as migrations.

```bash
# 1) Variáveis de ambiente — SECRET_KEY é OBRIGATÓRIA aqui (FLASK_DEBUG=0)
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # cole no .env
# Preencha ASKLY_ADMIN_PASSWORD e ASKLY_USER_PASSWORD no .env antes de subir.

# 2) Build + subir db e app
docker compose up -d --build

# O entrypoint aplica as migrations e cria os dados e contas iniciais.
```

Acesse **http://localhost:8000**. Healthcheck em `/health`.

---

## Comandos úteis

| Ação | Comando |
|------|---------|
| Rodar testes | `pytest` |
| Nova migration | `flask db migrate -m "..."` (aplica no próximo `flask run`) |
| Aplicar migrations | `flask db upgrade` |
| Popular dados base | `flask seed` |
| Logs do app (Docker) | `docker compose logs -f app` |

## Perfis (RBAC)

Após o `seed`, existem os cargos **Solicitante** e **Admin**, e as áreas RH,
Financeiro, Comercial, Jurídico, Desenvolvimento e Infraestrutura. O cadastro
público cria Solicitantes. Eles veem apenas os próprios chamados; o Admin vê
todos e pode alterar o status. Instalações antigas podem manter o cargo legado
Atendente, que passa a ter as permissões de usuário comum.
