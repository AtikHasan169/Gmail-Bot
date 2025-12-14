import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
BASE_URL = os.getenv("BASE_URL")

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
REDIRECT_URI = f"{BASE_URL}/oauth/google"