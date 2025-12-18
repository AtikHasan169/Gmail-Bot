import os
import re
import asyncio
import aiohttp
import random
import datetime
import time
import signal
from base64 import urlsafe_b64decode
from email import message_from_bytes
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- CONFIGURATION (Load from Environment) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
SECRET = os.getenv("CLIENT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
PORT = int(os.environ.get('PORT', 8080))
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

# --- DATABASE SETUP ---
if MONGO_URI:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['gmail_otp_bot']
    users_col = db['users']
    seen_col = db['seen_messages']
else:
    print("WARNING: MONGO_URI not found. MongoDB operations will fail.")

# --- UI GENERATOR ---
async def get_ui_content(uid_str):
    user = await users_col.find_one({"uid": uid_str})
    
    if not user:
        url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            "&response_type=code"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline&prompt=consent"
        )
        text = "❌ **Account Not Linked**\n\nPlease login to start monitoring."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔐 Login Google", url=url)]])
        return text, kb

    email = user.get("email", "Unknown")
    captured = user.get("captured", 0)
    last_check = user.get("last_check", "Never")
    latest_otp = user.get("latest_otp", "None Yet")
    gen_alias = user.get("last_gen", "None")
    status_icon = "🟢" if user.get("access") else "🔴"
    
    last_ts = user.get("last_otp_timestamp", 0)
    is_fresh = (time.time() - last_ts) < 30
    otp_header = "🚨 **[NEW] OTP RECEIVED** 🚨" if is_fresh else "📨 **Latest OTP:**"

    text = (
        f"🚀 **LIVE SESSION INTERFACE** {status_icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Account:** `{email}`\n"
        f"🔑 **Total Captured:** `{captured}`\n"
        f"🕒 **Last Scan:** `{last_check}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{otp_header}\n{latest_otp}\n\n"
        f"✨ **Last Alias:**\n`{gen_alias}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _All updates edit this message. Auto-clears 'NEW' status after 30s._"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Force Scan", callback_data="ui_refresh"),
         InlineKeyboardButton("✨ Gen Alias", callback_data="ui_gen")],
        [InlineKeyboardButton("🛑 Logout", callback_data="ui_logout"),
         InlineKeyboardButton("🗑 Clear Logs", callback_data="ui_clear")]
    ])
    
    return text, kb

# --- GMAIL ENGINE ---
async def refresh_google_token(uid_str, session):
    user = await users_col.find_one({"uid": uid_str})
    if not user or not user.get("refresh"): return None
    
    data = {
        "client_id": CLIENT_ID,
        "client_secret": SECRET,
        "refresh_token": user["refresh"],
        "grant_type": "refresh_token"
    }
    async with session.post("https://oauth2.googleapis.com/token", data=data) as r:
        res = await r.json()
        if "access_token" in res:
            await users_col.update_one({"uid": uid_str}, {"$set": {"access": res["access_token"]}})
            return res["access_token"]
    return None

async def fetch_unread(uid_str, user_data, session, limit=None):
    access = user_data["access"]
    headers = {"Authorization": f"Bearer {access}"}
    params = {"q": "is:unread"}
    if limit: params["maxResults"] = limit

    async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=params, headers=headers) as r:
        if r.status == 401:
            new_access = await refresh_google_token(uid_str, session)
            if not new_access: return []
            headers = {"Authorization": f"Bearer {new_access}"}
            async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=params, headers=headers) as r2:
                res = await r2.json()
        else:
            res = await r.json()
    return res.get("messages", [])

async def fetch_body(user_data, mid, session):
    headers = {"Authorization": f"Bearer {user_data['access']}"}
    async with session.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=raw", headers=headers) as r:
        res = await r.json()
        raw = res.get("raw")
        if not raw: return ""
        msg = message_from_bytes(urlsafe_b64decode(raw))
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(errors="ignore")
        return msg.get_payload(decode=True).decode(errors="ignore")

