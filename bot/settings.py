from pathlib import Path

from data.db_session import create_session, global_init

global_init('data/database.sqlite3')
ROOT = Path(__file__).parent.parent
session = create_session()
