import os
import sys

# Load from Environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")

# Auto-Login Settings (Localhost for capturing the redirect)
PORT = 8080
REDIRECT_URI = f"http://127.0.0.1:{PORT}/callback"

if not MONGO_URI or not BOT_TOKEN:
    print("CRITICAL: Missing BOT_TOKEN or MONGO_URI.")
    sys.exit(1)
