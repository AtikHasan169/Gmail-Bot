import re
import asyncio
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import BOT_TOKEN, GOOGLE_CLIENT_ID
from app.oauth import exchange_code
from app.gmail import (
    get_email,
    unread_count,
    build_service,
    list_latest_message_id,
)
from app.alias_engine import generate
from app.rate_limit import allow
from app.analytics import log_event
from app.db import (
    add_user,
    get_user,
    get_all_users,
    get_last_msg,
    set_last_msg,
)

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

def menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔐 Login", callback_data="login")],
            [InlineKeyboardButton("✉️ Generate", callback_data="gen")],
            [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        ]
    )


# ─────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Gmail Platform Bot 🚀", reply_markup=menu()
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    # ───── LOGIN ─────
    if q.data == "login":
        url = (
            "https://accounts.google.com/o/oauth2/auth"
            "?response_type=code"
            f"&client_id={GOOGLE_CLIENT_ID}"
            "&redirect_uri=http://localhost"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline&prompt=consent"
        )
        await q.message.reply_text(
            "Authorize Google account:\n\n" + url
        )

    # ───── GENERATE ALIAS ─────
    elif q.data == "gen":
        if not allow(uid):
            return await q.message.reply_text("⛔ Rate limited")

        user = get_user(uid)
        if not user:
            return await q.message.reply_text("🔐 Login first")

        alias = generate(user["email"])
        log_event(uid, "GEN_ALIAS")
        await q.message.reply_text(alias)

    # ───── INBOX COUNT ─────
    elif q.data == "inbox":
        user = get_user(uid)
        if not user:
            return await q.message.reply_text("🔐 Login first")

        count = unread_count(user)
        await q.message.reply_text(f"📥 Unread emails: {count}")


# ─────────────────────────────────────────────
# OAuth Redirect Handler
# ─────────────────────────────────────────────

async def handle_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = re.search(r"code=([^&]+)", update.message.text)
    if not m:
        return

    token = exchange_code(m.group(1))

    email = get_email(
        {
            "access": token["access_token"],
            "refresh": token["refresh_token"],
        }
    )

    add_user(
        update.effective_user.id,
        email,
        token["access_token"],
        token["refresh_token"],
    )

    log_event(update.effective_user.id, "LOGIN")

    await update.message.reply_text(
        f"✅ Connected: {email}", reply_markup=menu()
    )


# ─────────────────────────────────────────────
# Background Gmail Watcher (POLLING)
# ─────────────────────────────────────────────

async def email_watcher(application):
    await asyncio.sleep(5)  # let bot start

    while True:
        users = get_all_users()

        for uid, user in users.items():
            try:
                service = build_service(user)
                latest_id = list_latest_message_id(service)

                if not latest_id:
                    continue

                last_seen = get_last_msg(uid)

                if last_seen != latest_id:
                    await application.bot.send_message(
                        chat_id=uid,
                        text="📩 New email received!",
                    )
                    set_last_msg(uid, latest_id)

            except Exception:
                pass  # keep watcher alive no matter what

        await asyncio.sleep(30)  # poll interval


# ─────────────────────────────────────────────
# App bootstrap
# ─────────────────────────────────────────────

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(
    MessageHandler(
        filters.TEXT & filters.Regex("http://localhost"),
        handle_redirect,
    )
)

# 🔥 START BACKGROUND TASK
app.create_task(email_watcher(app))

app.run_polling()