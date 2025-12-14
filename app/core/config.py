import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost")

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_ID", "").split(",") if x]

DB_PATH = os.getenv("DB_PATH", "data.db")

PULL_INTERVAL = int(os.getenv("PULL_INTERVAL", "15"))