from flask import Blueprint
from flask_restx import Api

from app.services.exceptions import ServiceError

from .namespaces.auth import ns as auth_ns
from .namespaces.cargos import ns as cargos_ns
from .namespaces.categorias import ns as categorias_ns
from .namespaces.chamados import ns as chamados_ns
from .namespaces.prioridades import ns as prioridades_ns
from .namespaces.usuarios import ns as usuarios_ns

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

authorizations = {
    "Bearer": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Informe: **Bearer &lt;token&gt;** (obtido em POST /auth/login).",
    }
}

api = Api(
    api_bp,
    version="1.0",
    title="Askly API",
    description=(
        "API REST para gestão de chamados internos (service desk).\n\n"
        "**Autenticação:** JWT via header `Authorization: Bearer <token>`, "
        "obtido em `POST /auth/login`.\n\n"
        "**Controle de acesso (RBAC):** as permissões variam conforme o "
        "perfil do usuário (Admin ou Solicitante) e a área "
        "responsável pelo chamado."
    ),
    doc="/docs",
    authorizations=authorizations,
    ordered=True,
)

api.add_namespace(auth_ns, path="/auth")
api.add_namespace(chamados_ns, path="/chamados")
api.add_namespace(categorias_ns, path="/categorias")
api.add_namespace(prioridades_ns, path="/prioridades")
api.add_namespace(cargos_ns, path="/cargos")
api.add_namespace(usuarios_ns, path="/usuarios")


@api.errorhandler(ServiceError)
def handle_service_error(error):
    """Traduz erros de domínio para JSON com o status apropriado."""
    return {"message": error.message}, error.status_code
