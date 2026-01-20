import os
import sys

BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
REDIRECT_URI = "http://localhost"

if not MONGO_URI or not BOT_TOKEN:
    print("CRITICAL: Missing BOT_TOKEN or MONGO_URI.")
    sys.exit(1)
