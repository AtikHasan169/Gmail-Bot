from app.db.session import conn

conn.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    email TEXT,
    access_token TEXT,
    refresh_token TEXT,
    banned INTEGER DEFAULT 0
)
""")

conn.commit()


def upsert_user(tg, email, access, refresh):
    conn.execute("""
    INSERT INTO users VALUES (?,?,?,?,0)
    ON CONFLICT(telegram_id)
    DO UPDATE SET
        email=excluded.email,
        access_token=excluded.access_token,
        refresh_token=excluded.refresh_token
    """, (tg, email, access, refresh))
    conn.commit()


def get_user(tg):
    r = conn.execute(
        "SELECT * FROM users WHERE telegram_id=?",
        (tg,)
    ).fetchone()
    return dict(r) if r else None


def all_users():
    return conn.execute("SELECT * FROM users").fetchall()