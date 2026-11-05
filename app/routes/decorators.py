from functools import wraps

from flask import abort
from flask_login import current_user, login_required

from app.services import ROLE_ADMIN, role_of


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if role_of(current_user) != ROLE_ADMIN:
            abort(403)
        return fn(*args, **kwargs)

    return wrapper
