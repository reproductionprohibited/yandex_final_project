import pathlib

from flask import Flask, render_template
from flask_bcrypt import Bcrypt

from data.admin_crud import (
    get_all_users,
    get_all_journeys,
    get_journey_by_id,
)

from settings import session

BASE_DIR = pathlib.Path(__file__).parent
app = Flask(__name__)
app.template_folder = BASE_DIR / 'admin' / 'templates'
app.static_folder = BASE_DIR / 'admin' / 'static'
# login_manager = LoginManager(app)
bcrypt = Bcrypt()

# login_manager.login_view = 'login'


# @login_manager.user_loader
# def load_user(user_id):
#     db_admin = session.query(Admin).filter(Admin.id == user_id).first()
#     print(f'Got: {db_admin}')
#     return db_admin


@app.errorhandler(404)
def handle_404(*args, **kwargs):
    return render_template('404.html')

@app.get('/')
def mainpage():
    return render_template('homepage.html')


@app.get('/users')
def bot_users():
    users = get_all_users(session)
    print(f'Users Count: {len(users)}')
    return render_template('users.html', users=users)


@app.get('/journeys')
def bot_journeys():
    journeys = get_all_journeys(session)
    print(f'Journey count: {len(journeys)}')
    return render_template('journeys.html', journeys=journeys)


@app.get('/journeys/{id}')
def bot_journey_detail(id: int):
    journey = get_journey_by_id(session, journey_id=id)
    locations = journey.locations
    notes = journey.notes
    return render_template('journey_detail.html', journey=journey, locations=locations, notes=notes)


# @app.route('/logout')
# @login_required
# def logout():
#     logout_user()
#     return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
