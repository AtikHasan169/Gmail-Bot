import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    email TEXT,
    access TEXT,
    refresh TEXT,
    otp_enabled INTEGER DEFAULT 1,
    otp_count INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS otp_state (
    user_id INTEGER PRIMARY KEY,
    last_msg_id TEXT
)
""")

conn.commit()


def add_user(uid, email, access, refresh):
    cur.execute("""
    INSERT OR REPLACE INTO users
    (user_id, email, access, refresh, otp_enabled)
    VALUES (?, ?, ?, ?, 1)
    """, (uid, email, access, refresh))
    conn.commit()


def get_user(uid):
    row = cur.execute(
        "SELECT * FROM users WHERE user_id=?", (uid,)
    ).fetchone()
    if not row:
        return None
    return {
        "user_id": row[0],
        "email": row[1],
        "access": row[2],
        "refresh": row[3],
        "otp_enabled": bool(row[4]),
        "otp_count": row[5],
    }


def get_all_users():
    rows = cur.execute("SELECT * FROM users").fetchall()
    users = {}
    for r in rows:
        users[r[0]] = {
            "user_id": r[0],
            "email": r[1],
            "access": r[2],
            "refresh": r[3],
            "otp_enabled": bool(r[4]),
            "otp_count": r[5],
        }
    return users


def set_last_msg(uid, msg_id):
    cur.execute("""
    INSERT OR REPLACE INTO otp_state VALUES (?, ?)
    """, (uid, msg_id))
    conn.commit()


def get_last_msg(uid):
    r = cur.execute(
        "SELECT last_msg_id FROM otp_state WHERE user_id=?",
        (uid,)
    ).fetchone()
    return r[0] if r else None


def inc_otp(uid):
    cur.execute(
        "UPDATE users SET otp_count = otp_count + 1 WHERE user_id=?",
        (uid,)
    )
    conn.commit()


def toggle_otp(uid, state):
    cur.execute(
        "UPDATE users SET otp_enabled=? WHERE user_id=?",
        (1 if state else 0, uid)
    )
    conn.commit()


def user_count():
    return cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]