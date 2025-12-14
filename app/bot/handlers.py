import re
from telegram import Update
from telegram.ext import ContextTypes

from app.alias import generate_aliases
from app.bot.keyboards import main_menu

from app.gmail.client import (
    list_unread,
    exchange_code,
    get_profile,
    watch_mailbox,
)

from app.core.config import (
    GOOGLE_CLIENT_ID,
    OAUTH_REDIRECT_URI,
    GMAIL_SCOPES,
    GMAIL_PUBSUB_TOPIC,
)

from app.db.session import SessionLocal
from app.db.models import User


# ───────────────────────── START ─────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📧 Gmail Platform Bot",
        reply_markup=main_menu()
    )


# ───────────────────────── INBOX COUNT ─────────────────────────

async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    user = db.query(User).filter(
        User.telegram_id == update.effective_user.id
    ).first()
    db.close()

    if not user:
        await update.message.reply_text("❌ Login first")
        return

    unread = list_unread(user.access_token)
    await update.message.reply_text(f"📥 Unread emails: {len(unread)}")


# ───────────────────────── ALIASES ─────────────────────────

async def alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    user = db.query(User).filter(
        User.telegram_id == update.effective_user.id
    ).first()
    db.close()

    if not user:
        await update.message.reply_text("❌ Login first")
        return

    # ONLY uppercase/lowercase (engine must respect this)
    aliases = generate_aliases(user.email)

    text = "📧 Email Variants (A–Z only):\n\n"
    text += "\n".join(aliases)

    await update.message.reply_text(text)


# ───────────────────────── BUTTON HANDLER ─────────────────────────

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "login":
        scope = " ".join(GMAIL_SCOPES)

        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={GOOGLE_CLIENT_ID}"
            f"&redirect_uri={OAUTH_REDIRECT_URI}"
            f"&response_type=code"
            f"&scope={scope}"
            "&access_type=offline"
            "&prompt=consent"
        )

        await q.message.reply_text(
            "🔐 Authorize Gmail access:\n\n" + auth_url
        )


# ───────────────────────── OAUTH REDIRECT HANDLER ─────────────────────────

async def handle_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User pastes redirected URL containing ?code=
    """

    match = re.search(r"code=([^&]+)", update.message.text)
    if not match:
        await update.message.reply_text("❌ Authorization code not found")
        return

    # Exchange code for tokens
    token = exchange_code(match.group(1))

    # Fetch Gmail profile
    profile = get_profile(token["access_token"])
    email = profile["emailAddress"]

    # Save / update user
    db = SessionLocal()
    db.merge(
        User(
            telegram_id=update.effective_user.id,
            email=email,
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            banned=False,
        )
    )
    db.commit()
    db.close()

    # 🔔 START GMAIL PUSH (CRITICAL)
    watch_mailbox(
        token["access_token"],
        GMAIL_PUBSUB_TOPIC
    )

    await update.message.reply_text(
        f"✅ Gmail connected successfully:\n{email}"
    )