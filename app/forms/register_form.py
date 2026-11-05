from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from wtforms_sqlalchemy.fields import QuerySelectField


def get_areas():
    from app.models.category import Categoria

    return Categoria.query.filter_by(is_active=True).order_by(Categoria.name).all()


class RegisterForm(FlaskForm):
    """Formulário de cadastro público.

    O cargo não é escolhido no cadastro público: todo novo usuário entra como
    Solicitante (abre e acompanha os próprios chamados). A promoção a
    Admin é feita pelo painel admin (`/admin/usuarios`).
    """

    name = StringField("Nome Completo", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirmar Senha", validators=[DataRequired(), EqualTo("password")]
    )

    area = QuerySelectField(
        "Área",
        query_factory=get_areas,
        allow_blank=False,
        get_label="name",
        validators=[DataRequired()],
    )

    submit = SubmitField("Criar conta")
