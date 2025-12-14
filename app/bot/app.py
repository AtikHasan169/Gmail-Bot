from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from app.core.config import BOT_TOKEN
from app.bot.handlers import start, buttons, oauth_redirect
from app.gmail.watcher import gmail_watcher

def build_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("code="), oauth_redirect)
    )

    async def post_init(application):
        application.create_task(gmail_watcher(application, interval=20))

    app.post_init = post_init
    return app