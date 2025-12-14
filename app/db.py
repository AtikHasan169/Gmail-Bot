import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

# ─── USERS ─────────────────────────────────────

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    email TEXT,
    access TEXT,
    refresh TEXT
)
""")

# ─── OTP STATE ─────────────────────────────────

cur.execute("""
CREATE TABLE IF NOT EXISTS otp_state (
    user_id INTEGER PRIMARY KEY,
    last_msg_id TEXT
)
""")

conn.commit()


def add_user(uid, email, access, refresh):
    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)",
        (uid, email, access, refresh)
    )
    conn.commit()


def get_user(uid):
    row = cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (uid,)
    ).fetchone()
    if not row:
        return None

    return {
        "user_id": row[0],
        "email": row[1],
        "access": row[2],
        "refresh": row[3],
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
        }
    return users


def get_last_otp(uid):
    r = cur.execute(
        "SELECT last_msg_id FROM otp_state WHERE user_id=?",
        (uid,)
    ).fetchone()
    return r[0] if r else None


def set_last_otp(uid, msg_id):
    cur.execute(
        "INSERT OR REPLACE INTO otp_state VALUES (?, ?)",
        (uid, msg_id)
    )
    conn.commit()