import pathlib

from flask import Flask, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import current_user, LoginManager, login_user, login_required, logout_user

from admin.forms import LoginForm
from data.admin_crud import (
    get_all_users,
    get_all_journeys,
    get_journey_by_id,
)
from data.models import Admin
from settings import session

# ------------------
# App setup
# ------------------
BASE_DIR = pathlib.Path(__file__).parent

app = Flask(__name__)
app.template_folder = BASE_DIR / 'admin' / 'templates'
app.static_folder = BASE_DIR / 'admin' / 'static'
app.secret_key = 'secretkey_flask_2004'

bcrypt = Bcrypt()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    db_admin = session.query(Admin).filter(Admin.id == user_id).first()
    return db_admin


@app.errorhandler(404)
def handle_404(*args, **kwargs):
    return render_template('404.html')


@app.get('/')
@login_required
def mainpage():
    return render_template('homepage.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('mainpage'))
    form = LoginForm()
    if form.validate_on_submit():
        db_admin = session.query(Admin).filter_by(username=form.username.data).first()
        if db_admin and bcrypt.check_password_hash(db_admin.password_hash, request.form['password']):
            login_user(db_admin)
            return redirect(url_for('mainpage'))
        return render_template('login.html', form=form)
    return render_template('login.html', form=form)


@app.get('/users')
@login_required
def bot_users():
    users = get_all_users(session)
    print(f'Users Count: {len(users)}')
    return render_template('users.html', users=users)


@app.get('/journeys')
@login_required
def bot_journeys():
    journeys = get_all_journeys(session)
    print(f'Journey count: {len(journeys)}')
    return render_template('journeys.html', journeys=journeys)


@app.get('/journeys/<int:id>')
@login_required
def bot_journey_detail(id: int):
    journey = get_journey_by_id(session, journey_id=id)
    locations = journey.locations
    notes = journey.notes

    print(locations)
    return render_template('journey_detail.html', journey=journey, locations=locations, notes=notes)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
