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
# --- ADDED: process_user and update_live_ui for direct editing ---
from services import background_watcher, process_user, update_live_ui 

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

    # 4. Clean up Old UI 
    # We do NOT delete the old message anymore. We will edit it below.
    bot = request.app['bot']
    
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
    
    # 6. Notify Telegram User (EDIT LOGIC)
    ui_updated = False
    
    try:
        # Step A: Find the old Auth Message ID
        user_data = await db.users.find_one({"uid": user_id})
        msg_id = user_data.get("main_msg_id") if user_data else None

        if msg_id:
            # Step B: Show "Syncing" status on the existing message
            try:
                await bot.edit_message_text(
                    chat_id=user_id, 
                    message_id=msg_id, 
                    text=f"✅ <b>Login Successful!</b>\nConnected: {user_email}\n🔄 Syncing emails...", 
                    parse_mode="HTML"
                )
                ui_updated = True
            except Exception as e:
                # If editing fails (message deleted?), we mark as failed to trigger fallback
                ui_updated = False

            # Step C: Fetch Data and Update to Dashboard
            if ui_updated:
                async with aiohttp.ClientSession() as s: 
                    await process_user(bot, user_id, s, manual=True)
                await update_live_ui(bot, user_id)

    except Exception as e:
        logger.error(f"UI Edit Failed: {e}")
        ui_updated = False

    # 7. Fallback (If edit failed, use old method)
    if not ui_updated:
        try:
            await bot.send_message(user_id, f"✅ <b>Login Successful!</b>\nConnected: {user_email}", parse_mode="HTML")
            await refresh_and_repost(bot, user_id)
        except: pass

    # 8. THE NEW "ZENOX MAIL" CONNECTED PAGE
    bot_username = request.app.get('bot_username', 'GmailBot')
    tg_link = f"tg://resolve?domain={bot_username}"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Zenox Mail | Connected</title>
        <style>
            :root {{
                --bg: #0f1115;
                --card: #181b21;
                --primary: #29b6f6;
                --text: #ffffff;
                --subtext: #8b9bb4;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
            }}
            .container {{
                background: var(--card);
                padding: 40px;
                border-radius: 24px;
                box-shadow: 0 20px 50px rgba(0,0,0,0.3);
                width: 90%;
                max-width: 320px;
                animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            }}
            .icon-box {{
                width: 80px;
                height: 80px;
                background: rgba(41, 182, 246, 0.1);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 20px;
            }}
            .checkmark {{
                font-size: 40px;
                color: var(--primary);
                animation: popIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) 0.3s backwards;
            }}
            h1 {{
                font-size: 24px;
                margin: 0 0 10px;
                font-weight: 700;
            }}
            p {{
                color: var(--subtext);
                font-size: 15px;
                margin: 0 0 30px;
                line-height: 1.5;
            }}
            .btn {{
                display: block;
                width: 100%;
                padding: 14px 0;
                background: linear-gradient(90deg, #29b6f6, #0088cc);
                color: white;
                text-decoration: none;
                border-radius: 12px;
                font-weight: 600;
                font-size: 16px;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .btn:active {{
                transform: scale(0.98);
            }}
            @keyframes slideUp {{
                from {{ opacity: 0; transform: translateY(30px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            @keyframes popIn {{
                from {{ opacity: 0; transform: scale(0.5); }}
                to {{ opacity: 1; transform: scale(1); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon-box">
                <div class="checkmark">✓</div>
            </div>
            <h1>Connected!</h1>
            <p>Your Gmail has been successfully linked to Zenox Mail.</p>
            <a href="{tg_link}" class="btn">Return to Telegram</a>
        </div>
        <script>
            // Auto-redirect after 1.5 seconds so user sees the success animation
            setTimeout(function() {{
                window.location.href = "{tg_link}";
            }}, 1500);
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
