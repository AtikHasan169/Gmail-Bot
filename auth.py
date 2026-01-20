from google_auth_oauthlib.flow import Flow
from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

# --- CHANGED: "installed" -> "web" ---
# This matches the new credentials you just created.
CLIENT_CONFIG = {
    "web": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
    }
}

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

def get_flow(state=None):
    flow = Flow.from_client_config(
        CLIENT_CONFIG, 
        scopes=SCOPES, 
        redirect_uri=REDIRECT_URI
    )
    
    if state: 
        flow.state = state
        
    return flow
