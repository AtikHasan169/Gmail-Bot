from telegram import Update
from telegram.ext import ContextTypes
from app.config import ADMINS
from app.db import user_count

def is_admin(uid):
    return uid in ADMINS

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        f"👥 Users: {user_count()}"
    )