from google_auth_oauthlib.flow import Flow
from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

# Scopes: What permissions we are asking for
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

def get_flow(state=None):
    """
    Creates a Google OAuth Flow object.
    'state' is the secret ID we pass to Google to remember WHICH user is logging in.
    """
    flow = Flow.from_client_config(
        CLIENT_CONFIG, 
        scopes=SCOPES, 
        redirect_uri=REDIRECT_URI
    )
    
    if state: 
        flow.state = state
        
    return flow
