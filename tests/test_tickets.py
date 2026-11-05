"""Fluxo da API de chamados e regras de acesso do enunciado."""


def _create(client, headers, catalog, **overrides):
    data = {
        "title": "Impressora com defeito",
        "description": "Não imprime",
        "item_name": "Impressora HP",
        "equipment_tag": "PAT-123",
        "reported_date": "2026-11-05",
        "category_id": catalog["categoria"],
        "priority_id": catalog["prioridade"],
    }
    data.update(overrides)
    return client.post("/api/v1/chamados", json=data, headers=headers)


def test_opening_requires_and_returns_all_fields(client, make_user, api_login, catalog):
    email, _ = make_user(email="dono@test.com")
    headers = api_login(email)
    response = _create(client, headers, catalog)
    assert response.status_code == 201
    ticket = response.get_json()
    assert ticket["status"] == "Em aberto"
    assert ticket["item_name"] == "Impressora HP"
    assert ticket["equipment_tag"] == "PAT-123"
    assert ticket["reported_date"] == "2026-11-05"
    assert ticket["description"] == "Não imprime"
    assert ticket["category_id"] == catalog["categoria"]
    assert _create(client, headers, catalog, equipment_tag="").status_code == 400
    assert _create(client, headers, catalog, reported_date="2026-02-30").status_code == 400


def test_common_user_sees_only_own_tickets_even_in_same_area(client, make_user, api_login, catalog):
    first, _ = make_user(email="primeiro@test.com", area="Infraestrutura")
    second, _ = make_user(email="segundo@test.com", area="Infraestrutura")
    admin, _ = make_user(role="Admin", email="admin@test.com")
    first_auth = api_login(first)
    second_auth = api_login(second)
    admin_auth = api_login(admin)
    ticket_id = _create(client, first_auth, catalog).get_json()["id"]
    assert len(client.get("/api/v1/chamados", headers=first_auth).get_json()) == 1
    assert client.get("/api/v1/chamados", headers=second_auth).get_json() == []
    assert client.get(f"/api/v1/chamados/{ticket_id}", headers=second_auth).status_code == 403
    assert len(client.get("/api/v1/chamados", headers=admin_auth).get_json()) == 1


def test_only_admin_changes_status_and_records_history(client, make_user, api_login, catalog):
    owner, _ = make_user(email="dono@test.com", area="Infraestrutura")
    other, _ = make_user(email="colega@test.com", area="Infraestrutura")
    admin, _ = make_user(role="Admin", email="admin@test.com")
    owner_auth = api_login(owner)
    other_auth = api_login(other)
    admin_auth = api_login(admin)
    ticket_id = _create(client, owner_auth, catalog).get_json()["id"]
    path = f"/api/v1/chamados/{ticket_id}/status"
    for headers in (owner_auth, other_auth):
        assert (
            client.post(path, json={"status": "EM_ANDAMENTO"}, headers=headers).status_code == 403
        )
    assert (
        client.post(path, json={"status": "EM_ANDAMENTO"}, headers=admin_auth).get_json()["status"]
        == "Em andamento"
    )
    assert (
        client.post(
            path, json={"status": "FINALIZADO", "motivo": "Reparo concluído"}, headers=admin_auth
        ).get_json()["status"]
        == "Finalizado"
    )
    history = client.get(f"/api/v1/chamados/{ticket_id}/historico", headers=admin_auth).get_json()
    assert [(row["previous_status"], row["new_status"]) for row in history] == [
        ("Em aberto", "Em andamento"),
        ("Em andamento", "Finalizado"),
    ]
    assert history[-1]["motivo"] == "Reparo concluído"
    assert client.post(path, json={"status": "EM_ANDAMENTO"}, headers=admin_auth).status_code == 400


def test_cancel_deletes_open_ticket_and_comments(client, make_user, api_login, catalog):
    owner, _ = make_user(email="dono@test.com")
    other, _ = make_user(email="outro@test.com")
    owner_auth = api_login(owner)
    other_auth = api_login(other)
    ticket_id = _create(client, owner_auth, catalog).get_json()["id"]
    path = f"/api/v1/chamados/{ticket_id}"
    assert (
        client.post(
            f"{path}/comentarios", json={"content": "Detalhe"}, headers=owner_auth
        ).status_code
        == 201
    )
    assert client.delete(path, headers=other_auth).status_code == 403
    assert client.delete(path, headers=owner_auth).status_code == 204
    assert client.get(path, headers=owner_auth).status_code == 404


def test_cannot_cancel_after_treatment_starts(client, make_user, api_login, catalog):
    owner, _ = make_user(email="dono@test.com")
    admin, _ = make_user(role="Admin", email="admin@test.com")
    owner_auth = api_login(owner)
    admin_auth = api_login(admin)
    ticket_id = _create(client, owner_auth, catalog).get_json()["id"]
    path = f"/api/v1/chamados/{ticket_id}"
    client.post(f"{path}/status", json={"status": "EM_ANDAMENTO"}, headers=admin_auth)
    assert client.delete(path, headers=owner_auth).status_code == 400
    assert client.get(path, headers=owner_auth).status_code == 200


def test_admin_filters_by_date_and_sector(client, make_user, api_login, catalog, areas):
    owner, _ = make_user(email="dono@test.com")
    admin, _ = make_user(role="Admin", email="admin@test.com")
    owner_auth = api_login(owner)
    admin_auth = api_login(admin)
    _create(client, owner_auth, catalog, title="Antigo", reported_date="2026-11-04")
    _create(client, owner_auth, catalog, title="Atual", reported_date="2026-11-05")
    _create(
        client,
        owner_auth,
        catalog,
        title="Outro setor",
        category_id=areas["RH"],
        reported_date="2026-11-05",
    )
    all_tickets = client.get("/api/v1/chamados", headers=admin_auth).get_json()
    assert [ticket["title"] for ticket in all_tickets][-1] == "Antigo"
    by_date = client.get("/api/v1/chamados?data=2026-11-05", headers=admin_auth).get_json()
    assert {ticket["title"] for ticket in by_date} == {"Atual", "Outro setor"}
    by_sector = client.get(
        f"/api/v1/chamados?categoria_id={areas['RH']}", headers=admin_auth
    ).get_json()
    assert [ticket["title"] for ticket in by_sector] == ["Outro setor"]
