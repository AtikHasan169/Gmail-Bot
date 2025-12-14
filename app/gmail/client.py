import requests

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

def _headers(token):
    return {"Authorization": f"Bearer {token}"}

def get_profile(token):
    r = requests.get(f"{GMAIL_API}/profile", headers=_headers(token))
    r.raise_for_status()
    return r.json()

def list_unread(token):
    r = requests.get(
        f"{GMAIL_API}/messages?q=is:unread",
        headers=_headers(token)
    )
    r.raise_for_status()
    return r.json().get("messages", [])

def get_message(token, msg_id):
    r = requests.get(
        f"{GMAIL_API}/messages/{msg_id}?format=full",
        headers=_headers(token)
    )
    r.raise_for_status()
    return r.json()

def watch_mailbox(token, topic):
    body = {
        "topicName": topic,
        "labelIds": ["INBOX"],
    }
    r = requests.post(
        f"{GMAIL_API}/watch",
        headers=_headers(token),
        json=body
    )
    r.raise_for_status()
    return r.json()

def get_history(token, start_history_id):
    r = requests.get(
        f"{GMAIL_API}/history?startHistoryId={start_history_id}",
        headers=_headers(token)
    )
    r.raise_for_status()
    return r.json().get("history", [])