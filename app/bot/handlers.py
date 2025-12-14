import re
from telegram import Update
from telegram.ext import ContextTypes
from app.bot.keyboards import main_menu
from app.core.config import GOOGLE_CLIENT_ID, REDIRECT_URI, ADMIN_IDS
from app.db.models import add_user, get_user
from app.gmail.client import unread_count
from app.alias_engine import generate_aliases

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📧 Gmail Platform Bot",
        reply_markup=main_menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "login":
        url = (
            "https://accounts.google.com/o/oauth2/auth"
            f"?client_id={GOOGLE_CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            "&response_type=code"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline&prompt=consent"
        )
        await q.message.reply_text(url)

    elif q.data == "inbox":
        user = get_user(uid)
        if not user:
            return await q.message.reply_text("❌ Login first")
        count = unread_count(user["access_token"])
        await q.message.reply_text(f"📥 Unread emails: {count}")

    elif q.data == "alias":
        user = get_user(uid)
        if not user:
            return await q.message.reply_text("❌ Login first")
        aliases = generate_aliases(user["email"])
        await q.message.reply_text("\n".join(aliases))

    elif q.data == "admin":
        if uid not in ADMIN_IDS:
            return await q.message.reply_text("⛔ Admin only")
        await q.message.reply_text("🛠 Admin panel active")

async def oauth_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = re.search(r"code=([^&]+)", update.message.text)
    if not m:
        return

    # exchange handled in gmail.client
    from app.gmail.client import exchange_code

    token = exchange_code(m.group(1))
    add_user(
        update.effective_user.id,
        token["email"],
        token["access_token"],
        token["refresh_token"],
    )

    await update.message.reply_text("✅ Gmail connected")