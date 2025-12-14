import base64
import re

OTP_REGEX = re.compile(r"\b\d{4,8}\b")

def decode(data):
    return base64.urlsafe_b64decode(data).decode(errors="ignore")


def extract_text(msg):
    payload = msg.get("payload", {})
    if payload.get("body", {}).get("data"):
        return decode(payload["body"]["data"])

    for p in payload.get("parts", []):
        if p.get("body", {}).get("data"):
            return decode(p["body"]["data"])
    return ""


def extract_otp(text):
    m = OTP_REGEX.search(text)
    return m.group(0) if m else None