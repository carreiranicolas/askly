def test_dashboard_requires_login(client):
    assert client.get("/dashboard/").status_code == 302


def test_dashboard_metrics_scoped_by_area(app, make_user, areas):
    """Admin vê todos; qualquer outro perfil vê apenas os próprios."""
    from app.models.priority import Prioridade
    from app.models.user import Usuario
    from app.services import ticket_service

    sol_email, _ = make_user(role="Solicitante", email="sol-dash@test.com", area="RH")
    rh_email, _ = make_user(role="Atendente", email="rh-dash@test.com", area="RH")
    adm_email, _ = make_user(role="Admin", email="adm-dash@test.com")

    with app.app_context():
        sol = Usuario.query.filter_by(email=sol_email).first()
        rh = Usuario.query.filter_by(email=rh_email).first()
        adm = Usuario.query.filter_by(email=adm_email).first()
        pid = Prioridade.query.first().id

        ticket_service.create_ticket(
            sol,
            title="RH",
            description="x",
            category_id=areas["RH"],
            priority_id=pid,
            item_name="Computador",
            equipment_tag="PAT-123",
            reported_date="2026-11-05",
        )
        ticket_service.create_ticket(
            sol,
            title="Infra",
            description="x",
            category_id=areas["Infraestrutura"],
            priority_id=pid,
            item_name="Computador",
            equipment_tag="PAT-123",
            reported_date="2026-11-05",
        )

        # O perfil legado Atendente também fica restrito aos próprios chamados.
        assert ticket_service.dashboard_metrics(rh)["total"] == 0
        # Admin contabiliza todos.
        assert ticket_service.dashboard_metrics(adm)["total"] == 2


def test_dashboard_em_aberto_counts_active_states(app, make_user, areas):
    """Abertos inclui Em aberto e Em andamento."""
    from app.models.priority import Prioridade
    from app.models.user import Usuario
    from app.services import ticket_service

    sol_email, _ = make_user(role="Solicitante", email="sol-ab@test.com", area="RH")
    rh_email, _ = make_user(role="Atendente", email="rh-ab@test.com", area="RH")
    adm_email, _ = make_user(role="Admin", email="adm-ab@test.com")

    with app.app_context():
        sol = Usuario.query.filter_by(email=sol_email).first()
        rh = Usuario.query.filter_by(email=rh_email).first()
        adm = Usuario.query.filter_by(email=adm_email).first()
        pid = Prioridade.query.first().id

        t = ticket_service.create_ticket(
            sol,
            title="Chamado teste",
            description="Descrição do chamado.",
            category_id=areas["RH"],
            priority_id=pid,
            item_name="Computador",
            equipment_tag="PAT-123",
            reported_date="2026-11-05",
        )

        m = ticket_service.dashboard_metrics(adm)
        assert m["abertos"] == 1

        ticket_service.assign_ticket(adm, t.id, rh.id)
        m = ticket_service.dashboard_metrics(adm)
        assert m["abertos"] == 1

        ticket_service.change_status(adm, t.id, "FINALIZADO")
        m = ticket_service.dashboard_metrics(adm)
        assert m["abertos"] == 0
        assert m["finalizados"] == 1


def test_fresh_ticket_is_not_overdue(app, make_user, areas):
    """Regressão: chamado recém-aberto não pode constar como atrasado
    (created_at é gravado em UTC consciente, evitando o deslocamento de fuso)."""
    from datetime import datetime, timedelta, timezone

    from app.extensions import db
    from app.models.priority import Prioridade
    from app.models.ticket import Chamado
    from app.models.user import Usuario
    from app.services import ticket_service

    sol_email, _ = make_user(role="Solicitante", email="sol-sla@test.com", area="RH")
    with app.app_context():
        sol = Usuario.query.filter_by(email=sol_email).first()
        # SLA curto (1h) — pior caso para o bug de fuso.
        p = Prioridade(name="Imediata", description="x", sla_hours=1, is_active=True)
        db.session.add(p)
        db.session.commit()

        t = ticket_service.create_ticket(
            sol,
            title="novo",
            description="x",
            category_id=areas["RH"],
            priority_id=p.id,
            item_name="Computador",
            equipment_tag="PAT-123",
            reported_date="2026-11-05",
        )
        assert ticket_service.is_overdue(db.session.get(Chamado, t.id)) is False

        # SLA só corre em Em andamento.
        old = db.session.get(Chamado, t.id)
        old.created_at = datetime.now(timezone.utc) - timedelta(hours=5)
        db.session.commit()
        assert ticket_service.is_overdue(db.session.get(Chamado, t.id)) is False

        from app.models.role import Cargo
        from app.services import auth_service

        rh_adm = auth_service.register(
            "Admin RH",
            "adm-sla-rh@test.com",
            "Senha123",
            Cargo.query.filter_by(name="Admin").first().id,
        )
        rh_tec = auth_service.register(
            "Tec RH",
            "tec-sla-rh@test.com",
            "Senha123",
            Cargo.query.filter_by(name="Atendente").first().id,
            area_id=areas["RH"],
        )
        ticket_service.assign_ticket(rh_adm, t.id, rh_tec.id)
        assert ticket_service.is_overdue(db.session.get(Chamado, t.id)) is True


