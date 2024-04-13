import pathlib

import bcrypt

from bot.data.db_session import global_init, create_session
from bot.data.models import Admin

BASE_DIR = pathlib.Path(__file__).parent


# ----------------
# Add a new admin to the database
# ----------------
def main():
    global_init(f'{BASE_DIR}/bot/data/database.sqlite3')
    session = create_session()

    # ----------------
    # Set admin username & password
    # ----------------
    username = 'admin'
    password = 'admin'

    if len(session.query(Admin).filter(Admin.username == username).all()) > 0:
        raise Exception(f'Admin with username `{username}` already exists in the DB')

    password_hash = bcrypt.hashpw(password.encode(),  bcrypt.gensalt()).decode()
    db_admin = Admin(
        username=username,
        password_hash=password_hash
    )

    session.add(db_admin)
    session.commit()
    session.refresh(db_admin)


if __name__ == '__main__':
    main()
