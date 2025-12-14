import asyncio
from app.gmail.client import unread, message
from app.gmail.parser import extract_text, extract_otp
from app.db.memory import all_users

SEEN = set()

async def gmail_watcher(bot):
    await asyncio.sleep(5)

    while True:
        for u in all_users():
            msgs = unread(u["access"])
            for m in msgs:
                key = f'{u["telegram_id"]}:{m["id"]}'
                if key in SEEN:
                    continue

                msg = message(u["access"], m["id"])
                text = extract_text(msg)
                otp = extract_otp(text)

                if otp:
                    await bot.bot.send_message(
                        u["telegram_id"],
                        f"🔐 OTP: `{otp}`",
                        parse_mode="Markdown"
                    )

                SEEN.add(key)

        await asyncio.sleep(15)