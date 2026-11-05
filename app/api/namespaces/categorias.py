from flask_restx import Namespace, Resource, fields

from app.api.common import error_model
from app.api.security import roles_required, token_required
from app.services import ROLE_ADMIN, catalog_service

ns = Namespace("Áreas", description="Áreas / departamentos responsáveis pelos chamados.")

categoria_model = ns.model(
    "Categoria",
    {
        "id": fields.Integer(readonly=True, example=2),
        "name": fields.String(example="Sistemas"),
        "description": fields.String(example="Aplicações internas e ERPs."),
        "is_active": fields.Boolean(example=True),
    },
)

categoria_input = ns.model(
    "CategoriaInput",
    {
        "name": fields.String(required=True, example="Telefonia"),
        "description": fields.String(required=True, example="Ramais e VoIP."),
        "is_active": fields.Boolean(example=True),
    },
)

err = error_model(ns)


@ns.route("")
class CategoriaList(Resource):
    @ns.doc(security="Bearer")
    @ns.marshal_list_with(categoria_model)
    @token_required
    def get(self):
        """Lista as categorias."""
        return catalog_service.list_categorias()

    @ns.doc(security="Bearer")
    @ns.expect(categoria_input, validate=True)
    @ns.response(409, "Nome já existe", err)
    @ns.marshal_with(categoria_model, code=201)
    @roles_required(ROLE_ADMIN)
    def post(self):
        """Cria uma categoria (Admin)."""
        d = ns.payload
        obj = catalog_service.create_categoria(
            d["name"], d["description"], d.get("is_active", True)
        )
        return obj, 201


@ns.route("/<int:categoria_id>")
class CategoriaItem(Resource):
    @ns.doc(security="Bearer")
    @ns.response(404, "Não encontrada", err)
    @ns.marshal_with(categoria_model)
    @token_required
    def get(self, categoria_id):
        """Detalha uma categoria."""
        return catalog_service.get_categoria(categoria_id)

    @ns.doc(security="Bearer")
    @ns.expect(categoria_input)
    @ns.marshal_with(categoria_model)
    @roles_required(ROLE_ADMIN)
    def put(self, categoria_id):
        """Atualiza uma categoria (Admin)."""
        d = ns.payload or {}
        return catalog_service.update_categoria(
            categoria_id, d.get("name"), d.get("description"), d.get("is_active")
        )

    @ns.doc(security="Bearer")
    @ns.response(
        204,
        "Desativada (soft delete) — chamados e usuários antigos preservam a "
        "referência, mas a área deixa de aparecer nas telas operacionais.",
    )
    @roles_required(ROLE_ADMIN)
    def delete(self, categoria_id):
        """Desativa uma área (Admin).

        Hard delete não é permitido porque a área tem FK em chamados e em
        usuários — apagá-la quebraria o histórico. O endpoint marca a área
        como inativa; reative com ``PUT`` (``is_active: true``).
        """
        catalog_service.delete_categoria(categoria_id)
        return "", 204
