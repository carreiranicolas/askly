def test_cargos_list_requires_token(client):
    assert client.get("/api/v1/cargos").status_code == 401


def test_solicitante_cannot_create_cargo(client, make_user, api_login):
    email, _ = make_user(role="Solicitante", email="sol@test.com")
    resp = client.post(
        "/api/v1/cargos",
        json={"name": "Novo", "description": "x"},
        headers=api_login(email),
    )
    assert resp.status_code == 403


def test_admin_can_create_cargo(client, make_user, api_login):
    email, _ = make_user(role="Admin", email="adm@test.com")
    resp = client.post(
        "/api/v1/cargos",
        json={"name": "Supervisor", "description": "x"},
        headers=api_login(email),
    )
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "Supervisor"
