import asyncio
from app.gmail import build_service, fetch_unread, extract_otp
from app.db import get_all_users, get_last_msg, set_last_msg, inc_otp

async def otp_watcher(app):
    await asyncio.sleep(5)

    while True:
        users = get_all_users()

        for uid, user in users.items():
            if not user["otp_enabled"]:
                continue

            try:
                service = build_service(user)
                msgs = fetch_unread(service)

                last_seen = get_last_msg(uid)

                for m in msgs:
                    if m["id"] == last_seen:
                        break

                    otp = extract_otp(service, m["id"])
                    if otp:
                        await app.bot.send_message(
                            chat_id=uid,
                            text=f"🔐 OTP Code:\n\n`{otp}`",
                            parse_mode="Markdown",
                        )
                        set_last_msg(uid, m["id"])
                        inc_otp(uid)
                        break

            except Exception:
                pass

        await asyncio.sleep(20)