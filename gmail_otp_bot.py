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
# IMPORTANT: This must match your Google Console exactly
REDIRECT_URI = "https://gmail-bot-production.up.railway.app/oauth/callback"

# --- DATABASE SETUP ---
if not MONGO_URI:
    print("CRITICAL: MONGO_URI environment variable is missing.")
    sys.exit(1)

client = AsyncIOMotorClient(MONGO_URI)
db = client['gmail_otp_bot']
users_col = db['users']
seen_col = db['seen_messages']

# --- HTML TEMPLATES ---
PRIVACY_POLICY_HTML = """
<!DOCTYPE html>
<html>
<head><title>Privacy Policy - Gmail OTP Bot</title></head>
<body style="font-family: sans-serif; padding: 40px; line-height: 1.6; max-width: 800px; margin: auto;">
    <h1>Privacy Policy</h1>
    <p>This bot accesses your Gmail inbox for the sole purpose of detecting and displaying OTP codes to you in Telegram.</p>
    <h2>Data Usage</h2>
    <ul>
        <li>We only read emails marked as "unread".</li>
        <li>We extract numeric codes (5-10 digits).</li>
        <li>Tokens are stored securely in our private database.</li>
    </ul>
    <h2>Security</h2>
    <p>We do not store your actual emails, only the detected codes during the active session.</p>
</body>
</html>
"""

SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Success!</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #2ecc71;">✅ Successfully Linked!</h1>
    <p>Your Gmail account is now connected.</p>
    <p>Return to Telegram to start monitoring.</p>
    <script>setTimeout(() => { window.close(); }, 3000);</script>
</body>
</html>
"""

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head><title>Gmail Bot Server</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1>🤖 Gmail OTP Bot Server</h1>
    <p>This server handles OAuth redirects for the Telegram Bot.</p>
    <p><a href="/privacy">Privacy Policy</a></p>
    <hr>
    <p style="color: gray;">Status: Online</p>
</body>
</html>
"""

# --- UI GENERATOR ---
async def get_ui_content(uid_str):
    user = await users_col.find_one({"uid": uid_str})
    
    if not user or not user.get("access"):
        # We pass the Telegram UID in the 'state' parameter
        url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            "&response_type=code"
            "&scope=https://www.googleapis.com/auth/gmail.readonly"
            "&access_type=offline&prompt=consent"
            f"&state={uid_str}"
        )
        text = "❌ **Account Not Linked**\n\nPlease login using the button below to start monitoring."
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
        f"⚠️ _All updates edit this message. Session active._"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Force Scan", callback_data="ui_refresh"),
         InlineKeyboardButton("✨ Gen Alias", callback_data="ui_gen")],
        [InlineKeyboardButton("🛑 Logout", callback_data="ui_logout"),
         InlineKeyboardButton("🗑 Clear Logs", callback_data="ui_clear")]
    ])
    
    return text, kb

# --- WEB HANDLERS ---
async def handle_index(request):
    return web.Response(text=INDEX_HTML, content_type='text/html')

async def handle_privacy(request):
    return web.Response(text=PRIVACY_POLICY_HTML, content_type='text/html')

async def handle_oauth_callback(request):
    code = request.query.get("code")
    uid_str = request.query.get("state") # This is our Telegram UID
    
    if not code:
        # If human visits this directly, give instructions instead of raw error
        return web.Response(text="""
        <html><body style="font-family:sans-serif; text-align:center; padding:50px;">
        <h2>⚠️ Direct Access Detected</h2>
        <p>This URL is used automatically by Google during login.</p>
        <p>Please open your <b>Telegram Bot</b> and click the Login button there.</p>
        </body></html>
        """, content_type='text/html', status=200)
    
    if not uid_str:
        return web.Response(text="Error: State parameter (UID) is missing. Please restart login from Telegram.", status=400)

    try:
        async with aiohttp.ClientSession() as session:
            # Exchange code for token
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": CLIENT_ID,
                "client_secret": SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI
            }
            async with session.post(token_url, data=data) as r:
                token_data = await r.json()
                
            if "access_token" in token_data:
                access_token = token_data["access_token"]
                refresh_token = token_data.get("refresh_token")
                
                # Fetch Email
                headers = {"Authorization": f"Bearer {access_token}"}
                async with session.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers) as p:
                    profile = await p.json()
                    email = profile["emailAddress"]

                # Update DB
                await users_col.update_one({"uid": uid_str}, {"$set": {
                    "email": email,
                    "access": access_token,
                    "refresh": refresh_token,
                    "is_active": True,
                    "captured": 0,
                    "last_otp_timestamp": 0
                }}, upsert=True)
                
                # Notify User in Telegram
                bot = request.app['bot']
                await bot.send_message(int(uid_str), f"✅ **Linked Account:** `{email}`\nMonitoring is now active.")
                
                # Refresh UI message
                await update_live_ui(uid_str, bot)
                
                return web.Response(text=SUCCESS_HTML, content_type='text/html')
            else:
                desc = token_data.get('error_description', 'Token exchange failed')
                return web.Response(text=f"OAuth Error: {desc}", status=500)
                
    except Exception as e:
        return web.Response(text=f"Server Error: {str(e)}", status=500)

