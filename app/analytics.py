import time
from app.db import c, conn

def log_event(uid, event):
    c.execute(
        "INSERT INTO metrics VALUES (?,?,?)",
        (uid, event, int(time.time()))
    )
    conn.commit()