import requests

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


def _headers(access_token: str):
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


# ✅ GET USER PROFILE (THIS WAS MISSING)
def get_profile(access_token: str) -> dict:
    r = requests.get(
        f"{GMAIL_API}/users/me/profile",
        headers=_headers(access_token),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# List unread messages
def list_unread(access_token: str):
    r = requests.get(
        f"{GMAIL_API}/users/me/messages",
        headers=_headers(access_token),
        params={"q": "is:unread"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("messages", [])


# Get single message
def get_message(access_token: str, msg_id: str):
    r = requests.get(
        f"{GMAIL_API}/users/me/messages/{msg_id}",
        headers=_headers(access_token),
        params={"format": "full"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()