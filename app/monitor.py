import asyncio
from app.db import get_all_users, get_last_otp, set_last_otp
from app.gmail import fetch_unread_ids, extract_otp


async def email_puller(app):
    await asyncio.sleep(5)  # wait for bot startup

    while True:
        users = get_all_users()

        for uid, user in users.items():
            try:
                messages = fetch_unread_ids(user)
                if not messages:
                    continue

                last_seen = get_last_otp(uid)

                for m in messages:
                    msg_id = m["id"]

                    if msg_id == last_seen:
                        break

                    otp = extract_otp(user, msg_id)
                    if otp:
                        await app.bot.send_message(
                            chat_id=uid,
                            text=f"🔐 OTP Code:\n\n`{otp}`",
                            parse_mode="Markdown",
                        )
                        set_last_otp(uid, msg_id)
                        break

            except Exception:
                pass  # never crash polling

        await asyncio.sleep(20)