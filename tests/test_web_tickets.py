"""Testes das rotas WEB de chamados (`app/routes/tickets.py`).

Diferente de `test_tickets.py` (que bate na API REST com JWT), aqui exercitamos
a interface web com sessão por cookie (`web_login`). Validamos que as telas
renderizam e que os formulários (abrir chamado, comentar, mudar status,
atribuir e cancelar) chamam o serviço e redirecionam corretamente.

Convenção do projeto: as rotas web seguem o padrão Post/Redirect/Get — um POST
bem-sucedido responde 302 (redirect) e a mensagem aparece como flash.
"""

from app.models.ticket import StatusEnum
from app.models.user import Usuario


def _user_id(app, email):
    with app.app_context():
        return Usuario.query.filter_by(email=email).first().id


def _abrir_chamado_web(client, catalog, titulo="Sem acesso ao ERP"):
    """Abre um chamado pelo formulário web e devolve a resposta do POST."""
    return client.post(
        "/chamados/novo",
        data={
            "title": titulo,
            "description": "Descrição do problema",
            "category_id": str(catalog["categoria"]),
            "priority_id": str(catalog["prioridade"]),
            "item_name": "Computador",
            "equipment_tag": "PAT-123",
            "reported_date": "2026-11-05",
        },
        follow_redirects=False,
    )


def test_listar_exige_login(client):
    """Sem estar logado, /chamados redireciona para a tela de login."""
    resp = client.get("/chamados/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_novo_get_renderiza_formulario(client, make_user, web_login):
    """A tela de abertura de chamado deve renderizar (200) para quem está logado."""
    email, _ = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)
    assert client.get("/chamados/novo").status_code == 200


def test_novo_post_cria_e_redireciona_para_detalhe(client, make_user, web_login, catalog):
    """Abrir um chamado válido deve redirecionar (302) para a página de detalhe."""
    email, _ = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)
    resp = _abrir_chamado_web(client, catalog)
    assert resp.status_code == 302
    assert "/chamados/" in resp.headers["Location"]


def test_listar_mostra_chamado_aberto(client, make_user, web_login, catalog):
    """Depois de abrir um chamado, ele aparece na listagem do solicitante."""
    email, _ = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)
    _abrir_chamado_web(client, catalog, titulo="Impressora travada")
    page = client.get("/chamados/", follow_redirects=True)
    assert page.status_code == 200
    assert b"Impressora travada" in page.data
    assert "Atribuídos a mim" not in page.get_data(as_text=True)
    assert "Todos os chamados" not in page.get_data(as_text=True)


def test_listar_filtro_por_status(client, make_user, web_login, catalog):
    """Filtro de status na listagem web restringe os resultados."""
    email, _ = make_user(role="Solicitante", email="sol@test.com", area="Infraestrutura")
    web_login(email)
    _abrir_chamado_web(client, catalog, titulo="Chamado na fila")
    page = client.get("/chamados/?status=FINALIZADO", follow_redirects=True)
    assert page.status_code == 200
    assert b"Chamado na fila" not in page.data
    page_aberto = client.get("/chamados/?status=EM_ABERTO", follow_redirects=True)
    assert b"Chamado na fila" in page_aberto.data
    page_atendimento = client.get("/chamados/?status=EM_ANDAMENTO", follow_redirects=True)
    assert b"Chamado na fila" not in page_atendimento.data


def test_adicionar_comentario_web(client, make_user, web_login, catalog):
    """Comentar em um chamado próprio deve redirecionar de volta ao detalhe."""
    email, _ = make_user(role="Solicitante", email="sol@test.com")
    web_login(email)
    loc = _abrir_chamado_web(client, catalog).headers["Location"]
    resp = client.post(f"{loc}/comentario", data={"content": "Algum detalhe"})
    assert resp.status_code == 302


def test_listar_filtro_sla_atrasado(client, make_user, web_login, catalog, app):
    """Filtro SLA na listagem web não deve gerar erro e deve listar atrasados."""
    from datetime import datetime, timedelta, timezone

    from app.extensions import db
    from app.models.ticket import Chamado
    from app.services import ticket_service

    sol_email, _ = make_user(role="Solicitante", email="sol@test.com", area="Infraestrutura")
    tec_email, _ = make_user(role="Atendente", email="tec-sla@test.com", area="Infraestrutura")
    adm_email, _ = make_user(role="Admin", email="adm-sla@test.com")
    web_login(sol_email)
    _abrir_chamado_web(client, catalog, titulo="Chamado atrasado SLA")

    with app.app_context():
        ticket = Chamado.query.filter_by(title="Chamado atrasado SLA").first()
        adm = Usuario.query.filter_by(email=adm_email).first()
        tec = Usuario.query.filter_by(email=tec_email).first()
        ticket_service.assign_ticket(adm, ticket.id, tec.id)
        ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=10)
        db.session.commit()

    page = client.get("/chamados/?sla=atrasado", follow_redirects=True)
    assert page.status_code == 200
    assert b"Chamado atrasado SLA" in page.data

    page_ok = client.get("/chamados/?sla=no_prazo", follow_redirects=True)
    assert page_ok.status_code == 200
    assert b"Chamado atrasado SLA" not in page_ok.data


def test_fluxo_atribuir_e_mudar_status_web(app, client, make_user, web_login, catalog):
    """Fluxo de staff pela web: atribuir responsável e então mudar o status.

    catalog["categoria"] é "Infraestrutura" (1ª em ordem alfabética no seed),
    então o atendente precisa ser dessa área para poder receber o chamado.
    """
    sol_email, _ = make_user(role="Solicitante", email="sol@test.com")
    make_user(role="Atendente", email="tec@test.com", area="Infraestrutura")
    adm_email, _ = make_user(role="Admin", email="adm@test.com")

    # Solicitante abre o chamado.
    web_login(sol_email)
    loc = _abrir_chamado_web(client, catalog).headers["Location"]
    ticket_id = loc.rstrip("/").split("/")[-1]
    client.post("/logout")

    # Admin assume a sessão, atribui o atendente e move o status.
    web_login(adm_email)
    tec_id = _user_id(app, "tec@test.com")
    assign = client.post(f"/chamados/{ticket_id}/atribuir", data={"atendente_id": str(tec_id)})
    assert assign.status_code == 302

    status = client.post(
        f"/chamados/{ticket_id}/status",
        data={"status": StatusEnum.FINALIZADO.name, "motivo": "Aguardando cliente"},
    )
    assert status.status_code == 302


def test_web_cancel_excludes_open_ticket(app, client, make_user, web_login, catalog):
    from app.models.ticket import Chamado

    owner, _ = make_user(email="dono-cancel@test.com")
    web_login(owner)
    path = _abrir_chamado_web(client, catalog).headers["Location"]
    detail = client.get(path).get_data(as_text=True)
    assert "Cancelar e excluir" in detail
    assert "PAT-123" in detail
    assert client.post(f"{path}/cancelar").status_code == 302
    with app.app_context():
        assert Chamado.query.count() == 0
