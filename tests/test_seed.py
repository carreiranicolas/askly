"""Bootstrap das duas contas exigidas em uma instalação nova."""

from pathlib import Path

from dotenv import dotenv_values

from app.models.user import Usuario


def test_seed_creates_initial_accounts_once(app, monkeypatch):
    defaults = dotenv_values(Path(__file__).parents[1] / ".env.example")
    compose = (Path(__file__).parents[1] / "docker-compose.yaml").read_text()
    for prefix in ("ASKLY_ADMIN", "ASKLY_USER"):
        email = defaults[f"{prefix}_EMAIL"]
        assert f"${{{prefix}_EMAIL:-{email}}}" in compose
        monkeypatch.setenv(f"{prefix}_EMAIL", email)
    monkeypatch.setenv("ASKLY_ADMIN_PASSWORD", "AdminSenha123")
    monkeypatch.setenv("ASKLY_USER_PASSWORD", "UsuarioSenha123")
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0
    assert runner.invoke(args=["seed"]).exit_code == 0
    with app.app_context():
        users = Usuario.query.all()
        assert len(users) == 2
        assert {user.email for user in users} == {
            defaults["ASKLY_ADMIN_EMAIL"],
            defaults["ASKLY_USER_EMAIL"],
        }
        assert {user.cargo.name for user in users} == {"Admin", "Solicitante"}
        assert all(user.password != "AdminSenha123" for user in users)
