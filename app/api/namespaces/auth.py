from flask_restx import Namespace, Resource, fields

from app.api.common import error_model
from app.api.namespaces.usuarios import usuario_model
from app.api.security import (
    TOKEN_TTL_HOURS,
    current_user,
    generate_token,
    token_required,
)
from app.extensions import limiter
from app.services import auth_service

ns = Namespace("Autenticação", description="Autenticação e registro via JWT.")

login_input = ns.model(
    "LoginInput",
    {
        "email": fields.String(required=True, example="maria.silva@empresa.com"),
        "password": fields.String(required=True, example="senha123"),
    },
)

register_input = ns.model(
    "RegisterInput",
    {
        "name": fields.String(required=True, example="Maria Silva"),
        "email": fields.String(required=True, example="maria.silva@empresa.com"),
        "password": fields.String(required=True, example="senha123"),
        "area_id": fields.Integer(
            example=7, description="ID da área do usuário (ver GET /categorias)."
        ),
    },
)

token_output = ns.model(
    "Token",
    {
        "access_token": fields.String(example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."),
        "token_type": fields.String(example="Bearer"),
        "expires_in": fields.Integer(description="Validade em segundos.", example=28800),
        "user": fields.Nested(usuario_model),
    },
)

err = error_model(ns)


def _token_payload(user):
    return {
        "access_token": generate_token(user),
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL_HOURS * 3600,
        "user": user,
    }


@ns.route("/login")
class Login(Resource):
    decorators = [limiter.limit("10 per minute")]

    @ns.expect(login_input, validate=True)
    @ns.response(401, "Credenciais inválidas", err)
    @ns.response(429, "Muitas tentativas. Aguarde antes de tentar novamente.", err)
    @ns.marshal_with(token_output)
    def post(self):
        """Autentica o usuário e devolve um token JWT."""
        data = ns.payload
        user = auth_service.authenticate(data["email"], data["password"])
        return _token_payload(user)


@ns.route("/register")
class Register(Resource):
    decorators = [limiter.limit("10 per minute")]

    @ns.expect(register_input, validate=True)
    @ns.response(409, "E-mail já cadastrado", err)
    @ns.response(429, "Muitas tentativas. Aguarde antes de tentar novamente.", err)
    @ns.marshal_with(token_output, code=201)
    def post(self):
        """Cria uma conta e já devolve o token (entra autenticado).

        O registro público sempre cria usuários com cargo Solicitante.
        Promoção a Admin é feita por um administrador.
        """
        data = ns.payload
        user = auth_service.register(
            data["name"],
            data["email"],
            data["password"],
            role_id=None,
            area_id=data.get("area_id"),
        )
        return _token_payload(user), 201


@ns.route("/me")
class Me(Resource):
    @ns.doc(security="Bearer")
    @ns.response(401, "Não autenticado", err)
    @ns.marshal_with(usuario_model)
    @token_required
    def get(self):
        """Retorna o usuário autenticado."""
        return current_user()
