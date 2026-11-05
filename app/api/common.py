from flask_restx import fields


def error_model(ns):
    """Modelo padrão de erro usado nas respostas de falha de cada namespace."""
    return ns.model(
        "Erro",
        {
            "message": fields.String(
                description="Descrição legível do erro.",
                example="E-mail ou senha incorretos.",
            )
        },
    )
