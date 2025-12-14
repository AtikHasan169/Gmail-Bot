from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from app.bot.handlers import start, buttons
from app.core.config import BOT_TOKEN
from app.gmail.watcher import gmail_watcher

def build_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.job_queue.run_repeating(lambda _: gmail_watcher(app), interval=20, first=10)
    return app