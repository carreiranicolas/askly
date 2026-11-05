"""Testes das rotas WEB do painel administrativo (`app/routes/admin.py`).

O painel é protegido pelo decorator `admin_required`: qualquer não-admin recebe
403. Validamos esse guard e as ações de admin (listar usuários, alterar
cargo/área de um usuário, criar/ativar/desativar áreas).
"""

from app.extensions import db
from app.models.category import Categoria
from app.models.user import Usuario


def _user_id(app, email):
    with app.app_context():
        return Usuario.query.filter_by(email=email).first().id


def test_painel_usuarios_bloqueado_para_nao_admin(client, make_user, web_login):
    """Solicitante (não-admin) não pode acessar /admin/usuarios => 403."""
    email, _ = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)
    assert client.get("/admin/usuarios").status_code == 403


def test_painel_usuarios_ok_para_admin(client, make_user, web_login):
    """Admin acessa o painel de usuários normalmente => 200."""
    email, _ = make_user(role="Admin", email="adm@test.com")
    web_login(email)
    assert client.get("/admin/usuarios").status_code == 200


def test_admin_altera_cargo_e_area_de_usuario(app, client, make_user, web_login, cargo_ids, areas):
    """Admin promove um Solicitante a Admin e define a área dele."""
    make_user(role="Solicitante", email="sol@test.com", area="RH")
    adm_email, _ = make_user(role="Admin", email="adm@test.com")
    web_login(adm_email)

    sol_id = _user_id(app, "sol@test.com")
    resp = client.post(
        f"/admin/usuarios/{sol_id}/cargo",
        data={
            "role_id": str(cargo_ids["Admin"]),
            "area_id": str(areas["Infraestrutura"]),
        },
    )
    assert resp.status_code == 302  # Post/Redirect/Get

    # Confirma a persistência da promoção.
    with app.app_context():
        atualizado = Usuario.query.filter_by(email="sol@test.com").first()
        assert atualizado.cargo.name == "Admin"
        assert atualizado.area_id == areas["Infraestrutura"]


def test_admin_toggle_usuario_desativa_e_reativa(app, client, make_user, web_login):
    """Admin pode desativar outro usuário e reativá-lo depois."""
    sol_email, _ = make_user(role="Solicitante", email="sol-toggle@test.com")
    adm_email, _ = make_user(role="Admin", email="adm-toggle@test.com")
    web_login(adm_email)

    sol_id = _user_id(app, sol_email)
    resp = client.post(f"/admin/usuarios/{sol_id}/toggle")
    assert resp.status_code == 302
    with app.app_context():
        assert Usuario.query.filter_by(email=sol_email).first().is_active is False

    client.post(f"/admin/usuarios/{sol_id}/toggle")
    with app.app_context():
        assert Usuario.query.filter_by(email=sol_email).first().is_active is True


def test_admin_nao_pode_desativar_propria_conta(app, client, make_user, web_login):
    adm_email, _ = make_user(role="Admin", email="adm-self@test.com")
    web_login(adm_email)
    adm_id = _user_id(app, adm_email)

    resp = client.post(f"/admin/usuarios/{adm_id}/toggle", follow_redirects=True)
    assert resp.status_code == 200
    assert "não pode desativar a própria conta".encode() in resp.data
    with app.app_context():
        assert Usuario.query.filter_by(email=adm_email).first().is_active is True


def test_admin_cria_categoria(app, client, make_user, web_login):
    """Admin cria uma nova área pelo painel; ela passa a existir no banco."""
    adm_email, _ = make_user(role="Admin", email="adm@test.com")
    web_login(adm_email)

    resp = client.post(
        "/admin/categorias/criar",
        data={"name": "Marketing", "description": "Campanhas e mídia"},
    )
    assert resp.status_code == 302
    with app.app_context():
        assert Categoria.query.filter_by(name="Marketing").first() is not None


def test_admin_toggle_categoria_desativa_e_reativa(app, client, make_user, web_login, areas):
    """O toggle inverte o is_active da área (desativa se ativa; ativa se inativa)."""
    adm_email, _ = make_user(role="Admin", email="adm@test.com")
    web_login(adm_email)

    rh_id = areas["RH"]
    # 1º toggle: RH começa ativa => deve ficar inativa.
    client.post(f"/admin/categorias/{rh_id}/toggle")
    with app.app_context():
        assert db.session.get(Categoria, rh_id).is_active is False

    # 2º toggle: agora inativa => deve voltar a ativa.
    client.post(f"/admin/categorias/{rh_id}/toggle")
    with app.app_context():
        assert db.session.get(Categoria, rh_id).is_active is True
