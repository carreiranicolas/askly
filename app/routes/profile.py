from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.forms.change_password_form import ChangePasswordForm
from app.services import auth_service
from app.services.exceptions import ServiceError

web_profile_bp = Blueprint("web_profile", __name__, url_prefix="/configuracoes")


@web_profile_bp.route("/")
@login_required
def configuracoes():
    form = ChangePasswordForm()
    return render_template("profile/configuracoes.html", form=form, usuario=current_user)


@web_profile_bp.route("/senha", methods=["POST"])
@login_required
def alterar_senha():
    form = ChangePasswordForm()

    if form.validate_on_submit():
        try:
            auth_service.change_password(
                current_user,
                form.current_password.data,
                form.new_password.data,
            )
        except ServiceError as exc:
            flash(exc.message, "danger")
            return redirect(url_for("web_profile.configuracoes"))

        flash("Senha alterada com sucesso.", "success")
        return redirect(url_for("web_profile.configuracoes"))

    for errors in form.errors.values():
        for error in errors:
            flash(error, "danger")
    return redirect(url_for("web_profile.configuracoes"))
