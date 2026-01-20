import asyncio
import logging
import sys
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

# --- IMPORTS ---
from config import BOT_TOKEN, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, INSTANCE_ID, PORT
from database import db, update_user
from handlers import router, refresh_and_repost
from services import background_watcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- WEB SERVER HANDLER (The "Catcher") ---
async def handle_google_callback(request):
    """
    Google redirects the user here after login.
    We grab the 'code', match the 'state', and log them in.
    """
    code = request.query.get('code')
    state = request.query.get('state')
    
    if not code or not state:
        return web.Response(text="❌ Error: Missing code or state.")

    # 1. Verify the State (Security Check)
    oauth_record = await db.oauth_states.find_one({"state": state})
    if not oauth_record:
        return web.Response(text="❌ Error: Session expired or invalid. Please try again from the bot.")
        
    user_id = str(oauth_record['user_id'])

    # 2. Exchange Code for Access Token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data) as resp:
            token_data = await resp.json()
            
    if "error" in token_data:
        return web.Response(text=f"❌ Google Error: {token_data.get('error_description')}")

    # 3. Get User Profile (Email/Name)
    access_token = token_data['access_token']
    headers = {"Authorization": f"Bearer {access_token}"}
    
    user_email = "Connected"
    user_name = "User"
    
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://www.googleapis.com/oauth2/v1/userinfo?alt=json", headers=headers) as r:
                profile = await r.json()
                user_email = profile.get("email", user_email)
                user_name = profile.get("name", user_name)
    except: pass

    # 4. CLEANUP: Get old message ID before we overwrite the user data
    old_user_data = await db.users.find_one({"uid": user_id})

    # 5. Save New Data to Database
    await update_user(user_id, {
        "google_token": token_data,
        "access": access_token,
        "refresh": token_data.get("refresh_token"),
        "email": user_email,
        "name": user_name,
        "is_active": True,
        "captured": 0
    })
    
    # 6. UI Update (Delete Old -> Send New)
    try:
        # We need to access the bot instance from the app
        bot = request.app['bot']
        
        # A. Delete the old "Click to Connect" message
        if old_user_data and old_user_data.get("main_msg_id"):
            try:
                await bot.delete_message(chat_id=user_id, message_id=old_user_data["main_msg_id"])
            except Exception as e:
                # Message might already be deleted, which is fine
                pass

        # B. Send Success Message
        await bot.send_message(
            user_id, 
            f"✅ <b>Login Successful!</b>\nConnected as: <code>{user_email}</code>", 
            parse_mode="HTML"
        )
        
        # C. Force the dashboard to appear immediately
        await refresh_and_repost(bot, user_id)
        
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    # 7. Show Success Page in Browser
    html = """
    <html>
        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1 style="color: #2ecc71;">✅ Connected!</h1>
            <p>You can close this window and return to Telegram.</p>
            <script>window.close();</script>
        </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

# --- CONFLICT MONITOR (The Killer) ---
async def monitor_deployment_conflict():
    """Kills this process if a newer deployment starts."""
    lock_col = db['server_lock']
    while True:
        try:
            lock = await lock_col.find_one({"_id": "process_lock"})
            if lock and lock.get("active_id") != INSTANCE_ID:
                logger.warning(f"⚠️ New Instance Detected. Stopping old instance...")
                os._exit(0)
        except: pass
        await asyncio.sleep(10)

# --- MAIN APP ---
async def main():
    if not BOT_TOKEN:
        sys.exit("❌ Missing BOT_TOKEN")

    # 1. Register this instance as the Active One
    await db['server_lock'].update_one(
        {"_id": "process_lock"}, 
        {"$set": {"active_id": INSTANCE_ID}}, 
        upsert=True
    )
    logger.info(f"👑 Claimed Lock ID: {INSTANCE_ID[:8]}")
    logger.info("⏳ Waiting 5s for old instances to clear...")
    await asyncio.sleep(5)

    # 2. Start Bot
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # 3. Start Web Server
    app = web.Application()
    app['bot'] = bot # Attach bot to web app so we can message users
    
    # This route MUST match what you put in Google Console
    app.router.add_get('/auth/google', handle_google_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Bind to 0.0.0.0 so Railway can reach it
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌍 Server listening on Port {PORT}")
    logger.info(f"🔗 Callback URI: {REDIRECT_URI}")

    # 4. Start Background Tasks
    asyncio.create_task(monitor_deployment_conflict())
    asyncio.create_task(background_watcher(bot))

    # 5. Run
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot Stopped")
