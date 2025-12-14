USERS = {}

def add_user(tg_id, email, access, refresh):
    USERS[tg_id] = {
        "telegram_id": tg_id,
        "email": email,
        "access": access,
        "refresh": refresh,
        "banned": False
    }

def get_user(tg_id):
    return USERS.get(tg_id)

def all_users():
    return USERS.values()