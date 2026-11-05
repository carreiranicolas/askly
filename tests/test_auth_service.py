"""Testes da camada de autenticação (`app/services/auth_service.py`).

Cobre as regras de cadastro, login e troca de senha — sem passar pela web/API,
direto no serviço. Pontos validados:
  - `register` valida nome/e-mail/senha e impede e-mail duplicado;
  - quando o cargo não é informado, o padrão é Solicitante (cadastro público);
  - `authenticate` rejeita senha errada e conta desativada;
  - `change_password` exige a senha atual correta e tamanho mínimo da nova.
"""

import pytest

from app.services import ROLE_SOLICITANTE, auth_service
from app.services.exceptions import AuthError, ConflictError, ValidationError


def test_register_default_role_e_solicitante(app):
    """Cadastro sem cargo explícito entra como Solicitante (política pública)."""
    with app.app_context():
        user = auth_service.register("Fulano", "fulano@test.com", "Senha123")
        assert user.cargo.name == ROLE_SOLICITANTE


def test_register_email_duplicado_gera_conflito(app):
    """Não pode haver dois usuários com o mesmo e-mail."""
    with app.app_context():
        auth_service.register("Ana", "dup@test.com", "Senha123")
        with pytest.raises(ConflictError):
            auth_service.register("Bia", "dup@test.com", "Senha123")


def test_register_email_invalido_gera_validacao(app):
    """E-mail malformado deve ser rejeitado na validação."""
    with app.app_context():
        with pytest.raises(ValidationError):
            auth_service.register("Fulano", "nao-e-email", "Senha123")


def test_register_senha_curta_gera_validacao(app):
    """Senha abaixo do mínimo (8 caracteres) deve ser rejeitada."""
    with app.app_context():
        with pytest.raises(ValidationError):
            auth_service.register("Fulano", "curta@test.com", "Abc1234")


def test_register_senha_fraca_sem_maiuscula_gera_validacao(app):
    """Senha sem letra maiúscula deve ser rejeitada."""
    with app.app_context():
        with pytest.raises(ValidationError):
            auth_service.register("Fulano", "fraca@test.com", "senha123")


def test_register_senha_fraca_sem_numero_gera_validacao(app):
    """Senha sem número deve ser rejeitada."""
    with app.app_context():
        with pytest.raises(ValidationError):
            auth_service.register("Fulano", "fraca2@test.com", "SenhaForte")


def test_authenticate_sucesso(app, make_user):
    """Credenciais corretas devolvem o usuário autenticado."""
    email, password = make_user(role="Solicitante", email="ok@test.com")
    with app.app_context():
        user = auth_service.authenticate(email, password)
        assert user.email == email


def test_authenticate_senha_errada_gera_auth_error(app, make_user):
    email, _ = make_user(role="Solicitante", email="x@test.com")
    with app.app_context():
        with pytest.raises(AuthError):
            auth_service.authenticate(email, "senha-errada")


def test_authenticate_conta_desativada_e_bloqueada(app, make_user):
    """Conta inativa não autentica mesmo com a senha certa."""
    email, password = make_user(role="Solicitante", email="off@test.com")
    with app.app_context():
        from app.extensions import db
        from app.models.user import Usuario

        user = Usuario.query.filter_by(email=email).first()
        user.is_active = False
        db.session.commit()
        with pytest.raises(AuthError):
            auth_service.authenticate(email, password)


def test_authenticate_area_desativada_e_bloqueada(app, make_user, areas):
    """Usuário de área inativa não autentica (exceto Admin)."""
    email, password = make_user(role="Atendente", email="area-off@test.com", area="RH")
    with app.app_context():
        from app.extensions import db
        from app.models.category import Categoria

        area = Categoria.query.filter_by(name="RH").first()
        area.is_active = False
        db.session.commit()
        with pytest.raises(AuthError, match="área está desativada"):
            auth_service.authenticate(email, password)


def test_change_password_exige_senha_atual_correta(app, make_user):
    """Trocar a senha informando a senha atual ERRADA deve falhar."""
    email, _ = make_user(role="Solicitante", email="cp@test.com")
    with app.app_context():
        from app.models.user import Usuario

        user = Usuario.query.filter_by(email=email).first()
        with pytest.raises(AuthError):
            auth_service.change_password(user, "errada", "novaSenha123")


def test_change_password_sucesso_altera_hash(app, make_user):
    """Com a senha atual correta, a nova senha passa a valer (e a antiga não)."""
    email, password = make_user(role="Solicitante", email="cp2@test.com")
    with app.app_context():
        from app.models.user import Usuario

        user = Usuario.query.filter_by(email=email).first()
        auth_service.change_password(user, password, "novaSenha123")
        # A nova senha valida; a antiga não vale mais.
        assert user.check_password("novaSenha123") is True
        assert user.check_password(password) is False
