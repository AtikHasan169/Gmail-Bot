import asyncio
import time
from app.gmail.client import list_unread, get_message
from app.gmail.parser import extract_text, extract_otp
from app.db.session import SessionLocal
from app.db.models import User

SEEN = set()

async def gmail_watcher(app, interval: int = 15):
    """
    Poll Gmail inbox for unread messages
    and send OTP or content to Telegram users.
    """

    # give bot time to start
    await asyncio.sleep(5)

    while True:
        db = SessionLocal()
        users = db.query(User).filter(User.banned == False).all()
        db.close()

        for user in users:
            try:
                messages = list_unread(user.access_token)

                for m in messages:
                    key = f"{user.telegram_id}:{m['id']}"
                    if key in SEEN:
                        continue

                    msg = get_message(user.access_token, m["id"])
                    text = extract_text(msg)
                    otp = extract_otp(text)

                    if otp:
                        await app.bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"🔐 OTP Detected:\n`{otp}`",
                            parse_mode="Markdown"
                        )
                    else:
                        preview = text[:800]
                        await app.bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"📩 New Email:\n\n{preview}"
                        )

                    SEEN.add(key)

            except Exception as e:
                print(f"[WATCHER ERROR] {user.email}: {e}")

        await asyncio.sleep(interval)