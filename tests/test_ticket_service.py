"""Testes da lógica de domínio de chamados (`app/services/ticket_service.py`).

Aqui o foco é a lógica "pura" do serviço, complementando os testes de fluxo
HTTP em `test_tickets.py`:
  - `parse_status`: aceitar nome do enum ou rótulo e rejeitar inválidos;
  - `allowed_transitions`: os três estados do chamado;
  - SLA: cálculo de prazo, atraso e rótulo legível, manipulando `created_at`;
  - `dashboard_metrics`: a contagem agregada por status/área.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models.ticket import StatusEnum
from app.services import auth_service, ticket_service
from app.services.exceptions import ValidationError


def _novo_chamado(categoria_id, prioridade_id, email="dono@test.com"):
    """Cria um usuário Solicitante e um chamado dele; devolve (user, ticket).

    Usado pelos testes que precisam de um chamado real no banco para exercitar
    SLA e métricas. Roda assumindo um app_context já ativo.
    """
    user = auth_service.register("Dono", email, "Senha123")
    ticket = ticket_service.create_ticket(
        user,
        title="Chamado de teste",
        description="descricao",
        category_id=categoria_id,
        priority_id=prioridade_id,
        item_name="Computador",
        equipment_tag="PAT-123",
        reported_date="2026-11-05",
    )
    return user, ticket


# ----------------------------- parse_status -----------------------------
def test_parse_status_aceita_nome_do_enum(app):
    with app.app_context():
        assert ticket_service.parse_status("EM_ANDAMENTO") is StatusEnum.EM_ANDAMENTO


def test_parse_status_aceita_rotulo(app):
    """O rótulo legível ("Em andamento") também deve ser aceito."""
    with app.app_context():
        assert ticket_service.parse_status("Em andamento") is StatusEnum.EM_ANDAMENTO


def test_parse_status_invalido_gera_validacao(app):
    with app.app_context():
        with pytest.raises(ValidationError):
            ticket_service.parse_status("STATUS_QUE_NAO_EXISTE")


# -------------------------- allowed_transitions --------------------------
def test_status_transitions_follow_assignment(app):
    with app.app_context():
        assert ticket_service.allowed_transitions(StatusEnum.EM_ABERTO) == [
            StatusEnum.EM_ANDAMENTO,
            StatusEnum.FINALIZADO,
        ]
        assert ticket_service.allowed_transitions(StatusEnum.EM_ANDAMENTO) == [
            StatusEnum.FINALIZADO
        ]
        assert ticket_service.allowed_transitions(StatusEnum.FINALIZADO) == []


# --------------------------------- SLA ---------------------------------
def test_sla_deadline_soma_horas_da_prioridade(app, catalog):
    """O prazo do SLA é created_at + sla_hours da prioridade (Alta = 8h)."""
    with app.app_context():
        _, ticket = _novo_chamado(catalog["categoria"], catalog["prioridade"])
        esperado = ticket.created_at + timedelta(hours=8)
        assert ticket_service.sla_deadline(ticket) == esperado


def test_is_overdue_true_quando_prazo_estourou(app, catalog):
    """Recuando o created_at para 10h atrás (SLA 8h), o chamado fica atrasado."""
    with app.app_context():
        user, ticket = _novo_chamado(catalog["categoria"], catalog["prioridade"])
        from app.models.role import Cargo

        tec = auth_service.register(
            "Tec",
            "tec-overdue@test.com",
            "Senha123",
            Cargo.query.filter_by(name="Atendente").first().id,
            area_id=catalog["categoria"],
        )
        admin = auth_service.register(
            "Admin",
            "adm-overdue@test.com",
            "Senha123",
            Cargo.query.filter_by(name="Admin").first().id,
        )
        ticket_service.assign_ticket(admin, ticket.id, tec.id)
        ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=10)
        db.session.commit()
        assert ticket_service.is_overdue(ticket) is True
        assert "Atrasado" in ticket_service.sla_remaining_label(ticket)


def test_is_overdue_false_em_estado_que_para_o_sla(app, catalog):
    """Mesmo vencido, um chamado finalizado não conta como atrasado."""
    with app.app_context():
        _, ticket = _novo_chamado(catalog["categoria"], catalog["prioridade"])
        ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=10)
        ticket.status = StatusEnum.FINALIZADO
        db.session.commit()
        assert ticket_service.is_overdue(ticket) is False
        assert ticket_service.sla_remaining_label(ticket) == "SLA pausado"


def test_em_aberto_pausa_sla(app, catalog):
    with app.app_context():
        _, ticket = _novo_chamado(catalog["categoria"], catalog["prioridade"])
        ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=10)
        db.session.commit()
        assert ticket.status == StatusEnum.EM_ABERTO
        assert ticket_service.is_overdue(ticket) is False
        assert ticket_service.sla_remaining_label(ticket) == "SLA pausado"


def test_em_andamento_ativa_sla(app, catalog):
    with app.app_context():
        _, ticket = _novo_chamado(catalog["categoria"], catalog["prioridade"])
        ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=10)
        ticket.status = StatusEnum.EM_ANDAMENTO
        db.session.commit()
        assert ticket_service.is_overdue(ticket) is True


# ----------------------------- Dashboard -----------------------------
def test_dashboard_metrics_conta_abertos(app, catalog):
    """Um chamado recém-criado (Em aberto) deve contar como 1 total e 1 em aberto."""
    with app.app_context():
        user, _ = _novo_chamado(catalog["categoria"], catalog["prioridade"])
        metrics = ticket_service.dashboard_metrics(user)
        assert metrics["total"] == 1
        assert metrics["abertos"] == 1
        assert metrics["finalizados"] == 0


def test_filtro_sla_atrasado(app, catalog):
    """Filtro sla=atrasado retorna só chamados em atendimento com prazo estourado."""
    with app.app_context():
        user, ticket = _novo_chamado(catalog["categoria"], catalog["prioridade"])
        from app.models.role import Cargo

        tec = auth_service.register(
            "Tec",
            "tec-filtro@test.com",
            "Senha123",
            Cargo.query.filter_by(name="Atendente").first().id,
            area_id=catalog["categoria"],
        )
        admin = auth_service.register(
            "Admin",
            "adm-filtro@test.com",
            "Senha123",
            Cargo.query.filter_by(name="Admin").first().id,
        )
        ticket_service.assign_ticket(admin, ticket.id, tec.id)
        ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=10)
        db.session.commit()

        atrasados = ticket_service.list_tickets(user, sla="atrasado")
        no_prazo = ticket_service.list_tickets(user, sla="no_prazo")

        assert len(atrasados) == 1
        assert atrasados[0].id == ticket.id
        assert no_prazo == []

        ticket.status = StatusEnum.FINALIZADO
        db.session.commit()
        assert ticket_service.list_tickets(user, sla="atrasado") == []
