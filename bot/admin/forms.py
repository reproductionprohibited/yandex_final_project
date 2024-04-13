from wtforms import StringField, PasswordField, validators
from flask_wtf import FlaskForm


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[validators.Length(min=4, max=25)])
    password = PasswordField('Password')
