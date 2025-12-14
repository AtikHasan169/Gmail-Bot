_USERS = {}

def add_user(telegram_id, email, access_token, refresh_token):
    _USERS[telegram_id] = {
        "telegram_id": telegram_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "banned": False,
    }

def get_user(telegram_id):
    return _USERS.get(telegram_id)

def all_users():
    return list(_USERS.values())

def ban_user(telegram_id):
    if telegram_id in _USERS:
        _USERS[telegram_id]["banned"] = True