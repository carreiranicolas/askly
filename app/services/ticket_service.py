from datetime import date, datetime, timedelta

from sqlalchemy import func, or_

from app.extensions import db
from app.models.category import Categoria
from app.models.commentary import Comentario
from app.models.history import HistoricoStatus
from app.models.priority import Prioridade
from app.models.ticket import Chamado, StatusEnum
from app.models.user import Usuario

from . import ROLE_ADMIN, can_manage_ticket, is_admin, role_of
from .exceptions import NotFoundError, PermissionDenied, ValidationError

# Estados em que o SLA não corre (pausado ou encerrado).
_SLA_PAUSED = (
    StatusEnum.EM_ABERTO,
    StatusEnum.FINALIZADO,
)
_SLA_RUNNING = (StatusEnum.EM_ANDAMENTO,)
_OPEN = (StatusEnum.EM_ABERTO, StatusEnum.EM_ANDAMENTO)


def parse_status(value):
    """Aceita o nome do enum (EM_ANDAMENTO) ou o rótulo (Em andamento)."""
    if isinstance(value, StatusEnum):
        return value
    if value is None:
        raise ValidationError("Status é obrigatório.")
    key = str(value).strip()
    if key in StatusEnum.__members__:
        return StatusEnum[key]
    for status in StatusEnum:
        if status.value.lower() == key.lower():
            return status
    raise ValidationError(f"Status inválido: {value}.")


def allowed_transitions(current):
    """Transições válidas a partir do status atual (máquina de estados)."""
    if current == StatusEnum.EM_ABERTO:
        return [StatusEnum.EM_ANDAMENTO, StatusEnum.FINALIZADO]
    if current == StatusEnum.EM_ANDAMENTO:
        return [StatusEnum.FINALIZADO]
    return []


# ------------------------------- SLA -------------------------------
def sla_deadline(ticket):
    if ticket.priority is None or ticket.priority.sla_hours is None:
        return None
    return ticket.created_at + timedelta(hours=ticket.priority.sla_hours)


def _now_like(dt):
    """datetime.now() ciente do fuso de `dt` (que pode ser naive ou aware)."""
    if dt is not None and dt.tzinfo is not None:
        return datetime.now(dt.tzinfo)
    return datetime.now()


def is_overdue(ticket):
    deadline = sla_deadline(ticket)
    if deadline is None or ticket.status in _SLA_PAUSED:
        return False
    return _now_like(deadline) > deadline


