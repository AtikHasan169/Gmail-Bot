import requests
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REDIRECT_URI

def exchange_code(code):
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    ).json()

    return {
        "access_token": r["access_token"],
        "refresh_token": r.get("refresh_token"),
        "email": "user@gmail.com",  # replace with profile call if needed
    }

def list_unread(token):
    return []  # real Gmail API call here

def get_message(token, msg_id):
    return {}

def unread_count(token):
    return 0