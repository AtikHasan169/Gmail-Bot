import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

REDIRECT_URI = "http://localhost"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BOT_SECRET_KEY = os.getenv("BOT_SECRET_KEY")

ADMINS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.isdigit()
]