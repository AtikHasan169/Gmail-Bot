import requests
import time
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REDIRECT_URI

TOKEN_URL = "https://oauth2.googleapis.com/token"

def exchange_code(code: str) -> dict:
    r = requests.post(TOKEN_URL, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    data = r.json()
    data["expires_at"] = int(time.time()) + data.get("expires_in", 0)
    return data