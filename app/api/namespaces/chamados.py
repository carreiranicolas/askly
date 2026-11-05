from flask import request
from flask_restx import Namespace, Resource, fields

from app.api.common import error_model
from app.api.security import current_user, token_required
from app.models.ticket import StatusEnum
from app.services import ticket_service

ns = Namespace("Chamados", description="Chamados, comentários e histórico de status.")

STATUS_NAMES = [s.name for s in StatusEnum]

chamado_model = ns.model(
    "Chamado",
    {
        "id": fields.Integer(readonly=True, example=1),
        "title": fields.String(example="Sem acesso ao ERP"),
        "description": fields.String(
            example="Recebo erro 500 ao logar no Sankhya desde hoje de manhã."
        ),
        "item_name": fields.String(example="Computador"),
        "equipment_tag": fields.String(example="PAT-123"),
        "reported_date": fields.Date(example="2026-11-05"),
        "status": fields.String(attribute="status.value", example="Em andamento"),
        "category_id": fields.Integer(example=2),
        "priority_id": fields.Integer(example=3),
        "requester_id": fields.Integer(example=5),
        "assignee_id": fields.Integer(example=8),
        "created_at": fields.DateTime(example="2026-05-26T14:30:00"),
        "updated_at": fields.DateTime(example="2026-05-26T15:10:00"),
    },
)

chamado_input = ns.model(
    "ChamadoInput",
    {
        "title": fields.String(required=True, example="Sem acesso ao ERP"),
        "description": fields.String(
            required=True, example="Recebo erro 500 ao logar no Sankhya desde hoje."
        ),
        "item_name": fields.String(required=True, example="Computador"),
        "equipment_tag": fields.String(required=True, example="PAT-123"),
        "reported_date": fields.Date(required=True, example="2026-11-05"),
        "category_id": fields.Integer(required=True, example=2),
        "priority_id": fields.Integer(required=True, example=3),
    },
)

status_input = ns.model(
    "StatusInput",
    {
        "status": fields.String(
            required=True,
            example="EM_ANDAMENTO",
            description="Nome do status. Valores possíveis: " + ", ".join(STATUS_NAMES),
        ),
        "motivo": fields.String(
            required=False,
            example="Aguardando retorno do fornecedor.",
            description="Justificativa opcional registrada na auditoria.",
        ),
    },
)

assign_input = ns.model(
    "AssignInput",
    {
        "assignee_id": fields.Integer(
            required=True, example=8, description="ID de um usuário do setor."
        )
    },
)

comentario_model = ns.model(
    "Comentario",
    {
        "id": fields.Integer(readonly=True, example=1),
        "content": fields.String(example="Já estamos verificando com a equipe de infraestrutura."),
        "ticket_id": fields.Integer(example=1),
        "author_id": fields.Integer(example=8),
        "created_at": fields.DateTime(example="2026-05-26T15:00:00"),
    },
)

comentario_input = ns.model(
    "ComentarioInput",
    {
        "content": fields.String(
            required=True,
            example="Já estamos verificando com a equipe de infraestrutura.",
        )
    },
)

historico_model = ns.model(
    "HistoricoStatus",
    {
        "id": fields.Integer(readonly=True, example=1),
        "previous_status": fields.String(example="Em andamento"),
        "new_status": fields.String(example="Finalizado"),
        "motivo": fields.String(example="Aguardando retorno do fornecedor."),
        "changed_by_id": fields.Integer(example=8),
        "created_at": fields.DateTime(example="2026-05-26T15:10:00"),
    },
)

err = error_model(ns)


@ns.route("")
class ChamadoList(Resource):
    @ns.doc(
        security="Bearer",
        params={
            "tipo": "Filtro: meus | atribuidos",
            "categoria_id": "Filtra por área (categoria) do chamado.",
            "q": "Busca textual em título e descrição (case-insensitive).",
            "data": "Filtra pela data informada na abertura (AAAA-MM-DD).",
        },
    )
    @ns.marshal_list_with(chamado_model)
    @token_required
    def get(self):
        """Lista chamados conforme o perfil (Solicitante vê apenas os próprios)."""
        return ticket_service.list_tickets(
            current_user(),
            tipo=request.args.get("tipo"),
            categoria_id=request.args.get("categoria_id", type=int),
            q=request.args.get("q"),
            data=request.args.get("data"),
        )

    @ns.doc(security="Bearer")
    @ns.expect(chamado_input, validate=True)
    @ns.marshal_with(chamado_model, code=201)
    @token_required
    def post(self):
        """Abre um novo chamado (o solicitante é o usuário autenticado)."""
        d = ns.payload
        obj = ticket_service.create_ticket(
            current_user(),
            d["title"],
            d["description"],
            d["category_id"],
            d["priority_id"],
            d["item_name"],
            d["equipment_tag"],
            d["reported_date"],
        )
        return obj, 201


@ns.route("/<int:ticket_id>")
class ChamadoItem(Resource):
    @ns.doc(security="Bearer")
    @ns.response(404, "Não encontrado", err)
    @ns.marshal_with(chamado_model)
    @token_required
    def get(self, ticket_id):
        """Detalha um chamado (respeitando o RBAC)."""
        return ticket_service.get_ticket(current_user(), ticket_id)

    @ns.doc(security="Bearer")
    @ns.response(204, "Chamado cancelado e excluído")
    @token_required
    def delete(self, ticket_id):
        """Quem abriu pode cancelar antes do início do atendimento."""
        ticket_service.cancel_ticket(current_user(), ticket_id)
        return "", 204


@ns.route("/<int:ticket_id>/status")
class ChamadoStatus(Resource):
    @ns.doc(security="Bearer")
    @ns.expect(status_input, validate=True)
    @ns.response(403, "Sem permissão", err)
    @ns.marshal_with(chamado_model)
    @token_required
    def post(self, ticket_id):
        """Altera o status (gera registro de auditoria obrigatório)."""
        d = ns.payload
        return ticket_service.change_status(
            current_user(), ticket_id, d["status"], motivo=d.get("motivo")
        )


@ns.route("/<int:ticket_id>/atribuir")
class ChamadoAssign(Resource):
    @ns.doc(security="Bearer")
    @ns.expect(assign_input, validate=True)
    @ns.response(403, "Sem permissão", err)
    @ns.marshal_with(chamado_model)
    @token_required
    def post(self, ticket_id):
        """Atribui o chamado a um colega da mesma área."""
        d = ns.payload
        return ticket_service.assign_ticket(current_user(), ticket_id, d["assignee_id"])


@ns.route("/<int:ticket_id>/comentarios")
class ChamadoComentarios(Resource):
    @ns.doc(security="Bearer")
    @ns.marshal_list_with(comentario_model)
    @token_required
    def get(self, ticket_id):
        """Lista os comentários do chamado."""
        return ticket_service.list_comments(current_user(), ticket_id)

    @ns.doc(security="Bearer")
    @ns.expect(comentario_input, validate=True)
    @ns.marshal_with(comentario_model, code=201)
    @token_required
    def post(self, ticket_id):
        """Adiciona um comentário ao chamado."""
        d = ns.payload
        obj = ticket_service.add_comment(current_user(), ticket_id, d["content"])
        return obj, 201


@ns.route("/<int:ticket_id>/historico")
class ChamadoHistorico(Resource):
    @ns.doc(security="Bearer")
    @ns.marshal_list_with(historico_model)
    @token_required
    def get(self, ticket_id):
        """Histórico de mudanças de status (auditoria)."""
        return ticket_service.list_history(current_user(), ticket_id)
