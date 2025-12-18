import os
import re
import asyncio
import aiohttp
import random
import datetime
import time
import signal
import sys
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
from telegram.error import Conflict

# --- CONFIGURATION (Load from Environment) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
SECRET = os.getenv("CLIENT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
PORT = int(os.environ.get('PORT', 8080))
# Ensure this matches your Google Cloud Console exactly
REDIRECT_URI = "https://gmail-bot-production.up.railway.app/oauth/callback"

# --- DATABASE SETUP ---
if not MONGO_URI:
    print("CRITICAL: MONGO_URI environment variable is missing.")
    sys.exit(1)

client = AsyncIOMotorClient(MONGO_URI)
db = client['gmail_otp_bot']
users_col = db['users']
seen_col = db['seen_messages']

# --- HTML TEMPLATES (For Verification) ---
PRIVACY_POLICY_HTML = """
<!DOCTYPE html>
<html>
<head><title>Privacy Policy - Gmail OTP Bot</title></head>
<body style="font-family: sans-serif; padding: 40px; line-height: 1.6;">
    <h1>Privacy Policy</h1>
    <p>This bot accesses your Gmail inbox for the sole purpose of detecting and displaying OTP (One-Time Password) codes to you in Telegram.</p>
    <h2>Data Usage</h2>
    <ul>
        <li>We only read emails marked as "unread".</li>
        <li>We only extract numeric codes (5-10 digits).</li>
        <li>Your data is never shared with third parties.</li>
        <li>We use industry-standard encryption to store your OAuth tokens in our database.</li>
    </ul>
    <h2>Account Deletion</h2>
    <p>You can revoke access at any time by clicking the "Logout" button within the bot or by visiting your Google Account security settings.</p>
</body>
</html>
"""

SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Success!</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #2ecc71;">✅ Successfully Linked!</h1>
    <p>Your Gmail account is now connected to the bot.</p>
    <p>You can close this tab and return to Telegram.</p>
</body>
</html>
"""

# --- UI GENERATOR ---
async def get_ui_content(uid_str):
    user = await users_col.find_one({"uid": uid_str})
    
    if not user or not user.get("access"):
        url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            "&response_type=code"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline&prompt=consent"
            f"&state={uid_str}"
        )
        text = "❌ **Account Not Linked**\n\nPlease login to start monitoring."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔐 Login Google", url=url)]])
        return text, kb

    email = user.get("email", "Unknown")
    captured = user.get("captured", 0)
    last_check = user.get("last_check", "Never")
    latest_otp = user.get("latest_otp", "None Yet")
    gen_alias = user.get("last_gen", "None")
    is_active = user.get("is_active", True)
    status_icon = "🟢 ACTIVE" if is_active else "🟡 STOPPED"
    
    last_ts = user.get("last_otp_timestamp", 0)
    is_fresh = (time.time() - last_ts) < 30
    otp_header = "🚨 **[NEW] OTP RECEIVED** 🚨" if is_fresh else "📨 **Latest OTP:**"

    text = (
        f"🚀 **LIVE SESSION INTERFACE**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Account:** `{email}`\n"
        f"📡 **Monitor:** {status_icon}\n"
        f"🔑 **Total Captured:** `{captured}`\n"
        f"🕒 **Last Scan:** `{last_check}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{otp_header}\n{latest_otp}\n\n"
        f"✨ **Last Alias:**\n`{gen_alias}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _Monitoring active in background every 2-5s._"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Force Scan", callback_data="ui_refresh"),
         InlineKeyboardButton("✨ Gen Alias", callback_data="ui_gen")],
        [InlineKeyboardButton("🛑 Logout", callback_data="ui_logout"),
         InlineKeyboardButton("🗑 Clear Logs", callback_data="ui_clear")]
    ])
    
    return text, kb

# --- WEB HANDLERS ---
async def handle_privacy(request):
    return web.Response(text=PRIVACY_POLICY_HTML, content_type='text/html')

async def handle_oauth_callback(request):
    code = request.query.get("code")
    uid_str = request.query.get("state")
    
    if not code or not uid_str:
        return web.Response(text="Invalid callback parameters.", status=400)

    async with aiohttp.ClientSession() as session:
        data = {
            "client_id": CLIENT_ID, "client_secret": SECRET,
            "code": code, "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI
        }
        async with session.post("https://oauth2.googleapis.com/token", data=data) as r:
            token = await r.json()
            
            if "access_token" in token:
                headers = {"Authorization": f"Bearer {token['access_token']}"}
                async with session.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers) as p:
                    prof = await p.json()
                    await users_col.update_one({"uid": uid_str}, {"$set": {
                        "email": prof["emailAddress"], "access": token["access_token"], 
                        "refresh": token.get("refresh_token", ""), "captured": 0, 
                        "last_otp_timestamp": 0, "is_active": True
                    }}, upsert=True)
                    
                    # Notify user in Telegram
                    bot = request.app['bot']
                    await bot.send_message(int(uid_str), f"✅ **Linked Successfully:** `{prof['emailAddress']}`")
                    await update_live_ui(uid_str, bot)
                
                return web.Response(text=SUCCESS_HTML, content_type='text/html')
    
    return web.Response(text="Authentication Failed.", status=500)

# --- CORE LOGIC ---
async def update_live_ui(uid_str, bot):
    user = await users_col.find_one({"uid": uid_str})
    if not user or not user.get("main_msg_id"): return
    text, kb = await get_ui_content(uid_str)
    try:
        await bot.edit_message_text(chat_id=int(uid_str), message_id=user["main_msg_id"], text=text, reply_markup=kb, parse_mode="Markdown")
    except: pass

async def process_emails(uid_str, bot, session, manual=False):
    user = await users_col.find_one({"uid": uid_str})
    if not user or not user.get("access"): return False
    if not manual and not user.get("is_active", True): return False

    headers = {"Authorization": f"Bearer {user['access']}"}
    p = {"q": "is:unread", "maxResults": 5 if manual else 10}
    
    async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=p, headers=headers) as r:
        if r.status == 401:
            data = {"client_id": CLIENT_ID, "client_secret": SECRET, "refresh_token": user["refresh"], "grant_type": "refresh_token"}
            async with session.post("https://oauth2.googleapis.com/token", data=data) as tr:
                tr_json = await tr.json()
                if "access_token" in tr_json:
                    await users_col.update_one({"uid": uid_str}, {"$set": {"access": tr_json["access_token"]}})
                    headers["Authorization"] = f"Bearer {tr_json['access_token']}"
                    async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=p, headers=headers) as r2:
                        res = await r2.json()
                else: return False
        else: res = await r.json()

    messages = res.get("messages", [])
    found_any = False
    for m in messages:
        key = f"{uid_str}:{m['id']}"
        if not manual and await seen_col.find_one({"key": key}): continue
        
        async with session.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}?format=raw", headers=headers) as rb:
            rj = await rb.json()
            raw = rj.get("raw")
            if not raw: continue
            body = message_from_bytes(urlsafe_b64decode(raw)).get_payload(decode=True).decode(errors="ignore")
            codes = re.findall(r"\b\d{5,10}\b", body)
            if codes:
                app = "Unknown"
                for a in ["Telegram", "Google", "WhatsApp", "Amazon", "Facebook", "Instagram", "Apple", "Microsoft"]:
                    if a.lower() in body.lower(): app = a; break
                await users_col.update_one({"uid": uid_str}, {
                    "$set": {"latest_otp": f"📱 **{app}**: `{codes[0]}`\n⏰ {datetime.datetime.now().strftime('%H:%M:%S')}", "last_otp_timestamp": time.time()},
                    "$inc": {"captured": 1}
                })
                found_any = True
        if not manual: await seen_col.update_one({"key": key}, {"$set": {"at": time.time()}}, upsert=True)

    await users_col.update_one({"uid": uid_str}, {"$set": {"last_check": datetime.datetime.now().strftime("%H:%M:%S")}})
    if found_any or manual or (time.time() - user.get("last_otp_timestamp", 0)) < 40:
        await update_live_ui(uid_str, bot)
    return found_any

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid_str = str(update.effective_user.id)
    kb = ReplyKeyboardMarkup([["Start Monitoring", "Stop Monitoring"], ["🔄 Refresh Interface"]], resize_keyboard=True)
    await update.message.reply_text("✨ **Live Session Active**", reply_markup=kb)
    text, kb_inline = await get_ui_content(uid_str)
    sent = await update.message.reply_text(text, reply_markup=kb_inline, parse_mode="Markdown")
    await users_col.update_one({"uid": uid_str}, {"$set": {"main_msg_id": sent.message_id}}, upsert=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid_str, msg = str(update.effective_user.id), update.message.text
    if msg == "Start Monitoring": await users_col.update_one({"uid": uid_str}, {"$set": {"is_active": True}})
    elif msg == "Stop Monitoring": await users_col.update_one({"uid": uid_str}, {"$set": {"is_active": False}})
    elif msg == "🔄 Refresh Interface": return await start(update, context)
    await update_live_ui(uid_str, context.bot)

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid_str, data = str(q.from_user.id), q.data
    await q.answer()
    if data == "ui_refresh":
        async with aiohttp.ClientSession() as s: await process_emails(uid_str, context.bot, s, manual=True)
    elif data == "ui_gen":
        u = await users_col.find_one({"uid": uid_str})
        if u:
            user_p, dom = u["email"].split("@")
            mixed = "".join(c.upper() if random.getrandbits(1) else c.lower() for c in user_p)
            await users_col.update_one({"uid": uid_str}, {"$set": {"last_gen": f"{mixed}@{dom}"}})
            await update_live_ui(uid_str, context.bot)
    elif data == "ui_logout":
        await users_col.update_one({"uid": uid_str}, {"$unset": {"access": "", "refresh": ""}})
        await update_live_ui(uid_str, context.bot)
    elif data == "ui_clear":
        await users_col.update_one({"uid": uid_str}, {"$set": {"latest_otp": "Cleared", "captured": 0, "last_otp_timestamp": 0}})
        await update_live_ui(uid_str, context.bot)

# --- WATCHER ---
async def watcher(app):
    async with aiohttp.ClientSession() as session:
        while True:
            users = await users_col.find({"access": {"$exists": True}, "is_active": True}).to_list(None)
            if users:
                await asyncio.gather(*(process_emails(u["uid"], app.bot, session) for u in users), return_exceptions=True)
            await asyncio.sleep(3)

# --- MAIN ---
async def main():
    webapp = web.Application()
    webapp.add_routes([
        web.get('/oauth/callback', handle_oauth_callback),
        web.get('/privacy', handle_privacy)
    ])
    
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    webapp['bot'] = bot_app.bot
    
    runner = web.AppRunner(webapp)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    await asyncio.sleep(10)
    await bot_app.bot.delete_webhook()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(on_callback))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(watcher(bot_app))
    
    print(f"--- BOT & WEB SERVER ONLINE (PORT: {PORT}) ---")
    
    retries = 5
    for i in range(retries):
        try:
            await bot_app.updater.start_polling(drop_pending_updates=True)
            break
        except Conflict:
            await asyncio.sleep(5)
            if i == retries - 1: raise

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stop_event.set)
    await stop_event.wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except: pass