# --- CORE LOGIC ---
async def update_live_ui(uid_str, bot):
    text, kb = await get_ui_content(uid_str)
    user = await users_col.find_one({"uid": uid_str})
    if not user or not user.get("main_msg_id"): return
    
    try:
        await bot.edit_message_text(
            chat_id=int(uid_str),
            message_id=user["main_msg_id"],
            text=text,
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception: pass

async def process_user_emails(uid_str, bot, session, manual=False):
    user = await users_col.find_one({"uid": uid_str})
    if not user: return False
    
    messages = await fetch_unread(uid_str, user, session, limit=5 if manual else 10)
    new_otp_found = False
    
    for m in messages:
        mid = m['id']
        key = f"{uid_str}:{mid}"
        
        is_seen = await seen_col.find_one({"key": key})
        if not manual and is_seen: continue
        
        body = await fetch_body(user, mid, session)
        codes = re.findall(r"\b\d{5,10}\b", body)
        if codes:
            app_name = "Unknown"
            msgl = body.lower()
            apps = ["Telegram", "Google", "WhatsApp", "Amazon", "Facebook", "Instagram", "Apple", "Microsoft", "Netflix"]
            for a in apps:
                if a.lower() in msgl: app_name = a; break
            
            await users_col.update_one({"uid": uid_str}, {
                "$set": {
                    "latest_otp": f"📱 **{app_name}**: `{codes[0]}`\n⏰ {datetime.datetime.now().strftime('%H:%M:%S')}",
                    "last_otp_timestamp": time.time()
                },
                "$inc": {"captured": 1}
            })
            new_otp_found = True
        
        if not manual:
            await seen_col.update_one({"key": key}, {"$set": {"at": time.time()}}, upsert=True)
    
    await users_col.update_one({"uid": uid_str}, {"$set": {"last_check": datetime.datetime.now().strftime("%H:%M:%S")}})
    
    last_ts = user.get("last_otp_timestamp", 0)
    is_recently_new = (time.time() - last_ts) < 40 
    
    if new_otp_found or manual or is_recently_new:
        await update_live_ui(uid_str, bot)
    return new_otp_found

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid_str = str(update.effective_user.id)
    await update.message.reply_text("🔄 Syncing Live Interface...", reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True))
    
    text, kb = await get_ui_content(uid_str)
    sent = await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    
    await users_col.update_one({"uid": uid_str}, {"$set": {"main_msg_id": sent.message_id}}, upsert=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid_str, msg = str(update.effective_user.id), update.message.text

    if "4/" in msg or len(msg) > 30:
        async with aiohttp.ClientSession() as s:
            data = {"client_id": CLIENT_ID, "client_secret": SECRET, "code": msg, "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI}
            async with s.post("https://oauth2.googleapis.com/token", data=data) as r:
                t = await r.json()
                if "access_token" in t:
                    async with s.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers={"Authorization": f"Bearer {t['access_token']}"}) as p:
                        prof = await p.json()
                        await users_col.update_one({"uid": uid_str}, {"$set": {
                            "email": prof["emailAddress"], 
                            "access": t["access_token"], 
                            "refresh": t.get("refresh_token", ""),
                            "captured": 0, "last_otp_timestamp": 0
                        }}, upsert=True)
                        user_data = await users_col.find_one({"uid": uid_str})
                        m_list = await fetch_unread(uid_str, user_data, s)
                        for m in m_list: await seen_col.update_one({"key": f"{uid_str}:{m['id']}"}, {"$set": {"at": time.time()}}, upsert=True)
                        await update_live_ui(uid_str, context.bot)
        try: await update.message.delete()
        except: pass

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid_str, data = str(q.from_user.id), q.data
    await q.answer()
    if data == "ui_refresh":
        async with aiohttp.ClientSession() as s: await process_user_emails(uid_str, context.bot, s, manual=True)
    elif data == "ui_gen":
        u = await users_col.find_one({"uid": uid_str})
        if u:
            user_part, dom = u["email"].split("@")
            mixed = "".join(c.upper() if random.getrandbits(1) else c.lower() for c in user_part)
            await users_col.update_one({"uid": uid_str}, {"$set": {"last_gen": f"{mixed}@{dom}"}})
            await update_live_ui(uid_str, context.bot)
    elif data == "ui_logout": await users_col.delete_one({"uid": uid_str}); await update_live_ui(uid_str, context.bot)
    elif data == "ui_clear": 
        await users_col.update_one({"uid": uid_str}, {"$set": {"latest_otp": "Cleared", "captured": 0, "last_otp_timestamp": 0}})
        await update_live_ui(uid_str, context.bot)

# --- HEALTH CHECK SERVER (FOR RAILWAY) ---
async def health_check(request): return web.Response(text="Bot is running")

# --- BACKGROUND WATCHER ---
async def watcher(app):
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                users = await users_col.find({"access": {"$exists": True}}).to_list(None)
                if users:
                    await asyncio.gather(*(process_user_emails(u["uid"], app.bot, session) for u in users), return_exceptions=True)
            except Exception as e:
                print(f"Watcher error: {e}")
            await asyncio.sleep(2)

# --- MAIN ---
async def main():
    # Start Dummy Web Server for Railway Health Check
    app_runner = web.AppRunner(web.Application())
    await app_runner.setup()
    await web.TCPSite(app_runner, '0.0.0.0', PORT).start()

    # Important: Small sleep to allow old instances to disconnect from Telegram
    await asyncio.sleep(2)

    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(on_callback))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(watcher(bot_app))
    
    print(f"--- BOT ONLINE (PORT: {PORT}) ---")
    
    # drop_pending_updates is critical here to resolve the Conflict error on startup
    await bot_app.updater.start_polling(drop_pending_updates=True)
    
    # Setup graceful shutdown signals
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
        
    await stop_event.wait()
    
    print("--- STOPPING BOT ---")
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

if __name__ == "__main__":
    try: 
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): 
        pass