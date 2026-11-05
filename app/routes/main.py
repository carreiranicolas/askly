from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.forms.login_form import LoginForm
from app.forms.register_form import RegisterForm
from app.services import auth_service
from app.services.exceptions import ServiceError

main_bp = Blueprint("main", __name__)
web_auth_bp = Blueprint("web_auth", __name__)


def _safe_next(target):
    """Evita open redirect: só aceita caminhos relativos do próprio site."""
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/"):
        return None
    return target


@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("web_tickets.listar"))
    return redirect(url_for("web_auth.login"))


@web_auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = LoginForm()

    if form.validate_on_submit():
        try:
            user = auth_service.authenticate(form.email.data, form.password.data)
        except ServiceError as exc:
            flash(exc.message, "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        next_page = _safe_next(request.args.get("next"))
        return redirect(next_page or url_for("main.home"))

    return render_template("auth/login.html", form=form)


@web_auth_bp.route("/cadastro", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = RegisterForm()

    if form.validate_on_submit():
        try:
            novo_usuario = auth_service.register(
                name=form.name.data,
                email=form.email.data,
                password=form.password.data,
                area_id=form.area.data.id,
            )
        except ServiceError as exc:
            flash(exc.message, "danger")
            return render_template("auth/cadastro.html", form=form)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao cadastrar usuário")
            flash("Não foi possível concluir o cadastro. Tente novamente.", "danger")
            return render_template("auth/cadastro.html", form=form)

        # Já entra logado na plataforma após o cadastro.
        login_user(novo_usuario)
        flash(f"Bem-vindo(a), {novo_usuario.name}! Sua conta foi criada.", "success")
        return redirect(url_for("main.home"))

    return render_template("auth/cadastro.html", form=form)


@web_auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("web_auth.login"))
