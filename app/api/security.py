import datetime
import functools

import jwt
from flask import current_app, g, request

from app.extensions import db
from app.models.user import Usuario
from app.services.exceptions import AuthError, PermissionDenied

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "askly"
JWT_AUDIENCE = "askly-api"
TOKEN_TTL_HOURS = 8


def generate_token(user):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user.id),
        "name": user.name,
        "role": user.cargo.name if user.cargo else None,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + datetime.timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=JWT_ALGORITHM)


def _decode(token):
    return jwt.decode(
        token,
        current_app.config["SECRET_KEY"],
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )


def _extract_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer ") :].strip()


def current_user():
    return getattr(g, "current_user", None)


def token_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            raise AuthError("Token de autenticação ausente.")
        try:
            payload = _decode(token)
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expirado. Faça login novamente.")
        except jwt.InvalidTokenError:
            raise AuthError("Token inválido.")

        user = db.session.get(Usuario, int(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthError("Usuário inválido ou desativado.")

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @functools.wraps(fn)
        @token_required
        def wrapper(*args, **kwargs):
            user = current_user()
            if user.cargo is None or user.cargo.name not in roles:
                raise PermissionDenied("Permissão insuficiente para esta ação.")
            return fn(*args, **kwargs)

        return wrapper

    return decorator
