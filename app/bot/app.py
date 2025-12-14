from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from app.admin.commands import admin_users, admin_ban, admin_unban
from app.bot.handlers import inbox, alias
from app.bot.handlers import start, buttons, handle_redirect
from app.core.config import BOT_TOKEN

def build_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inbox", inbox))
    app.add_handler(CommandHandler("alias", alias))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex("code="), handle_redirect)
    )

    return app