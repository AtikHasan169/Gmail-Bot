import re
from telegram import Update
from telegram.ext import ContextTypes
from app.bot.keyboards import main_menu
from app.db.models import upsert_user, get_user
from app.core.config import GOOGLE_CLIENT_ID
from app.gmail.client import profile
from app.gmail.alias import generate_aliases

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Gmail Platform Bot",
        reply_markup=main_menu()
    )

async def buttons(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "login":
        url = (
            "https://accounts.google.com/o/oauth2/auth"
            "?response_type=code"
            f"&client_id={GOOGLE_CLIENT_ID}"
            "&redirect_uri=http://localhost"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline&prompt=consent"
        )
        return await q.message.reply_text(url)

    user = get_user(uid)
    if not user:
        return await q.message.reply_text("Login first")

    if q.data == "alias":
        aliases = generate_aliases(user["email"])
        return await q.message.reply_text(
            "\n".join(aliases[:40])
        )

async def oauth_redirect(update: Update, ctx):
    m = re.search(r"code=([^&]+)", update.message.text)
    if not m:
        return

    from app.oauth import exchange_code
    tok = exchange_code(m.group(1))
    email = profile(tok["access_token"])["emailAddress"]

    upsert_user(
        update.effective_user.id,
        email,
        tok["access_token"],
        tok["refresh_token"]
    )

    await update.message.reply_text("✅ Connected")