# --- CORE LOGIC ---
async def update_live_ui(uid_str, bot):
    user = await users_col.find_one({"uid": uid_str})
    if not user or not user.get("main_msg_id"): return
    text, kb = await get_ui_content(uid_str)
    try:
        await bot.edit_message_text(
            chat_id=int(uid_str),
            message_id=user["main_msg_id"],
            text=text,
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception: pass

async def process_emails(uid_str, bot, session, manual=False):
    user = await users_col.find_one({"uid": uid_str})
    if not user or not user.get("access"): return False
    if not manual and not user.get("is_active", True): return False

    headers = {"Authorization": f"Bearer {user['access']}"}
    p = {"q": "is:unread", "maxResults": 10}
    
    async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=p, headers=headers) as r:
        if r.status == 401:
            # Refresh Token logic
            if not user.get("refresh"): return False
            refresh_data = {
                "client_id": CLIENT_ID, "client_secret": SECRET,
                "refresh_token": user["refresh"], "grant_type": "refresh_token"
            }
            async with session.post("https://oauth2.googleapis.com/token", data=refresh_data) as tr:
                tr_json = await tr.json()
                if "access_token" in tr_json:
                    new_at = tr_json["access_token"]
                    await users_col.update_one({"uid": uid_str}, {"$set": {"access": new_at}})
                    headers["Authorization"] = f"Bearer {new_at}"
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
                lower_body = body.lower()
                for a in ["Telegram", "Google", "WhatsApp", "Amazon", "Facebook", "Instagram", "Apple", "Microsoft"]:
                    if a.lower() in lower_body: app = a; break
                
                await users_col.update_one({"uid": uid_str}, {
                    "$set": {
                        "latest_otp": f"📱 **{app}**: `{codes[0]}`\n⏰ {datetime.datetime.now().strftime('%H:%M:%S')}",
                        "last_otp_timestamp": time.time()
                    },
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
            try:
                users = await users_col.find({"access": {"$exists": True}, "is_active": True}).to_list(None)
                if users:
                    await asyncio.gather(*(process_emails(u["uid"], app.bot, session) for u in users), return_exceptions=True)
            except Exception: pass
            await asyncio.sleep(4)

# --- MAIN ---
async def main():
    webapp = web.Application()
    webapp.add_routes([
        web.get('/', handle_index),
        web.get('/oauth/callback', handle_oauth_callback),
        web.get('/privacy', handle_privacy)
    ])
    
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    webapp['bot'] = bot_app.bot # Attach bot to webapp for callback notifications
    
    runner = web.AppRunner(webapp)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    await asyncio.sleep(10) # Railway cooldown
    await bot_app.bot.delete_webhook()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(on_callback))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(watcher(bot_app))
    
    print(f"--- BOT & WEB SERVER ONLINE (PORT: {PORT}) ---")
    
    # Simple conflict handling
    try:
        await bot_app.updater.start_polling(drop_pending_updates=True)
    except Conflict:
        print("Conflict detected, retrying...")
        await asyncio.sleep(5)
        await bot_app.updater.start_polling(drop_pending_updates=True)

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stop_event.set)
    await stop_event.wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except: pass