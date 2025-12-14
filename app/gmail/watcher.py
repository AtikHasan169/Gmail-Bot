import asyncio
from app.gmail.client import list_unread, get_message
from app.gmail.parser import extract_text, extract_otp
from app.db.models import all_users

SEEN = set()

async def gmail_watcher(app, interval: int):
    await asyncio.sleep(5)

    while True:
        for u in all_users():
            if u["banned"]:
                continue

            msgs = list_unread(u["access_token"])

            for m in msgs:
                key = f'{u["telegram_id"]}:{m["id"]}'
                if key in SEEN:
                    continue

                msg = get_message(u["access_token"], m["id"])
                text = extract_text(msg)
                otp = extract_otp(text)

                if otp:
                    await app.bot.send_message(
                        chat_id=u["telegram_id"],
                        text=f"🔐 OTP Detected: `{otp}`",
                        parse_mode="Markdown"
                    )

                SEEN.add(key)

        await asyncio.sleep(interval)