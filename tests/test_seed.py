"""Bootstrap das duas contas exigidas em uma instalação nova."""

from app.models.user import Usuario


def test_seed_creates_initial_accounts_once(app, monkeypatch):
    monkeypatch.setenv("ASKLY_ADMIN_EMAIL", "admin-seed@example.com")
    monkeypatch.setenv("ASKLY_ADMIN_PASSWORD", "AdminSenha123")
    monkeypatch.setenv("ASKLY_USER_EMAIL", "usuario-seed@example.com")
    monkeypatch.setenv("ASKLY_USER_PASSWORD", "UsuarioSenha123")
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0
    assert runner.invoke(args=["seed"]).exit_code == 0
    with app.app_context():
        users = Usuario.query.all()
        assert len(users) == 2
        assert {user.cargo.name for user in users} == {"Admin", "Solicitante"}
        assert all(user.password != "AdminSenha123" for user in users)
