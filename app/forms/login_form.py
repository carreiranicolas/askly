from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email


class LoginForm(FlaskForm):
    email = StringField(
        "E-mail",
        validators=[
            DataRequired(message="O e-mail é obrigatório."),
            Email(message="Insira um e-mail válido."),
        ],
    )
    password = PasswordField("Senha", validators=[DataRequired(message="A senha é obrigatória.")])
    remember_me = BooleanField("Lembrar de mim")
    submit = SubmitField("Entrar")
