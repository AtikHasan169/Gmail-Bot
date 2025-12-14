import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

BASE_URL = os.environ.get("BASE_URL")  # https://xxxx.up.railway.app

OAUTH_REDIRECT_URI = f"{BASE_URL}/oauth/callback"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

ADMIN_IDS = {
    int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x
}