# Askly (MVP) — Gestão de Chamados Internos

Plataforma web para **gestão de chamados internos** (MVP), construída em **Flask 3.x + PostgreSQL (Docker)**, com **RBAC** (Solicitante/Admin), **auditoria de status** e **UI em Bulma**.

## Sumário

- [Stack](#stack)
- [Arquitetura (Clean Architecture)](#arquitetura-clean-architecture)
- [Setup rápido](#setup-rápido)
- [Comandos úteis](#comandos-úteis)
- [Swagger / OpenAPI](#swagger--openapi)
- [Segurança (onde está cada proteção)](#segurança-onde-está-cada-proteção)
  - [CSRF (Web)](#csrf-web)
  - [XSS / CSP / Security Headers](#xss--csp--security-headers)
  - [Tokenização (JWT) na API](#tokenização-jwt-na-api)
  - [Hash de senha](#hash-de-senha)
  - [RBAC (Solicitante / Admin)](#rbac-solicitante--admin)
  - [Rate limiting](#rate-limiting)
- [Auditoria obrigatória de mudança de status](#auditoria-obrigatória-de-mudança-de-status)
- [Testes](#testes)

## Stack

- **Backend**: Flask 3.x
- **DB**: PostgreSQL (Docker)
- **ORM/Migrations**: SQLAlchemy + Flask-Migrate (Alembic)
- **Auth (Web)**: Flask-Login (sessão/cookies)
- **Auth (API)**: JWT Bearer token (tokenização)
- **Docs API**: `flask-restx` (Swagger UI)
- **UI**: Jinja2 + Bulma

## Arquitetura

Web (Jinja) e API REST compartilham a mesma **camada de serviço** — as regras
de negócio (RBAC, validações, auditoria de status) ficam num lugar só.

```
app/
  extensions.py      # singletons: db, csrf, login_manager, migrate
  cli.py             # comando flask seed
  models/            # ORM (SQLAlchemy)
  forms/             # WTForms (web)
  routes/            # web (server-rendered): main(auth), tickets, admin
  services/          # regras de negócio compartilhadas (web + API)
  api/               # REST API (flask-restx): security(JWT) + namespaces/
```

## Setup rápido

### 1) Variáveis de ambiente

```bash
cp .env.example .env
# defina SECRET_KEY, ASKLY_ADMIN_PASSWORD e ASKLY_USER_PASSWORD
# ajuste POSTGRES_PORT/credenciais conforme o seu docker-compose
```

### 2) Banco de dados (PostgreSQL via Docker)

```bash
docker compose up -d db
```

### 3) Ambiente Python

```bash
python -m venv venv
source venv/bin/activate #Linux/Mac
pip install .
```

O `.flaskenv` já define `FLASK_APP=app` e `FLASK_DEBUG=1`, então não é
preciso exportar variáveis na mão.

### 4) Rodar

```bash
flask run
```

Ao subir o servidor, as migrations pendentes são aplicadas automaticamente
no Postgres (`flask db upgrade`), criando o banco com todas as tabelas.

### 5) Dados base e contas iniciais

```bash
flask seed
```

Cria os cargos, áreas, prioridades e as contas configuradas por
`ASKLY_ADMIN_EMAIL`/`ASKLY_ADMIN_PASSWORD` e
`ASKLY_USER_EMAIL`/`ASKLY_USER_PASSWORD`. É idempotente. No Docker, o
`entrypoint` executa esse comando automaticamente.

## API REST

- Base: `/api/v1` — **Swagger UI** em `http://127.0.0.1:5000/api/v1/docs`.
- Autenticação **JWT Bearer**: `POST /api/v1/auth/login` (ou `/auth/register`)
  devolve `access_token`; envie `Authorization: Bearer <token>` nas demais rotas.
- Namespaces: `auth`, `usuarios`, `cargos`, `categorias`, `prioridades`,
  `chamados` (com `/status`, `/comentarios`, `/historico` e `DELETE` para cancelar).
- Escrita em catálogos (cargos/categorias/prioridades) e gestão de usuários
  exigem perfil **Admin** (RBAC por decorator).

## Comandos úteis

- **Criar migração**: `flask db migrate -m "..."` (o `flask run` aplica no próximo boot, ou rode `flask db upgrade`)
- **Seed**: `flask seed`
- **Rodar testes**: `pytest`

## Testes

Suíte em `tests/` (usa o banco `askly_test_db`), cobrindo autenticação da API,
RBAC, fluxo de chamados com auditoria de status e o fluxo web de auth:

```bash
pytest
```
