from flask_restx import Namespace, Resource, fields

from app.api.common import error_model
from app.api.security import roles_required, token_required
from app.services import ROLE_ADMIN, catalog_service

ns = Namespace("Cargos", description="Cargos / perfis de acesso.")

cargo_model = ns.model(
    "Cargo",
    {
        "id": fields.Integer(readonly=True, example=1),
        "name": fields.String(example="Solicitante"),
        "description": fields.String(example="Abre e acompanha os próprios chamados."),
        "is_active": fields.Boolean(example=True),
    },
)

cargo_input = ns.model(
    "CargoInput",
    {
        "name": fields.String(required=True, example="Supervisor"),
        "description": fields.String(required=True, example="Acompanha indicadores da equipe."),
        "is_active": fields.Boolean(example=True),
    },
)

err = error_model(ns)


@ns.route("")
class CargoList(Resource):
    @ns.doc(security="Bearer")
    @ns.marshal_list_with(cargo_model)
    @token_required
    def get(self):
        """Lista os cargos."""
        return catalog_service.list_cargos()

    @ns.doc(security="Bearer")
    @ns.expect(cargo_input, validate=True)
    @ns.response(409, "Nome já existe", err)
    @ns.marshal_with(cargo_model, code=201)
    @roles_required(ROLE_ADMIN)
    def post(self):
        """Cria um cargo (Admin)."""
        d = ns.payload
        obj = catalog_service.create_cargo(d["name"], d["description"], d.get("is_active", True))
        return obj, 201


@ns.route("/<int:cargo_id>")
class CargoItem(Resource):
    @ns.doc(security="Bearer")
    @ns.response(404, "Não encontrado", err)
    @ns.marshal_with(cargo_model)
    @token_required
    def get(self, cargo_id):
        """Detalha um cargo."""
        return catalog_service.get_cargo(cargo_id)

    @ns.doc(security="Bearer")
    @ns.expect(cargo_input)
    @ns.marshal_with(cargo_model)
    @roles_required(ROLE_ADMIN)
    def put(self, cargo_id):
        """Atualiza um cargo (Admin)."""
        d = ns.payload or {}
        return catalog_service.update_cargo(
            cargo_id, d.get("name"), d.get("description"), d.get("is_active")
        )

    @ns.doc(security="Bearer")
    @ns.response(204, "Removido")
    @roles_required(ROLE_ADMIN)
    def delete(self, cargo_id):
        """Remove um cargo (Admin)."""
        catalog_service.delete_cargo(cargo_id)
        return "", 204
