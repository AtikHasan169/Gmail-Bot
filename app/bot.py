import re
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
from app.gmail import get_email
from app.db import add_user
from app.monitor import email_puller


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Login", callback_data="login")],
    ])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📧 Gmail OTP Bot",
        reply_markup=menu()
    )


async def buttons(update: Update, ctx):
    q = update.callback_query
    await q.answer()

    if q.data == "login":
        url = (
            "https://accounts.google.com/o/oauth2/auth"
            "?response_type=code"
            f"&client_id={GOOGLE_CLIENT_ID}"
            "&redirect_uri=http://localhost"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline&prompt=consent"
        )
        await q.message.reply_text(url)


async def handle_redirect(update: Update, ctx):
    m = re.search(r"code=([^&]+)", update.message.text)
    if not m:
        return

    token = exchange_code(m.group(1))
    email = get_email(token)

    add_user(
        update.effective_user.id,
        email,
        token["access_token"],
        token["refresh_token"]
    )

    await update.message.reply_text("✅ Gmail connected")


# 🔥 THIS IS THE IMPORTANT PART
async def post_init(application):
    application.create_task(email_puller(application))


app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .post_init(post_init)   # ✅ correct place
    .build()
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(
    MessageHandler(filters.TEXT & filters.Regex("http://localhost"), handle_redirect)
)

app.run_polling()