import re
from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import GOOGLE_CLIENT_ID
from app.gmail.client import get_profile
from app.db.models import save_user
from app.bot.keyboards import main_menu
from app.oauth import exchange_code


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📬 Gmail Platform Bot\n\n"
        "• Login with Google\n"
        "• Receive OTPs automatically\n"
        "• Multi-user supported\n",
        reply_markup=main_menu()
    )


# Inline buttons
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "login":
        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            "?response_type=code"
            f"&client_id={GOOGLE_CLIENT_ID}"
            "&redirect_uri=https://oauth.pstmn.io/v1/callback"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline"
            "&prompt=consent"
        )

        await query.message.reply_text(
            "🔐 Login with Google\n\n"
            "1️⃣ Open this link\n"
            "2️⃣ Login\n"
            "3️⃣ Copy the FULL redirected URL\n"
            "4️⃣ Paste it here\n\n"
            f"{auth_url}"
        )


# 🔥 THIS WAS MISSING — OAuth redirect handler
async def handle_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # extract ?code=XXXX
    match = re.search(r"code=([^&]+)", text)
    if not match:
        return

    code = match.group(1)

    token = exchange_code(code)
    profile = get_profile(token["access_token"])

    save_user(
        telegram_id=update.effective_user.id,
        email=profile["emailAddress"],
        access_token=token["access_token"],
        refresh_token=token["refresh_token"],
    )

    await update.message.reply_text(
        f"✅ Connected Gmail:\n`{profile['emailAddress']}`",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )