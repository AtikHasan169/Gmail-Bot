from telegram import Update
from telegram.ext import ContextTypes
from app.bot.keyboards import menu
from app.core.config import GOOGLE_CLIENT_ID, REDIRECT_URI, GMAIL_SCOPE
from app.db.memory import get_user
from app.utils.email_case import generate

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gmail Platform Bot", reply_markup=menu())

async def buttons(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "login":
        url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={GOOGLE_CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code"
            f"&scope={GMAIL_SCOPE}"
            "&access_type=offline&prompt=consent"
        )
        await q.message.reply_text(url)

    if q.data == "case":
        u = get_user(uid)
        if not u:
            return await q.message.reply_text("Login first")

        variants = generate(u["email"], 50)
        await q.message.reply_text("\n".join(variants))