def sla_remaining_label(ticket):
    """Retorna texto legível do tempo restante/atrasado do SLA."""
    deadline = sla_deadline(ticket)
    if deadline is None:
        return None
    if ticket.status in _SLA_PAUSED:
        return "SLA pausado"
    delta_h = (deadline - _now_like(deadline)).total_seconds() / 3600
    hours = abs(delta_h)
    if hours < 1:
        time_str = f"{int(round(hours * 60))}min"
    elif hours < 24:
        time_str = f"{int(round(hours))}h"
    else:
        days = int(hours // 24)
        rest = int(round(hours % 24))
        time_str = f"{days}d {rest}h" if rest else f"{days}d"
    if delta_h < 0:
        return f"Atrasado há {time_str}"
    return f"Faltam {time_str}"


# ----------------------------- Consultas -----------------------------
def _can_view(user, ticket):
    if is_admin(user):
        return True
    if ticket.requester_id == user.id:
        return True
    return False


def tickets_query(
    user, tipo=None, categoria_id=None, q=None, status=None, priority_id=None, sla=None, data=None
):
    """Query de chamados já com RBAC + filtros (para listar/paginar/contar).

    Admin vê todos; os demais veem apenas os próprios chamados.
    """
    query = Chamado.query

    if tipo == "meus":
        query = query.filter(Chamado.requester_id == user.id)
    elif tipo == "atribuidos" and is_admin(user):
        query = query.filter(Chamado.assignee_id == user.id)
    elif is_admin(user):
        pass
    else:
        query = query.filter(Chamado.requester_id == user.id)

    if categoria_id:
        query = query.filter(Chamado.category_id == categoria_id)
    if status:
        query = query.filter(Chamado.status == parse_status(status))
    if priority_id:
        query = query.filter(Chamado.priority_id == priority_id)
    if data:
        try:
            query = query.filter(Chamado.reported_date == date.fromisoformat(data))
        except ValueError as exc:
            raise ValidationError("Data inválida.") from exc
    if sla in ("atrasado", "no_prazo"):
        query = query.join(Prioridade, Chamado.priority_id == Prioridade.id)
        # Postgres: make_interval(years, months, weeks, days, hours, …)
        deadline = Chamado.created_at + func.make_interval(0, 0, 0, 0, Prioridade.sla_hours)
        now = func.now()
        active = Chamado.status.in_(_SLA_RUNNING)
        if sla == "atrasado":
            query = query.filter(active, Prioridade.sla_hours.isnot(None), deadline < now)
        else:
            query = query.filter(or_(~active, Prioridade.sla_hours.is_(None), deadline >= now))
    if q and q.strip():
        term = q.strip()
        if term.startswith("#"):
            term = term[1:]
        if term.isdigit():
            query = query.filter(Chamado.id == int(term))
        else:
            like = f"%{term}%"
            query = query.filter(or_(Chamado.title.ilike(like), Chamado.description.ilike(like)))
    return query.order_by(Chamado.reported_date.desc(), Chamado.created_at.desc())


def list_tickets(
    user, tipo=None, categoria_id=None, q=None, status=None, priority_id=None, sla=None, data=None
):
    return tickets_query(
        user,
        tipo=tipo,
        categoria_id=categoria_id,
        q=q,
        status=status,
        priority_id=priority_id,
        sla=sla,
        data=data,
    ).all()


def get_ticket(user, ticket_id, for_update=False):
    ticket = (
        db.session.execute(
            db.select(Chamado).where(Chamado.id == ticket_id).with_for_update()
        ).scalar_one_or_none()
        if for_update
        else db.session.get(Chamado, ticket_id)
    )
    if ticket is None:
        raise NotFoundError("Chamado não encontrado.")
    if not _can_view(user, ticket):
        raise PermissionDenied("Você não tem acesso a este chamado.")
    return ticket


TITLE_MIN_LENGTH = 2
TITLE_MAX_LENGTH = 150


def create_ticket(
    user, title, description, category_id, priority_id, item_name, equipment_tag, reported_date
):
    title = (title or "").strip()
    description = (description or "").strip()
    item_name = (item_name or "").strip()
    equipment_tag = (equipment_tag or "").strip()

    if len(title) < TITLE_MIN_LENGTH:
        raise ValidationError(f"O título precisa ter ao menos {TITLE_MIN_LENGTH} caracteres.")
    if len(title) > TITLE_MAX_LENGTH:
        raise ValidationError(f"O título pode ter no máximo {TITLE_MAX_LENGTH} caracteres.")
    if not description:
        raise ValidationError("A descrição é obrigatória.")
    if not item_name or len(item_name) > 150:
        raise ValidationError("Informe o nome do item (até 150 caracteres).")
    if not equipment_tag or len(equipment_tag) > 100:
        raise ValidationError("Informe o número da etiqueta (até 100 caracteres).")
    try:
        reported_date = date.fromisoformat(reported_date)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Informe uma data válida.") from exc

    categoria = db.session.get(Categoria, category_id) if category_id else None
    if categoria is None:
        raise ValidationError("Área informada não existe.")
    if not categoria.is_active:
        raise ValidationError("Esta área está inativa e não pode receber novos chamados.")

    prioridade = db.session.get(Prioridade, priority_id) if priority_id else None
    if prioridade is None:
        raise ValidationError("Prioridade informada não existe.")
    if not prioridade.is_active:
        raise ValidationError(
            "Esta prioridade está inativa e não pode ser usada em novos chamados."
        )

    ticket = Chamado(
        title=title,
        description=description,
        item_name=item_name,
        equipment_tag=equipment_tag,
        reported_date=reported_date,
        category_id=category_id,
        priority_id=priority_id,
        requester_id=user.id,
        status=StatusEnum.EM_ABERTO,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def _record_transition(user, ticket, target, motivo=None):
    """Aplica a transição validando a máquina de estados e gera auditoria."""
    if target not in allowed_transitions(ticket.status):
        raise ValidationError(
            f"Transição inválida: de '{ticket.status.value}' para '{target.value}'."
        )

    previous = ticket.status
    ticket.status = target
    # Auditoria obrigatória: toda mudança de status gera histórico (com motivo).
    db.session.add(
        HistoricoStatus(
            ticket_id=ticket.id,
            previous_status=previous.value,
            new_status=target.value,
            motivo=(motivo.strip() if motivo and motivo.strip() else None),
            changed_by_id=user.id,
        )
    )
    db.session.commit()


def change_status(user, ticket_id, new_status, motivo=None):
    ticket = get_ticket(user, ticket_id, for_update=True)
    target = parse_status(new_status)
    if not can_manage_ticket(user, ticket):
        raise PermissionDenied("Apenas administradores podem alterar o status.")
    _record_transition(user, ticket, target, motivo)
    return ticket


def assign_ticket(actor, ticket_id, assignee_id):
    ticket = get_ticket(actor, ticket_id, for_update=True)
    if not can_manage_ticket(actor, ticket):
        raise PermissionDenied("Apenas administradores podem atribuir responsáveis.")

    assignee = db.session.get(Usuario, assignee_id)
    if assignee is None:
        raise ValidationError("Usuário atribuído não existe.")
    if not assignee.is_active:
        raise ValidationError("Não é possível atribuir o chamado a um usuário inativo.")
    if assignee.area_id != ticket.category_id:
        raise ValidationError("Só é possível atribuir a usuários da área do chamado.")

    ticket.assignee_id = assignee_id
    if ticket.status == StatusEnum.EM_ABERTO:
        _record_transition(
            actor,
            ticket,
            StatusEnum.EM_ANDAMENTO,
            motivo="Responsável atribuído.",
        )
    else:
        db.session.commit()
    return ticket


def cancel_ticket(user, ticket_id):
    ticket = db.session.execute(
        db.select(Chamado).where(Chamado.id == ticket_id).with_for_update()
    ).scalar_one_or_none()
    if ticket is None:
        raise NotFoundError("Chamado não encontrado.")
    if ticket.requester_id != user.id:
        raise PermissionDenied("Só quem abriu pode cancelar o chamado.")
    if ticket.status != StatusEnum.EM_ABERTO or ticket.assignee_id is not None:
        raise ValidationError("O atendimento já foi iniciado; não é possível cancelar.")
    HistoricoStatus.query.filter_by(ticket_id=ticket.id).delete()
    Comentario.query.filter_by(ticket_id=ticket.id).delete()
    db.session.delete(ticket)
    db.session.commit()


def list_history(user, ticket_id):
    ticket = get_ticket(user, ticket_id)
    return (
        HistoricoStatus.query.filter_by(ticket_id=ticket.id)
        .order_by(HistoricoStatus.created_at)
        .all()
    )


def list_comments(user, ticket_id):
    ticket = get_ticket(user, ticket_id)
    return Comentario.query.filter_by(ticket_id=ticket.id).order_by(Comentario.created_at).all()


def add_comment(user, ticket_id, content):
    ticket = get_ticket(user, ticket_id)
    if not content or not content.strip():
        raise ValidationError("O comentário não pode ser vazio.")
    comment = Comentario(content=content, ticket_id=ticket.id, author_id=user.id)
    db.session.add(comment)
    db.session.commit()
    return comment


# ----------------------------- Dashboard -----------------------------
def dashboard_metrics(user):
    tickets = tickets_query(user).all()
    by_status = {}
    by_area = {}

    # Admin vê todas as áreas cadastradas (mesmo sem chamados).
    if role_of(user) == ROLE_ADMIN:
        for cat in Categoria.query.filter_by(is_active=True).all():
            by_area[cat.name] = 0

    overdue = 0
    em_aberto = 0
    for t in tickets:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        area = t.category.name if t.category else "—"
        by_area[area] = by_area.get(area, 0) + 1
        if t.status in _OPEN:
            em_aberto += 1
        if is_overdue(t):
            overdue += 1
    return {
        "total": len(tickets),
        "abertos": em_aberto,
        "em_andamento": sum(1 for t in tickets if t.status == StatusEnum.EM_ANDAMENTO),
        "finalizados": sum(1 for t in tickets if t.status == StatusEnum.FINALIZADO),
        "atrasados": overdue,
        "por_status": sorted(by_status.items(), key=lambda kv: kv[0]),
        "por_area": sorted(by_area.items(), key=lambda kv: kv[0]),
    }


# ------------------------------- SLA -------------------------------
def _humanize_hours(hours):
    """Formata uma quantidade de horas em algo legível: 45min, 6h, 2d 3h."""
    hours = abs(hours)
    if hours < 1:
        return f"{int(round(hours * 60))}min"
    if hours < 24:
        return f"{int(round(hours))}h"
    days = int(hours // 24)
    rest = int(round(hours % 24))
    return f"{days}d {rest}h" if rest else f"{days}d"


def _close_timestamps(ticket_ids):
    """Mapa ticket_id -> instante em que entrou em 'Fechado' (via auditoria)."""
    if not ticket_ids:
        return {}
    rows = HistoricoStatus.query.filter(
        HistoricoStatus.ticket_id.in_(ticket_ids),
        HistoricoStatus.new_status.in_((StatusEnum.FINALIZADO.value, "Fechado")),
    ).all()
    closed_at = {}
    for r in rows:
        if r.ticket_id not in closed_at or r.created_at > closed_at[r.ticket_id]:
            closed_at[r.ticket_id] = r.created_at
    return closed_at


def sla_report(user):
    """Acompanhamento de SLA (escopo por RBAC):

    - `ativos`: chamados em aberto com prazo de SLA correndo;
    - `por_area`: tempo médio de fechamento e cumprimento de SLA por área.
    """
    tickets = tickets_query(user).all()

    ativos = []
    for t in tickets:
        if t.status == StatusEnum.EM_ABERTO:
            ativos.append(
                {
                    "ticket": t,
                    "deadline": sla_deadline(t),
                    "overdue": False,
                    "remaining_label": "Aguardando atribuição",
                }
            )
            continue
        if t.status not in _SLA_RUNNING:
            continue
        deadline = sla_deadline(t)
        overdue = is_overdue(t)
        if deadline is None:
            label = "—"
        else:
            delta_h = (deadline - _now_like(deadline)).total_seconds() / 3600
            label = (
                f"Atrasado há {_humanize_hours(delta_h)}"
                if delta_h < 0
                else f"Faltam {_humanize_hours(delta_h)}"
            )
        ativos.append(
            {
                "ticket": t,
                "deadline": deadline,
                "overdue": overdue,
                "remaining_label": label,
            }
        )
    ativos.sort(
        key=lambda r: (not r["overdue"], r["deadline"] is None, r["deadline"] or datetime.max)
    )

    atrasados = sum(1 for r in ativos if r["overdue"])
    vence_24h = 0
    for r in ativos:
        if r["overdue"] or r["deadline"] is None:
            continue
        delta_h = (r["deadline"] - _now_like(r["deadline"])).total_seconds() / 3600
        if 0 < delta_h <= 24:
            vence_24h += 1

    resumo = {
        "correndo": len(ativos),
        "atrasados": atrasados,
        "vence_24h": vence_24h,
        "sem_responsavel": sum(1 for t in tickets if t.status == StatusEnum.EM_ABERTO),
    }

    closed = [t for t in tickets if t.status == StatusEnum.FINALIZADO]
    closed_at = _close_timestamps([t.id for t in closed])

    # Admin vê todas as áreas cadastradas; demais usuários só as que aparecem
    # nos chamados que podem visualizar.
    buckets = {}
    if role_of(user) == ROLE_ADMIN:
        for cat in Categoria.query.filter_by(is_active=True).all():
            buckets[cat.name] = {"count": 0, "hours": 0.0, "within": 0}

    for t in closed:
        area = t.category.name if t.category else "—"
        b = buckets.setdefault(area, {"count": 0, "hours": 0.0, "within": 0})
        end = closed_at.get(t.id) or t.updated_at
        if end is not None:
            b["hours"] += (end - t.created_at).total_seconds() / 3600
        b["count"] += 1
        deadline = sla_deadline(t)
        if deadline is not None and end is not None and end <= deadline:
            b["within"] += 1

    por_area = []
    for area, b in sorted(buckets.items(), key=lambda kv: kv[0]):
        count = b["count"]
        avg = b["hours"] / count if count else 0
        por_area.append(
            {
                "area": area,
                "fechados": count,
                "avg_hours": avg,
                "avg_label": _humanize_hours(avg) if count else None,
                "sla_compliance": round(b["within"] / count * 100) if count else None,
            }
        )

    return {"ativos": ativos, "por_area": por_area, "resumo": resumo}
