import os
import sys
import uuid

# --- ENV VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# --- RAILWAY & WEB CONFIG ---
# Get the public domain provided by Railway
RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "localhost")

# Clean up URL to ensure it has no 'https://' prefix for consistent formatting
if "://" in RAILWAY_DOMAIN:
    RAILWAY_DOMAIN = RAILWAY_DOMAIN.split("://")[1]

# This is the "Magic Link" Google sends the user back to
if "localhost" in RAILWAY_DOMAIN:
    REDIRECT_URI = f"http://{RAILWAY_DOMAIN}:8080/auth/google"
else:
    REDIRECT_URI = f"https://{RAILWAY_DOMAIN}/auth/google"

# Railway assigns a random port here. Default to 8080.
PORT = int(os.getenv("PORT", 8080))

# --- DEPLOYMENT CONFLICT FIX ---
# Generates a unique ID every time the bot restarts to kill old versions
INSTANCE_ID = uuid.uuid4().hex 

# --- SAFETY CHECK ---
if not MONGO_URI or not BOT_TOKEN:
    print("❌ CRITICAL ERROR: Missing BOT_TOKEN or MONGO_URI.")
    sys.exit(1)

if not CLIENT_ID or not CLIENT_SECRET:
    print("⚠️ WARNING: CLIENT_ID or CLIENT_SECRET missing. Google Login will fail.")
