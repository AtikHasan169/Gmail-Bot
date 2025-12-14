from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import SCOPES

def service(token: dict):
    creds = Credentials(
        token=token["access"],
        refresh_token=token["refresh"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES
    )
    return build("gmail", "v1", credentials=creds)

def get_email(token: dict) -> str:
    profile = service(token).users().getProfile(userId="me").execute()
    return profile["emailAddress"]

def unread_count(token: dict) -> int:
    res = service(token).users().messages().list(
        userId="me", q="is:unread"
    ).execute()
    return len(res.get("messages", []))