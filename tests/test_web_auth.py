def test_cadastro_auto_login(client, areas):
    # O cadastro público não escolhe cargo: o novo usuário entra como Solicitante.
    resp = client.post(
        "/cadastro",
        data={
            "name": "Joao Web",
            "email": "joao@test.com",
            "password": "Senha123",
            "confirm_password": "Senha123",
            "area": str(areas["RH"]),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    # Já autenticado: home redireciona para a lista de chamados.
    home = client.get("/")
    assert home.status_code == 302
    assert "/chamados" in home.headers["Location"]


def test_cadastro_default_role_is_solicitante(client, areas):
    """Quem se cadastra pelo formulário público entra como Solicitante.

    Promover a Atendente/Admin é uma ação do administrador no painel
    `/admin/usuarios` — manter Atendente como default expandiria
    indevidamente a visibilidade do recém-cadastrado para toda a área.
    """
    from app.models.user import Usuario

    client.post(
        "/cadastro",
        data={
            "name": "Pessoa RH",
            "email": "pessoa@test.com",
            "password": "Senha123",
            "confirm_password": "Senha123",
            "area": str(areas["RH"]),
        },
        follow_redirects=False,
    )
    user = Usuario.query.filter_by(email="pessoa@test.com").first()
    assert user is not None
    assert user.cargo.name == "Solicitante"
    assert user.area_id == areas["RH"]


def test_login_logout_flow(client, make_user):
    email, password = make_user(role="Solicitante", email="web@test.com")
    resp = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Logout é POST-only.
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302


def test_login_wrong_password_shows_form(client, make_user):
    email, _ = make_user(role="Solicitante", email="web@test.com")
    resp = client.post(
        "/login",
        data={"email": email, "password": "errada"},
        follow_redirects=False,
    )
    assert resp.status_code == 200  # re-renderiza o form, sem redirecionar
