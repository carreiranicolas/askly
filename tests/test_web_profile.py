"""Testes das rotas WEB de perfil/configurações (`app/routes/profile.py`).

Cobre a página de configurações e a troca de senha pelo formulário web:
  - a tela exige login e renderiza (200);
  - trocar com a senha atual ERRADA não altera nada (mostra erro);
  - trocar com a senha atual correta efetiva a nova senha.
"""

from app.models.user import Usuario


def test_configuracoes_exige_login(client):
    """Sem login, /configuracoes redireciona para a tela de login."""
    resp = client.get("/configuracoes/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_configuracoes_renderiza_para_logado(client, make_user, web_login):
    email, _ = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)
    assert client.get("/configuracoes/").status_code == 200


def test_alterar_senha_atual_errada_nao_muda(app, client, make_user, web_login):
    """Senha atual incorreta: redireciona (com flash de erro) e a senha não muda."""
    email, password = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)

    resp = client.post(
        "/configuracoes/senha",
        data={
            "current_password": "errada",
            "new_password": "novaSenha123",
            "confirm_new_password": "novaSenha123",
        },
    )
    assert resp.status_code == 302
    with app.app_context():
        user = Usuario.query.filter_by(email=email).first()
        # A senha original continua valendo (a troca foi recusada).
        assert user.check_password(password) is True


def test_alterar_senha_sucesso(app, client, make_user, web_login):
    """Senha atual correta + nova válida: a nova senha passa a valer."""
    email, password = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)

    resp = client.post(
        "/configuracoes/senha",
        data={
            "current_password": password,
            "new_password": "novaSenha123",
            "confirm_new_password": "novaSenha123",
        },
    )
    assert resp.status_code == 302
    with app.app_context():
        user = Usuario.query.filter_by(email=email).first()
        assert user.check_password("novaSenha123") is True
