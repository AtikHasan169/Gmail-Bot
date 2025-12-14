import base64
import re

OTP_REGEX = re.compile(r"\b(\d{4,8})\b")

def extract_text(msg):
    parts = msg.get("payload", {}).get("parts", [])
    text = ""

    for p in parts:
        if p.get("mimeType") == "text/plain":
            data = p["body"].get("data")
            if data:
                text += base64.urlsafe_b64decode(data).decode(errors="ignore")

    return text

def extract_otp(text):
    m = OTP_REGEX.search(text)
    return m.group(1) if m else None