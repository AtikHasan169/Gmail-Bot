import requests

BASE = "https://gmail.googleapis.com/gmail/v1"

def headers(token):
    return {"Authorization": f"Bearer {token}"}


def profile(token):
    r = requests.get(f"{BASE}/users/me/profile", headers=headers(token))
    r.raise_for_status()
    return r.json()


def list_unread(token):
    r = requests.get(
        f"{BASE}/users/me/messages",
        headers=headers(token),
        params={"q": "is:unread"}
    )
    return r.json().get("messages", [])


def get_message(token, msg_id):
    r = requests.get(
        f"{BASE}/users/me/messages/{msg_id}",
        headers=headers(token),
        params={"format": "full"}
    )
    return r.json()