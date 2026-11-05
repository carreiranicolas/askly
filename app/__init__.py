import logging
import os
import sys
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_migrate import upgrade
from sqlalchemy import text

from .extensions import csrf, db, limiter, login_manager, migrate, talisman

load_dotenv()

# CSP pragmática: 'unsafe-inline' é necessário hoje pelos estilos/scripts inline
# (tema sem flash, toggles) e pelos CDNs (Bulma, Google Fonts, Swagger UI).
CONTENT_SECURITY_POLICY = {
    "default-src": "'self'",
    "script-src": "'self' 'unsafe-inline' https://unpkg.com",
    "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net "
    "https://fonts.googleapis.com https://unpkg.com",
    "font-src": "'self' https://fonts.gstatic.com data:",
    "img-src": "'self' data:",
}


def _database_uri():
    uri = os.environ.get("DATABASE_URL")
    if uri:
        return uri

    user = os.environ.get("POSTGRES_USER", "askly")
    password = os.environ.get("POSTGRES_PASSWORD", "askly_dev_password")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    name = os.environ.get("POSTGRES_DB", "askly_db")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def _is_debug():
    return os.environ.get("FLASK_DEBUG", "") in ("1", "true", "True")


def _resolve_secret_key():
    secret = os.environ.get("SECRET_KEY")
    if secret:
        return secret
    if _is_debug():
        return "dev-only-change-me"
    raise RuntimeError(
        "SECRET_KEY não definida. Configure no .env antes de subir fora do modo debug."
    )


def _running_dev_server():
    # Aplica as migrations só quando o servidor sobe (flask run / python run.py),
    # nunca durante comandos `flask db ...`, `flask seed` ou os testes.
    if "run" not in sys.argv and os.path.basename(sys.argv[0]) != "run.py":
        return False
    # Com o reloader ativo, evita rodar no processo monitor (só no worker).
    if _is_debug() and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return False
    return True


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = _resolve_secret_key()
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Cookies de sessão endurecidos. Secure fica ligado só quando servido via HTTPS
    # (em dev sobre http, Secure=True faria o navegador descartar o cookie).
    secure_cookies = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = secure_cookies
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_SECURE"] = secure_cookies

    # Expiração de sessão: sessões web expiram após 8h de inatividade.
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)

    # Headers de segurança + CSP (Talisman). force_https/HSTS só fora de dev.
    force_https = os.environ.get("FORCE_HTTPS", "0") == "1"
    talisman.init_app(
        app,
        force_https=force_https,
        strict_transport_security=force_https,
        session_cookie_secure=secure_cookies,
        content_security_policy=CONTENT_SECURITY_POLICY,
    )

    # Rate limiting (anti brute force). Use Redis em produção via RATELIMIT_STORAGE_URI.
    app.config.setdefault(
        "RATELIMIT_STORAGE_URI", os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    )
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    limiter.init_app(app)

    _configure_logging(app)

    login_manager.init_app(app)
    login_manager.login_view = "web_auth.login"
    login_manager.login_message = "Por favor, faça o login para acessar esta página."
    login_manager.login_message_category = "warning"

    from .models.user import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Usuario, int(user_id))
        except (TypeError, ValueError):
            return None

    from .routes.admin import web_admin_bp
    from .routes.dashboard import web_dashboard_bp
    from .routes.main import main_bp, web_auth_bp
    from .routes.profile import web_profile_bp
    from .routes.tickets import web_tickets_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(web_auth_bp)
    app.register_blueprint(web_tickets_bp)
    app.register_blueprint(web_admin_bp)
    app.register_blueprint(web_profile_bp)
    app.register_blueprint(web_dashboard_bp)

    # API REST (JWT) — isenta de CSRF por não usar cookies de sessão.
    from .api import api_bp

    app.register_blueprint(api_bp)
    csrf.exempt(api_bp)

    from .cli import register_commands

    register_commands(app)

    _register_context_processors(app)
    _register_error_handlers(app)

    @app.get("/health")
    def health():
        """Healthcheck para orquestradores (Docker/Compose/CI)."""
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception:
            app.logger.exception("Healthcheck falhou")
            return {"status": "error"}, 503

    if _running_dev_server():
        with app.app_context():
            try:
                upgrade()
            except Exception:
                app.logger.exception(
                    "Falha ao aplicar migrations no boot. "
                    "Verifique o banco e rode `flask db upgrade` manualmente."
                )

    return app


def _configure_logging(app):
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app.logger.handlers = [handler]
    app.logger.setLevel(level)


def _app_timezone():
    """Fuso para exibição (datas são armazenadas em UTC). Configurável via env."""
    name = os.environ.get("APP_TIMEZONE", "America/Sao_Paulo")
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # pragma: no cover - fallback se a tz não existir no SO
        from datetime import timezone

        return timezone.utc


def _register_context_processors(app):
    from .models.category import Categoria

    @app.context_processor
    def inject_globals():
        def get_categorias():
            try:
                return Categoria.query.filter_by(is_active=True).order_by(Categoria.name).all()
            except Exception:
                return []

        return {"ASKLY_VERSION": "0.1.0", "get_categorias": get_categorias}

    @app.template_filter("local")
    def _local(value, fmt="%d/%m/%Y %H:%M"):
        """Converte um datetime (UTC ou naive-assumido-UTC) para o fuso local."""
        from datetime import timezone

        if value is None:
            return "—"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(_app_timezone()).strftime(fmt)


def _register_error_handlers(app):
    def make_handler(code):
        def handler(_error):
            return render_template(f"errors/{code}.html"), code

        return handler

    for code in (400, 401, 403, 404, 500):
        app.register_error_handler(code, make_handler(code))
