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

# --- WEB SERVER HANDLER ---
async def handle_google_callback(request):
    code = request.query.get('code')
    state = request.query.get('state')
    
    if not code or not state:
        return web.Response(text="❌ Error: Missing code or state.")

    # 1. Verify State
    oauth_record = await db.oauth_states.find_one({"state": state})
    if not oauth_record:
        return web.Response(text="❌ Error: Session expired. Please try again from the bot.")
        
    user_id = str(oauth_record['user_id'])

    # 2. Exchange Code for Token
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

    # 3. Get User Profile
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

    # 4. Clean up Old UI (Delete "Connect" Button)
    old_user_data = await db.users.find_one({"uid": user_id})
    bot = request.app['bot']
    
    if old_user_data and old_user_data.get("main_msg_id"):
        try: await bot.delete_message(chat_id=user_id, message_id=old_user_data["main_msg_id"])
        except: pass

    # 5. Save Data to DB
    await update_user(user_id, {
        "google_token": token_data,
        "access": access_token,
        "refresh": token_data.get("refresh_token"),
        "email": user_email,
        "name": user_name,
        "is_active": True,
        "captured": 0
    })
    
    # 6. Notify Telegram User
    try:
        await bot.send_message(user_id, f"✅ <b>Login Successful!</b>\nConnected: {user_email}", parse_mode="HTML")
        await refresh_and_repost(bot, user_id)
    except: pass

    # 7. THE "ZENOX MAIL" BRANDED REDIRECT PAGE
    # We fetch the username dynamically so the 'Open Telegram' button works for ANY bot
    bot_username = request.app.get('bot_username', 'GmailBot')
    tg_link = f"tg://resolve?domain={bot_username}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Zenox Mail</title> <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                background-color: #f0f2f5; 
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }}
            .card {{
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 300px;
            }}
            .icon {{ font-size: 50px; margin-bottom: 20px; }}
            h2 {{ margin: 0 0 10px 0; color: #1a1a1a; }}
            p {{ color: #666; margin-bottom: 30px; line-height: 1.5; }}
            .btn {{ 
                display: block; 
                background-color: #0088cc; 
                color: white; 
                padding: 14px 20px; 
                text-decoration: none; 
                border-radius: 12px; 
                font-weight: 600; 
                font-size: 16px;
                transition: background 0.2s;
            }}
            .btn:hover {{ background-color: #0077b5; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h2>Zenox Mail Connected!</h2> <p>Your Gmail is successfully linked.</p>
            <a href="{tg_link}" class="btn">Open Telegram</a>
        </div>

        <script>
            // Auto-redirect logic
            setTimeout(function() {{
                window.location.href = "{tg_link}";
            }}, 500);
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

# --- CONFLICT MONITOR ---
async def monitor_deployment_conflict():
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

    # 1. Lock Process
    await db['server_lock'].update_one(
        {"_id": "process_lock"}, 
        {"$set": {"active_id": INSTANCE_ID}}, 
        upsert=True
    )
    logger.info(f"👑 Claimed Lock ID: {INSTANCE_ID[:8]}")
    await asyncio.sleep(5)

    # 2. Start Bot & Detect Username
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    logger.info(f"🤖 Bot Detected: @{bot_username}")
    
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # 3. Start Web Server
    app = web.Application()
    app['bot'] = bot
    app['bot_username'] = bot_username # Save username for the redirect
    
    app.router.add_get('/auth/google', handle_google_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌍 Server listening on Port {PORT}")

    # 4. Start Tasks
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
