from flask_restx import Namespace, Resource, fields

from app.api.common import error_model
from app.api.security import roles_required
from app.services import ROLE_ADMIN, user_service

ns = Namespace("Usuários", description="Gestão de usuários (apenas Admin).")

usuario_model = ns.model(
    "Usuario",
    {
        "id": fields.Integer(readonly=True, example=1),
        "name": fields.String(example="Maria Silva"),
        "email": fields.String(example="maria.silva@empresa.com"),
        "role_id": fields.Integer(example=1),
        "role_name": fields.String(attribute="cargo.name", example="Solicitante"),
        "area_id": fields.Integer(example=7),
        "area_name": fields.String(attribute="area.name", example="RH"),
        "is_active": fields.Boolean(example=True),
        "created_at": fields.DateTime(example="2026-05-26T14:30:00"),
    },
)

usuario_update = ns.model(
    "UsuarioUpdate",
    {
        "name": fields.String(example="Maria S. Andrade"),
        "role_id": fields.Integer(example=2),
        "area_id": fields.Integer(example=7, description="Área do usuário."),
        "is_active": fields.Boolean(example=False),
    },
)

err = error_model(ns)


@ns.route("")
class UsuarioList(Resource):
    @ns.doc(security="Bearer")
    @ns.response(403, "Permissão insuficiente", err)
    @ns.marshal_list_with(usuario_model)
    @roles_required(ROLE_ADMIN)
    def get(self):
        """Lista todos os usuários."""
        return user_service.list_users()


@ns.route("/<int:user_id>")
class UsuarioItem(Resource):
    @ns.doc(security="Bearer")
    @ns.response(404, "Não encontrado", err)
    @ns.marshal_with(usuario_model)
    @roles_required(ROLE_ADMIN)
    def get(self, user_id):
        """Detalha um usuário."""
        return user_service.get_user(user_id)

    @ns.doc(security="Bearer")
    @ns.expect(usuario_update)
    @ns.marshal_with(usuario_model)
    @roles_required(ROLE_ADMIN)
    def put(self, user_id):
        """Atualiza nome, cargo ou status (ativo/inativo) de um usuário."""
        data = ns.payload or {}
        return user_service.update_user(
            user_id,
            name=data.get("name"),
            role_id=data.get("role_id"),
            area_id=data.get("area_id"),
            is_active=data.get("is_active"),
        )
