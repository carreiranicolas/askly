from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.routes.decorators import admin_required
from app.services import ROLE_ADMIN, ROLE_SOLICITANTE, catalog_service, user_service
from app.services.exceptions import ServiceError

web_admin_bp = Blueprint("web_admin", __name__, url_prefix="/admin")


def _staff_cargos():
    return [c for c in catalog_service.list_cargos() if c.name in (ROLE_SOLICITANTE, ROLE_ADMIN)]


@web_admin_bp.route("/usuarios")
@admin_required
def usuarios():
    return render_template(
        "admin/usuarios.html",
        usuarios=user_service.list_users(),
        cargos=_staff_cargos(),
        areas=catalog_service.list_categorias(),
    )


@web_admin_bp.route("/usuarios/<int:id>/cargo", methods=["POST"])
@admin_required
def alterar_perfil(id):
    role_id = request.form.get("role_id", type=int)
    if not role_id:
        flash("Selecione Solicitante ou Admin.", "danger")
        return redirect(url_for("web_admin.usuarios"))
    try:
        user_service.update_user(
            id,
            role_id=role_id,
            area_id=request.form.get("area_id", type=int),
        )
        flash("Usuário atualizado.", "success")
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_admin.usuarios"))


@web_admin_bp.route("/usuarios/<int:id>/toggle", methods=["POST"])
@admin_required
def toggle_usuario(id):
    try:
        user = user_service.toggle_user_active(current_user, id)
        flash(
            "Usuário desativado." if not user.is_active else "Usuário reativado.",
            "success",
        )
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_admin.usuarios"))


@web_admin_bp.route("/categorias")
@admin_required
def categorias():
    return render_template("admin/categorias.html", categorias=catalog_service.list_categorias())


@web_admin_bp.route("/categorias/criar", methods=["POST"])
@admin_required
def criar_categoria():
    try:
        catalog_service.create_categoria(
            request.form.get("name", "").strip(),
            request.form.get("description", "").strip(),
        )
        flash("Área criada.", "success")
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_admin.categorias"))


@web_admin_bp.route("/categorias/<int:id>/toggle", methods=["POST"])
@admin_required
def toggle_categoria(id):
    try:
        categoria = catalog_service.get_categoria(id)
        was_active = categoria.is_active
        catalog_service.update_categoria(id, is_active=not was_active)
        flash(
            "Área desativada." if was_active else "Área ativada.",
            "success",
        )
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_admin.categorias"))
