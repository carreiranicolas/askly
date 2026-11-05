def test_register_returns_token_and_user(client, cargo_ids):
    """Registro público sempre cria usuário como Solicitante (role_id não aceito)."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Maria",
            "email": "maria@test.com",
            "password": "Senha123",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["access_token"]
    assert body["user"]["email"] == "maria@test.com"
    assert body["user"]["role_name"] == "Solicitante"


def test_register_duplicate_email_conflict(client, make_user, cargo_ids):
    make_user(role="Solicitante", email="dup@test.com")
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Outro",
            "email": "dup@test.com",
            "password": "Senha123",
        },
    )
    assert resp.status_code == 409


def test_register_invalid_email(client, cargo_ids):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "X",
            "email": "naoeumemail",
            "password": "Senha123",
        },
    )
    assert resp.status_code == 400


def test_login_ok_and_bad(client, make_user):
    email, password = make_user(role="Solicitante", email="login@test.com")
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": password}).status_code
        == 200
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": "errada"}).status_code
        == 401
    )


def test_me_requires_token(client, make_user, api_login):
    assert client.get("/api/v1/auth/me").status_code == 401
    email, _ = make_user(role="Solicitante", email="me@test.com")
    resp = client.get("/api/v1/auth/me", headers=api_login(email))
    assert resp.status_code == 200
    assert resp.get_json()["email"] == email
