from google_auth_oauthlib.flow import Flow
from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

CLIENT_CONFIG = {
    "web": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_flow(state=None):
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    if state:
        flow.state = state
    return flow
