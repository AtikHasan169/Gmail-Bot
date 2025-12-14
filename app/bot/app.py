# app/bot/app.py

import asyncio
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)
from app.bot.handlers import start, buttons
from app.gmail.watcher import gmail_watcher
from app.core.config import BOT_TOKEN

async def post_init(app):
    asyncio.create_task(gmail_watcher(app, interval=5))

def build_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    app.post_init = post_init
    return app