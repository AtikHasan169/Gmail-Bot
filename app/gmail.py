import base64
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    SCOPES,
)

OTP_REGEX = re.compile(r"\b(\d{4,8})\b")


def build_service(user):
    creds = Credentials(
        token=user["access"],
        refresh_token=user["refresh"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def fetch_unread_ids(user, max_results=5):
    service = build_service(user)
    res = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=max_results,
    ).execute()
    return res.get("messages", [])


def extract_otp(user, msg_id):
    service = build_service(user)
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="full",
    ).execute()

    payload = msg.get("payload", {})
    parts = payload.get("parts", [])

    text = ""

    for p in parts:
        if p.get("mimeType") == "text/plain":
            data = p.get("body", {}).get("data")
            if data:
                text += base64.urlsafe_b64decode(data).decode(
                    errors="ignore"
                )

    m = OTP_REGEX.search(text)
    return m.group(1) if m else None