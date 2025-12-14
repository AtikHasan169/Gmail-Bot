import base64
import re

OTP_RE = re.compile(r"\b\d{4,8}\b")

def extract_text(msg):
    parts = msg["payload"].get("parts", [])
    for p in parts:
        if p["mimeType"] == "text/plain":
            data = p["body"]["data"]
            return base64.urlsafe_b64decode(data).decode()
    return ""

def extract_otp(text):
    m = OTP_RE.search(text)
    return m.group(0) if m else None