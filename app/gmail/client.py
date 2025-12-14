from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def service(token):
    creds = Credentials(token=token)
    return build("gmail", "v1", credentials=creds)

def unread(token):
    res = service(token).users().messages().list(
        userId="me", q="is:unread"
    ).execute()
    return res.get("messages", [])

def message(token, msg_id):
    return service(token).users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()