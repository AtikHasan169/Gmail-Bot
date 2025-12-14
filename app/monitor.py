from app.gmail import unread_count

def check_inbox(token):
    try:
        return unread_count(token)
    except Exception:
        return None