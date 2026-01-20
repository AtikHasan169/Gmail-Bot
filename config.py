import os
import sys
import uuid

# --- ENV VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost"


INSTANCE_ID = uuid.uuid4().hex 

if not MONGO_URI or not BOT_TOKEN:
    print("CRITICAL: Missing BOT_TOKEN or MONGO_URI.")
    sys.exit(1)
