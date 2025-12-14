from cryptography.fernet import Fernet
from app.config import BOT_SECRET_KEY

fernet = Fernet(BOT_SECRET_KEY.encode())

def encrypt(text: str) -> str:
    return fernet.encrypt(text.encode()).decode()

def decrypt(text: str) -> str:
    return fernet.decrypt(text.encode()).decode()