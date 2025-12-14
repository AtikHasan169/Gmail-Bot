from telegram import Update
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive")

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()