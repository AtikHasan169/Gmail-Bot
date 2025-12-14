import sqlite3
import time

conn = sqlite3.connect("app.db", check_same_thread=False)
c = conn.cursor()

c.executescript("""
CREATE TABLE IF NOT EXISTS users (
    tg_id TEXT,
    email TEXT,
    access_token TEXT,
    refresh_token TEXT,
    role TEXT,
    created INTEGER
);

CREATE TABLE IF NOT EXISTS aliases (
    tg_id TEXT,
    email TEXT,
    alias TEXT,
    created INTEGER
);

CREATE TABLE IF NOT EXISTS metrics (
    tg_id TEXT,
    event TEXT,
    created INTEGER
);
""")

conn.commit()

def add_user(tg_id, email, access, refresh, role="USER"):
    c.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?)",
        (tg_id, email, access, refresh, role, int(time.time()))
    )
    conn.commit()

def get_user(tg_id):
    c.execute("SELECT email, access_token, refresh_token FROM users WHERE tg_id=?", (tg_id,))
    row = c.fetchone()
    if not row:
        return None
    return {
        "email": row[0],
        "access": row[1],
        "refresh": row[2]
    }