import base64
import json
from fastapi import APIRouter, Request
from app.gmail.client import get_history, get_message
from app.gmail.parser import extract_text, extract_otp
from app.db.session import SessionLocal
from app.db.models import User
from telegram import Bot
from app.core.config import TELEGRAM_BOT_TOKEN

router = APIRouter()
bot = Bot(token=TELEGRAM_BOT_TOKEN)

@router.post("/gmail/push")
async def gmail_push(request: Request):
    body = await request.json()

    if "message" not in body:
        return {"status": "ignored"}

    data = base64.b64decode(body["message"]["data"]).decode()
    payload = json.loads(data)

    email = payload.get("emailAddress")
    history_id = payload.get("historyId")

    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()

    if not user or user.banned:
        db.close()
        return {"status": "ignored"}

    history = get_history(user.access_token, history_id)

    for h in history:
        if "messagesAdded" not in h:
            continue

        for m in h["messagesAdded"]:
            msg = get_message(user.access_token, m["message"]["id"])
            text = extract_text(msg)
            otp = extract_otp(text)

            if otp:
                await bot.send_message(
                    user.telegram_id,
                    f"🔐 OTP Detected: `{otp}`",
                    parse_mode="Markdown"
                )

    db.close()
    return {"status": "ok"}