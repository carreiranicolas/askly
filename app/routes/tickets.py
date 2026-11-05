from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models.ticket import StatusEnum
from app.services import can_manage_ticket, catalog_service, is_admin, ticket_service, user_service
from app.services.exceptions import ServiceError

web_tickets_bp = Blueprint("web_tickets", __name__, url_prefix="/chamados")

PER_PAGE = 5


def _list_filters():
    """Filtros da listagem normalizados (usados na query, paginação e busca."""
    status = (request.args.get("status") or "").strip() or None
    sla = (request.args.get("sla") or "").strip() or None
    if sla not in (None, "atrasado", "no_prazo"):
        sla = None
    return {
        "tipo": request.args.get("tipo") or None,
        "categoria_id": (
            request.args.get("categoria_id", type=int) or request.args.get("categoria", type=int)
        ),
        "status": status if status in StatusEnum.__members__ else None,
        "priority_id": request.args.get("priority_id", type=int) or None,
        "sla": sla,
        "q": (request.args.get("q") or "").strip() or None,
        "data": (request.args.get("data") or "").strip() or None,
    }


def _filter_page_args(filters):
    """Query string preservada na paginação."""
    args = {}
    for key in ("tipo", "categoria_id", "status", "priority_id", "sla", "q", "data"):
        value = filters.get(key)
        if value:
            args[key] = value
    return args


@web_tickets_bp.route("/")
@login_required
def listar():
    filters = _list_filters()
    try:
        query = ticket_service.tickets_query(current_user, **filters)
    except ServiceError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("web_tickets.listar"))
    pagination = query.paginate(
        page=request.args.get("page", 1, type=int),
        per_page=PER_PAGE,
        error_out=False,
    )
    user_is_admin = is_admin(current_user)
    return render_template(
        "tickets/listar.html",
        chamados=pagination,
        q=filters["q"] or "",
        filters=filters,
        filter_page_args=_filter_page_args(filters),
        categorias=catalog_service.list_categorias(only_active=True) if user_is_admin else [],
        prioridades=catalog_service.list_prioridades(only_active=True),
        status_options=list(StatusEnum),
        is_overdue=ticket_service.is_overdue,
        is_admin=user_is_admin,
    )


@web_tickets_bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if request.method == "POST":
        try:
            ticket = ticket_service.create_ticket(
                current_user,
                title=request.form.get("title", ""),
                description=request.form.get("description", ""),
                category_id=request.form.get("category_id", type=int),
                priority_id=request.form.get("priority_id", type=int),
                item_name=request.form.get("item_name", ""),
                equipment_tag=request.form.get("equipment_tag", ""),
                reported_date=request.form.get("reported_date", ""),
            )
        except ServiceError as exc:
            flash(exc.message, "danger")
        else:
            flash(f"Chamado #{ticket.id} aberto com sucesso.", "success")
            return redirect(url_for("web_tickets.detalhe", id=ticket.id))

    # Apenas catálogo ativo: o solicitante não deve ver áreas/prioridades
    # desativadas pelo admin.
    return render_template(
        "tickets/novo.html",
        categorias=catalog_service.list_categorias(only_active=True),
        prioridades=catalog_service.list_prioridades(only_active=True),
    )


@web_tickets_bp.route("/<int:id>")
@login_required
def detalhe(id):
    try:
        chamado = ticket_service.get_ticket(current_user, id)
    except ServiceError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("web_tickets.listar"))

    pode_gerir = can_manage_ticket(current_user, chamado)
    return render_template(
        "tickets/detalhe.html",
        chamado=chamado,
        pode_gerir=pode_gerir,
        comentarios=ticket_service.list_comments(current_user, id),
        historico=ticket_service.list_history(current_user, id),
        status_options=ticket_service.allowed_transitions(chamado.status) if pode_gerir else [],
        colegas_area=user_service.list_staff_for_area(chamado.category_id) if pode_gerir else [],
        pode_cancelar=chamado.requester_id == current_user.id
        and chamado.status == StatusEnum.EM_ABERTO
        and chamado.assignee_id is None,
        sla_deadline=ticket_service.sla_deadline(chamado),
        sla_overdue=ticket_service.is_overdue(chamado),
        sla_remaining=ticket_service.sla_remaining_label(chamado),
        is_overdue=ticket_service.is_overdue,
    )


@web_tickets_bp.route("/<int:id>/comentario", methods=["POST"])
@login_required
def adicionar_comentario(id):
    try:
        ticket_service.add_comment(current_user, id, request.form.get("content", ""))
        flash("Comentário adicionado.", "success")
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_tickets.detalhe", id=id))


@web_tickets_bp.route("/<int:id>/status", methods=["POST"])
@login_required
def alterar_status(id):
    try:
        ticket_service.change_status(
            current_user,
            id,
            request.form.get("status"),
            motivo=request.form.get("motivo"),
        )
        flash("Status atualizado.", "success")
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_tickets.detalhe", id=id))


@web_tickets_bp.route("/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar(id):
    try:
        ticket_service.cancel_ticket(current_user, id)
        flash("Chamado cancelado e excluído.", "success")
        return redirect(url_for("web_tickets.listar"))
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_tickets.detalhe", id=id))


@web_tickets_bp.route("/<int:id>/atribuir", methods=["POST"])
@login_required
def atribuir(id):
    try:
        ticket_service.assign_ticket(current_user, id, request.form.get("atendente_id", type=int))
        flash("Chamado atribuído.", "success")
    except ServiceError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("web_tickets.detalhe", id=id))
