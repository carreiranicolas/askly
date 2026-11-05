class ServiceError(Exception):
    """Erro de domínio. Web e API traduzem para resposta apropriada."""

    status_code = 400

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class ValidationError(ServiceError):
    status_code = 400


class AuthError(ServiceError):
    status_code = 401


class PermissionDenied(ServiceError):
    status_code = 403


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409
