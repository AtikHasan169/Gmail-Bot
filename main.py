import asyncio
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties # <--- FIXED IMPORT
from aiogram.enums import ParseMode

from config import BOT_TOKEN, PORT
from handlers import router
from services import background_watcher, update_live_ui
from database import update_user
from auth import get_flow

logging.basicConfig(level=logging.INFO)

# --- WEB SERVER (Captures Login) ---
async def google_callback(request):
    code = request.query.get('code')
    uid = request.query.get('state')
    
    if not code or not uid:
        return web.Response(text="Error: Missing code or user state.")

    try:
        # 1. Exchange Code for Tokens using Google Module
        flow = get_flow(state=uid)
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # 2. Fetch Email Address
        async with aiohttp.ClientSession() as s:
            headers = {"Authorization": f"Bearer {creds.token}"}
            async with s.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers) as p:
                profile = await p.json()
                
                # 3. Save to Database
                await update_user(uid, {
                    "email": profile.get("emailAddress"),
                    "access": creds.token,
                    "refresh": creds.refresh_token,
                    "captured": 0,
                    "is_active": True,
                    "history_id": None # Reset history on new login
                })

        # 4. Notify User in Telegram
        bot = request.app['bot']
        await bot.send_message(uid, "✅ <b>Login Successful!</b>\n<i>You can close the browser now.</i>", parse_mode="HTML")
        await update_live_ui(bot, uid)
        
        return web.Response(text="Login Successful! You can close this window.")

    except Exception as e:
        return web.Response(text=f"Login Failed: {str(e)}")

# --- MAIN ---
async def main():
    # Fix: We wrap settings in DefaultBotProperties
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.include_router(router)
    
    # Setup Web Server
    app = web.Application()
    app['bot'] = bot
    app.router.add_get('/callback', google_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    print(f"✅ Server running on Port {PORT}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(background_watcher(bot))
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Stopped.")
