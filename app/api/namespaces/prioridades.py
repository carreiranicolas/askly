from flask_restx import Namespace, Resource, fields

from app.api.common import error_model
from app.api.security import roles_required, token_required
from app.services import ROLE_ADMIN, catalog_service

ns = Namespace("Prioridades", description="Prioridades e SLA dos chamados.")

prioridade_model = ns.model(
    "Prioridade",
    {
        "id": fields.Integer(readonly=True, example=3),
        "name": fields.String(example="Alta"),
        "description": fields.String(example="Impacto relevante, requer atenção."),
        "sla_hours": fields.Integer(example=8),
        "is_active": fields.Boolean(example=True),
    },
)

prioridade_input = ns.model(
    "PrioridadeInput",
    {
        "name": fields.String(required=True, example="Emergencial"),
        "description": fields.String(required=True, example="Resposta imediata."),
        "sla_hours": fields.Integer(required=True, example=1),
        "is_active": fields.Boolean(example=True),
    },
)

err = error_model(ns)


@ns.route("")
class PrioridadeList(Resource):
    @ns.doc(security="Bearer")
    @ns.marshal_list_with(prioridade_model)
    @token_required
    def get(self):
        """Lista as prioridades."""
        return catalog_service.list_prioridades()

    @ns.doc(security="Bearer")
    @ns.expect(prioridade_input, validate=True)
    @ns.response(409, "Nome já existe", err)
    @ns.marshal_with(prioridade_model, code=201)
    @roles_required(ROLE_ADMIN)
    def post(self):
        """Cria uma prioridade (Admin)."""
        d = ns.payload
        obj = catalog_service.create_prioridade(
            d["name"], d["description"], d["sla_hours"], d.get("is_active", True)
        )
        return obj, 201


@ns.route("/<int:prioridade_id>")
class PrioridadeItem(Resource):
    @ns.doc(security="Bearer")
    @ns.response(404, "Não encontrada", err)
    @ns.marshal_with(prioridade_model)
    @token_required
    def get(self, prioridade_id):
        """Detalha uma prioridade."""
        return catalog_service.get_prioridade(prioridade_id)

    @ns.doc(security="Bearer")
    @ns.expect(prioridade_input)
    @ns.marshal_with(prioridade_model)
    @roles_required(ROLE_ADMIN)
    def put(self, prioridade_id):
        """Atualiza uma prioridade (Admin)."""
        d = ns.payload or {}
        return catalog_service.update_prioridade(
            prioridade_id,
            d.get("name"),
            d.get("description"),
            d.get("sla_hours"),
            d.get("is_active"),
        )

    @ns.doc(security="Bearer")
    @ns.response(
        204,
        "Desativada (soft delete) — chamados antigos preservam a referência, "
        "mas a prioridade deixa de aparecer nas telas operacionais.",
    )
    @roles_required(ROLE_ADMIN)
    def delete(self, prioridade_id):
        """Desativa uma prioridade (Admin).

        Hard delete não é permitido porque a prioridade tem FK em chamados
        (com cálculo de SLA atrelado). O endpoint marca a prioridade como
        inativa; reative com ``PUT`` (``is_active: true``).
        """
        catalog_service.delete_prioridade(prioridade_id)
        return "", 204
