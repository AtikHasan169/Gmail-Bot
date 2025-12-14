import base64
import re

def extract_text(msg):
    return ""

def extract_otp(text):
    if not text:
        return None
    m = re.search(r"\b(\d{4,8})\b", text)
    return m.group(1) if m else None