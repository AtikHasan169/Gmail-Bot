from telegram import Update
from telegram.ext import ContextTypes
from app.core.security import is_admin
from app.core.config import ADMIN_IDS
from app.db.models import all_users
from app.db.session import conn

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id, ADMIN_IDS):
        return
    users = all_users()
    await update.message.reply_text(
        f"👥 Users: {len(users)}"
    )

async def admin_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id, ADMIN_IDS):
        return
    if not ctx.args:
        return
    tg = int(ctx.args[0])
    conn.execute("UPDATE users SET banned=1 WHERE telegram_id=?", (tg,))
    conn.commit()
    await update.message.reply_text("🚫 User banned")