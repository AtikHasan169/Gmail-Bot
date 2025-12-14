import sqlite3
from app.core.config import DB_PATH

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row