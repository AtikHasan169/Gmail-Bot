from telegram import Update
from telegram.ext import ContextTypes
from app.core.config import ADMIN_IDS
from app.db.session import SessionLocal
from app.db.models import User

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    db = SessionLocal()
    users = db.query(User).all()
    db.close()

    text = "👥 Users:\n\n"
    for u in users:
        text += f"{u.telegram_id} | {u.email} | banned={u.banned}\n"

    await update.message.reply_text(text)

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        return await update.message.reply_text("Usage: /ban <telegram_id>")

    tid = int(context.args[0])

    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == tid).first()
    if user:
        user.banned = True
        db.commit()
        await update.message.reply_text(f"🚫 Banned {tid}")
    else:
        await update.message.reply_text("User not found")

    db.close()

async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        return await update.message.reply_text("Usage: /unban <telegram_id>")

    tid = int(context.args[0])

    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == tid).first()
    if user:
        user.banned = False
        db.commit()
        await update.message.reply_text(f"✅ Unbanned {tid}")
    else:
        await update.message.reply_text("User not found")

    db.close()