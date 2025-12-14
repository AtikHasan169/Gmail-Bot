from app.config import ADMINS

def is_admin(uid: int) -> bool:
    return uid in ADMINS