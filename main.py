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
from database import db, client 
from handlers import router
from services import background_watcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- WEB SERVER HANDLER (The "Catcher") ---
async def handle_google_callback(request):
    """
    Google sends the user here after they click 'Allow'.
    We grab the code, find who the user is, and save the token.
    """
    code = request.query.get('code')
    state = request.query.get('state')
    
    if not code or not state:
        return web.Response(text="❌ Error: Missing code or state.")

    # 1. Find who this state belongs to (The Secret Link)
    oauth_record = await db.oauth_states.find_one({"state": state})
    if not oauth_record:
        return web.Response(text="❌ Error: Invalid or expired login session.")
        
    user_id = str(oauth_record['user_id'])

    # 2. Exchange Code for Token (Back-channel to Google)
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

    # 3. Success! Save tokens to the User
    # We fetch their profile info quickly to greet them
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

    await db.users.update_one(
        {"uid": user_id},
        {"$set": {
            "google_token": token_data, # Store full token data
            "access": access_token,
            "refresh": token_data.get("refresh_token"),
            "email": user_email,
            "name": user_name,
            "is_active": True,
            "captured": 0
        }},
        upsert=True
    )
    
    # 4. Notify User on Telegram
    try:
        # We need to access the bot instance from the app
        bot = request.app['bot']
        await bot.send_message(
            user_id, 
            f"✅ <b>Login Successful!</b>\n\nConnected as: <code>{user_email}</code>\n<i>You can now return to the chat.</i>", 
            parse_mode="HTML"
        )
        
        # Trigger a dashboard refresh
        from handlers import refresh_and_repost
        await refresh_and_repost(bot, user_id)
        
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    # 5. Show Success Page in Browser
    html_content = """
    <html>
        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1 style="color: green;">✅ Login Successful!</h1>
            <p>Your Gmail account is now connected to the bot.</p>
            <p>You can close this window.</p>
            <script>window.close();</script>
        </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

# --- CONFLICT MONITOR ---
async def monitor_deployment_conflict():
    lock_col = db['server_lock']
    while True:
        try:
            lock = await lock_col.find_one({"_id": "process_lock"})
            if lock and lock.get("active_id") != INSTANCE_ID:
                logger.warning(f"⚠️ New Bot Detected. Shutting down...")
                os._exit(0)
        except: pass
        await asyncio.sleep(10)

# --- MAIN ENTRY POINT ---
async def main():
    if not BOT_TOKEN:
        sys.exit("❌ Missing BOT_TOKEN")

    # 1. Database & Highlander Lock
    await db['server_lock'].update_one(
        {"_id": "process_lock"}, {"$set": {"active_id": INSTANCE_ID}}, upsert=True
    )
    logger.info(f"👑 Claimed Process Lock. ID: {INSTANCE_ID[:8]}")
    logger.info("⏳ Waiting 5s for old instance to stop...")
    await asyncio.sleep(5)
    
    # 2. Setup Bot
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # 3. Setup Web Server (aiohttp)
    app = web.Application()
    app['bot'] = bot # Store bot so the web handler can use it
    
    # This route MUST match what you put in Google Console
    app.router.add_get('/auth/google', handle_google_callback) 
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Bind to 0.0.0.0 so Railway can reach it on the assigned PORT
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌍 Web Server running on Port {PORT}")
    logger.info(f"🔗 Waiting for Google at: {REDIRECT_URI}")

    # 4. Start Background Tasks
    asyncio.create_task(monitor_deployment_conflict())
    asyncio.create_task(background_watcher(bot))
    
    # 5. Start Polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🤖 Bot Started Polling...")
    
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