def test_sla_report_has_expected_shape(app, make_user):
    from app.models.user import Usuario
    from app.services import ticket_service

    adm_email, _ = make_user(role="Admin", email="adm-sla@test.com")
    with app.app_context():
        adm = Usuario.query.filter_by(email=adm_email).first()
        report = ticket_service.sla_report(adm)
        assert "ativos" in report
        assert "por_area" in report
        assert "resumo" in report
        assert set(report["resumo"]) == {"correndo", "atrasados", "vence_24h", "sem_responsavel"}


def test_sla_report_resumo_e_areas_sem_fechamento(app, make_user, areas):
    """Resumo conta SLA correndo; áreas sem fechamento não exibem compliance 0%."""
    from datetime import datetime, timedelta, timezone

    from app.extensions import db
    from app.models.priority import Prioridade
    from app.models.user import Usuario
    from app.services import ticket_service

    sol_email, _ = make_user(role="Solicitante", email="sol-sla-r@test.com", area="RH")
    rh_email, _ = make_user(role="Atendente", email="rh-sla-r@test.com", area="RH")
    adm_email, _ = make_user(role="Admin", email="adm-sla-r@test.com")

    with app.app_context():
        sol = Usuario.query.filter_by(email=sol_email).first()
        rh = Usuario.query.filter_by(email=rh_email).first()
        adm = Usuario.query.filter_by(email=adm_email).first()
        pid = Prioridade.query.first().id

        t1 = ticket_service.create_ticket(
            sol,
            title="Atrasado",
            description="x",
            category_id=areas["RH"],
            priority_id=pid,
            item_name="Computador",
            equipment_tag="PAT-123",
            reported_date="2026-11-05",
        )
        t1.created_at = datetime.now(timezone.utc) - timedelta(hours=10)
        db.session.commit()

        ticket_service.create_ticket(
            sol,
            title="Sem dono",
            description="x",
            category_id=areas["RH"],
            priority_id=pid,
            item_name="Computador",
            equipment_tag="PAT-123",
            reported_date="2026-11-05",
        )

        t3 = ticket_service.create_ticket(
            sol,
            title="Fechado ok",
            description="x",
            category_id=areas["RH"],
            priority_id=pid,
            item_name="Computador",
            equipment_tag="PAT-123",
            reported_date="2026-11-05",
        )
        ticket_service.assign_ticket(adm, t3.id, rh.id)
        ticket_service.change_status(adm, t3.id, "FINALIZADO")

        report = ticket_service.sla_report(adm)
        assert report["resumo"]["correndo"] == 2
        assert report["resumo"]["atrasados"] == 0
        assert report["resumo"]["sem_responsavel"] == 2

        ticket_service.assign_ticket(adm, t1.id, rh.id)
        report = ticket_service.sla_report(adm)
        assert report["resumo"]["correndo"] == 2
        assert report["resumo"]["atrasados"] == 1
        assert report["resumo"]["sem_responsavel"] == 1

        rh_area = next(a for a in report["por_area"] if a["area"] == "RH")
        assert rh_area["fechados"] == 1
        assert rh_area["sla_compliance"] == 100

        infra = next(a for a in report["por_area"] if a["area"] == "Infraestrutura")
        assert infra["fechados"] == 0
        assert infra["sla_compliance"] is None

        com_dados = [a for a in report["por_area"] if a["fechados"]]
        assert len(com_dados) == 1
        assert com_dados[0]["area"] == "RH"


def test_dashboard_ok_for_logged_user(client, make_user):
    email, password = make_user(role="Admin", email="adm@test.com")
    client.post("/login", data={"email": email, "password": password})
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    assert "Dashboard" in resp.get_data(as_text=True)


def test_sla_page_requires_admin(client, make_user):
    """SLA & Métricas é restrito a administradores."""
    adm_email, adm_pass = make_user(role="Admin", email="adm-sla-page@test.com")
    sol_email, sol_pass = make_user(role="Solicitante", email="sol-sla-page@test.com")

    client.post("/login", data={"email": sol_email, "password": sol_pass})
    assert client.get("/dashboard/sla").status_code == 403

    client.post("/logout")
    client.post("/login", data={"email": adm_email, "password": adm_pass})
    assert client.get("/dashboard/sla").status_code == 200


def test_web_search_filters(client, make_user, api_login, catalog):
    email, password = make_user(role="Solicitante", email="sol@test.com")
    headers = api_login(email)
    for title in ("Impressora quebrada", "Acesso VPN"):
        client.post(
            "/api/v1/chamados",
            json={
                "title": title,
                "description": "x",
                "category_id": catalog["categoria"],
                "priority_id": catalog["prioridade"],
                "item_name": "Computador",
                "equipment_tag": "PAT-123",
                "reported_date": "2026-11-05",
            },
            headers=headers,
        )
    client.post("/login", data={"email": email, "password": password})
    body = client.get("/chamados/?q=Impressora").get_data(as_text=True)
    assert "Impressora quebrada" in body
    assert "Acesso VPN" not in body
