"""Testes da camada de usuários (`app/services/user_service.py`).

Cobre as consultas de staff usadas na atribuição de chamados e a atualização
de usuário pelo admin. Pontos sensíveis exercitados aqui:
  - `list_staff_for_area` deve devolver apenas staff ATIVO da área (é a fonte
    do seletor de responsável; um inativo não pode receber chamados);
  - `update_user` valida cargo/área inexistentes antes de gravar.
"""

import pytest

from app.models.user import Usuario
from app.services import user_service
from app.services.exceptions import NotFoundError, ValidationError


def _user_id(email):
    """Atalho: id do usuário pelo e-mail (dentro de um contexto já ativo)."""
    return Usuario.query.filter_by(email=email).first().id


def test_list_users_ordena_por_nome(app, make_user):
    """list_users deve retornar todos os usuários em ordem alfabética de nome."""
    make_user(role="Solicitante", email="zulmira@test.com", name="Zulmira")
    make_user(role="Admin", email="ana@test.com", name="Ana")
    with app.app_context():
        nomes = [u.name for u in user_service.list_users()]
        assert nomes == sorted(nomes)


def test_list_staff_so_traz_atendentes_e_admins(app, make_user):
    """Staff = Atendente + Admin. Solicitante NÃO é staff e fica de fora."""
    make_user(role="Solicitante", email="sol@test.com", area="RH")
    make_user(role="Atendente", email="tec@test.com", area="RH")
    make_user(role="Admin", email="adm@test.com")
    with app.app_context():
        emails = {u.email for u in user_service.list_staff()}
        assert "tec@test.com" in emails
        assert "adm@test.com" in emails
        assert "sol@test.com" not in emails  # solicitante não é staff


def test_list_staff_for_area_filtra_area_e_inativos(app, make_user, areas):
    """O seletor de responsável oferece todos os usuários ATIVOS da área."""
    make_user(role="Solicitante", email="rh_sol@test.com", area="RH")
    make_user(role="Atendente", email="rh@test.com", area="RH")
    make_user(role="Atendente", email="infra@test.com", area="Infraestrutura")
    make_user(role="Atendente", email="rh_inativo@test.com", area="RH")

    with app.app_context():
        inativo = Usuario.query.filter_by(email="rh_inativo@test.com").first()
        inativo.is_active = False
        from app.extensions import db

        db.session.commit()

        rh_users = user_service.list_staff_for_area(areas["RH"])
        emails = {u.email for u in rh_users}
        assert emails == {"rh_sol@test.com", "rh@test.com"}


def test_list_staff_for_area_sem_area_retorna_vazio(app):
    """Sem área (None) não há a quem atribuir: retorna lista vazia."""
    with app.app_context():
        assert user_service.list_staff_for_area(None) == []


def test_get_user_inexistente_gera_not_found(app):
    with app.app_context():
        with pytest.raises(NotFoundError):
            user_service.get_user(999999)


def test_update_user_promove_cargo(app, make_user, cargo_ids):
    """Admin promovendo um Solicitante a Admin deve trocar o cargo."""
    make_user(role="Solicitante", email="sol@test.com", area="RH")
    with app.app_context():
        uid = _user_id("sol@test.com")
        atualizado = user_service.update_user(uid, role_id=cargo_ids["Admin"])
        assert atualizado.cargo.name == "Admin"


def test_update_user_cargo_inexistente_gera_validacao(app, make_user):
    """Passar um role_id que não existe deve falhar com ValidationError."""
    make_user(role="Solicitante", email="sol@test.com")
    with app.app_context():
        uid = _user_id("sol@test.com")
        with pytest.raises(ValidationError):
            user_service.update_user(uid, role_id=999999)


def test_update_user_rejeita_cargo_legado(app, make_user, cargo_ids):
    """O cargo legado Atendente não pode ser atribuído no painel."""
    import pytest

    from app.models.user import Usuario
    from app.services import user_service
    from app.services.exceptions import ValidationError

    make_user(role="Solicitante", email="sol-role@test.com")
    with app.app_context():
        uid = Usuario.query.filter_by(email="sol-role@test.com").first().id
        with pytest.raises(ValidationError):
            user_service.update_user(uid, role_id=cargo_ids["Atendente"])


def test_last_active_admin_cannot_be_demoted(app, make_user, cargo_ids):
    email, _ = make_user(role="Admin", email="only-admin@test.com")
    with app.app_context():
        uid = _user_id(email)
        with pytest.raises(ValidationError):
            user_service.update_user(uid, role_id=cargo_ids["Solicitante"])


def test_toggle_user_active_bloqueia_proprio_usuario(app, make_user):
    import pytest

    from app.models.user import Usuario
    from app.services import user_service
    from app.services.exceptions import ValidationError

    adm_email, _ = make_user(role="Admin", email="adm-toggle-svc@test.com")
    with app.app_context():
        adm = Usuario.query.filter_by(email=adm_email).first()
        with pytest.raises(ValidationError):
            user_service.toggle_user_active(adm, adm.id)


def test_update_user_area_inexistente_gera_validacao(app, make_user):
    """Passar um area_id que não existe deve falhar com ValidationError."""
    make_user(role="Atendente", email="tec@test.com", area="RH")
    with app.app_context():
        uid = _user_id("tec@test.com")
        with pytest.raises(ValidationError):
            user_service.update_user(uid, area_id=999999)
