# Comandos — Askly

Referência rápida de **todos os comandos** do projeto: setup, banco de dados,
execução, testes, qualidade de código e Docker.

> Pré-requisitos: **Python 3.11+** e **Docker + Docker Compose**.
> Em quase todos os comandos abaixo assume-se o **virtualenv ativo**
> (`source .venv/bin/activate`) e o **`.env` configurado** (veja a seção
> [Variáveis de ambiente](#variáveis-de-ambiente)).

---

## Índice

- [Setup inicial](#setup-inicial)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Banco de dados (Docker)](#banco-de-dados-docker)
- [Migrations (Alembic / Flask-Migrate)](#migrations-alembic--flask-migrate)
- [Seed (dados base)](#seed-dados-base)
- [Rodar a aplicação](#rodar-a-aplicação)
- [Testes e cobertura](#testes-e-cobertura)
- [Qualidade de código (lint / format)](#qualidade-de-código-lint--format)
- [Docker (tudo containerizado)](#docker-tudo-containerizado)
- [URLs úteis](#urls-úteis)

---

## Setup inicial

```bash
# 1) Criar e ativar o virtualenv
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2) Instalar dependências
pip install ".[dev,test]"            # app + ferramentas de dev e testes
pip install "."                      # só a aplicação (produção)
pip install ".[test]"               # app + dependências de teste

# 3) (opcional) instalar os hooks de pre-commit
pre-commit install
```

---

## Variáveis de ambiente

```bash
# Copiar o template e gerar uma SECRET_KEY forte (>= 32 bytes)
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # cole no .env
```

| Variável | Para que serve | Padrão |
|----------|----------------|--------|
| `SECRET_KEY` | Assina sessões e tokens JWT. **Obrigatória** fora do modo debug | — |
| `FLASK_DEBUG` | `1` liga o modo debug/reloader | `1` (no `.flaskenv`) |
| `DATABASE_URL` | URL completa do Postgres (sobrescreve as `POSTGRES_*`) | — |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Credenciais do banco | `askly` / `askly_dev_password` / `askly_db` |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Host/porta do banco | `localhost` / `5432` |
| `APP_TIMEZONE` | Fuso para exibir datas (armazenadas em UTC) | `America/Sao_Paulo` |
| `RATELIMIT_STORAGE_URI` | Storage do rate limiter (use Redis em produção) | `memory://` |
| `SESSION_COOKIE_SECURE` / `FORCE_HTTPS` | `1` para endurecer cookies/HSTS sob HTTPS | `0` |
| `LOG_LEVEL` | Nível de log (`INFO`, `DEBUG`, ...) | `INFO` |
| `GUNICORN_WORKERS` | Nº de workers do gunicorn (Docker) | `3` |

---

## Banco de dados (Docker)

```bash
# Subir SÓ o banco (cenário de desenvolvimento local)
docker compose up -d db

# Criar o banco de TESTE (uma vez; os testes usam um banco separado)
docker exec askly_postgres psql -U askly -d askly_db \
  -c "CREATE DATABASE askly_test_db;"

# Abrir um psql no banco
docker exec -it askly_postgres psql -U askly -d askly_db

# Parar o banco (mantém os dados no volume)
docker compose stop db

# Derrubar tudo e APAGAR os dados (volume)
docker compose down -v
```

> Os testes esperam um Postgres em `localhost:5435` (porta exposta pelo
> container `askly_postgres`) no banco `askly_test_db`. Veja a seção de testes.

---

## Migrations (Alembic / Flask-Migrate)

```bash
flask db upgrade                     # aplica as migrations pendentes
flask db migrate -m "descrição"      # gera uma nova migration a partir dos models
flask db downgrade                   # reverte a última migration
flask db current                     # mostra a revisão atual do banco
flask db history                     # lista o histórico de migrations
flask db heads                       # mostra a(s) revisão(ões) de topo
flask db stamp head                  # marca o banco como atualizado sem rodar
```

> No modo dev (`flask run` / `python run.py`) as migrations são aplicadas
> automaticamente no boot. No Docker, o `entrypoint.sh` roda `flask db upgrade`
> antes de iniciar o gunicorn.

---

## Seed (dados base)

```bash
flask seed                           # popula cargos, áreas, prioridades e contas iniciais
```

Cria os cargos **Solicitante / Admin**, as áreas (RH, Financeiro,
Comercial, Jurídico, Desenvolvimento, Infraestrutura) e as prioridades
(Baixa, Média, Alta, Crítica) e as contas definidas pelas variáveis
`ASKLY_ADMIN_EMAIL`, `ASKLY_ADMIN_PASSWORD`, `ASKLY_USER_EMAIL` e
`ASKLY_USER_PASSWORD`. Rodar de novo não duplica nada.

> No cadastro público (`/cadastro`) **não se escolhe cargo**: todo novo usuário
> entra como **Solicitante**. A promoção a Admin é feita pelo painel
> `/admin/usuarios`.

---

## Rodar a aplicação

```bash
# Desenvolvimento (reloader + debug; aplica migrations no boot)
flask run                            # http://127.0.0.1:5000
python run.py                        # equivalente, via script

# Escolher host/porta
flask run --host 0.0.0.0 --port 5000

# Produção (servidor WSGI) — é o que o Docker usa
gunicorn --workers 3 --bind 0.0.0.0:8000 run:app

# Shell interativo com o contexto da app (db, models já no escopo)
flask shell
```

---

## Testes e cobertura

```bash
pytest                               # roda toda a suíte (já mede cobertura)
pytest -q                            # saída compacta
pytest tests/test_tickets.py         # só um arquivo
pytest tests/test_tickets.py::test_create_ticket_starts_aberto   # só um teste
pytest -k "sla or overdue"           # filtra por nome
pytest -x                            # para no primeiro erro
pytest -vv                           # bem verboso (mostra diffs completos)

# Relatório de cobertura em HTML (abre htmlcov/index.html)
pytest --cov-report=html
```

> A cobertura e o **gate** (`--cov-fail-under=80`) já estão no `pyproject.toml`,
> então um simples `pytest` falha se a cobertura cair abaixo de 80%.
>
> Se a cobertura aparecer estranhamente baixa (modelos em ~50%), é cache
> obsoleto — limpe e rode de novo:
> ```bash
> rm -f .coverage; rm -rf .pytest_cache
> find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
> ```

---

## Qualidade de código (lint / format)

```bash
# Formatar (aplica as mudanças)
black .                              # formata o código (linha 100)
isort .                             # ordena os imports

# Verificar sem alterar (é o que o CI faz — bloqueante)
black --check .
isort --check-only .
flake8 .                            # lint (config em .flake8, alinhada ao black)
mypy app                            # checagem de tipos estática

# Rodar todos os hooks de pre-commit manualmente
pre-commit run --all-files
```

---

## Docker (tudo containerizado)

```bash
# Build + subir banco E aplicação (gunicorn). O entrypoint aplica migrations.
docker compose up -d --build         # http://localhost:8000

# Popular dados base dentro do container
docker compose exec app flask seed

# Acompanhar logs da aplicação
docker compose logs -f app

# Abrir um shell no container da app
docker compose exec app sh

# Rodar um comando flask qualquer no container
docker compose exec app flask db upgrade

# Parar / derrubar
docker compose down                  # para os containers (mantém o volume)
docker compose down -v               # para e APAGA os dados do banco
```

---

## URLs úteis

| Recurso | Local (`flask run`) | Docker (`compose`) |
|---------|---------------------|--------------------|
| Aplicação | http://127.0.0.1:5000 | http://localhost:8000 |
| Cadastro | `/cadastro` | `/cadastro` |
| Swagger / OpenAPI | `/api/v1/docs` | `/api/v1/docs` |
| Healthcheck | `/health` | `/health` |
