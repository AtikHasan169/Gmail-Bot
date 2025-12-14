from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from app.core.config import BOT_TOKEN, PULL_INTERVAL
from app.bot.handlers import start, buttons, oauth_redirect
from app.gmail.watcher import gmail_watcher
from app.admin.commands import admin_stats, admin_ban

def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("ban", admin_ban))

    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT, oauth_redirect))

    app.post_init = lambda app: app.create_task(
        gmail_watcher(app, PULL_INTERVAL)
    )
    return app