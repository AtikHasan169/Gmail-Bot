from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from app.bot.handlers import start, buttons
from app.core.config import BOT_TOKEN

def build_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    return app