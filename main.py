import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

# --- IMPORTS ---
from config import BOT_TOKEN, INSTANCE_ID
from database import client  # Needs raw client for the lock
from handlers import router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- THE KILLER FUNCTION ---
async def monitor_deployment_conflict():
    """
    Checks DB every 10s. If I am not the 'Active ID', I kill myself.
    """
    db = client['gmail_otp_bot'] 
    lock_col = db['server_lock'] 
    
    logger.info(f"🛡 Conflict Monitor Started. My ID: {INSTANCE_ID[:8]}")
    
    while True:
        try:
            lock = await lock_col.find_one({"_id": "process_lock"})
            
            # If lock exists AND it is NOT my ID -> Die
            if lock and lock.get("active_id") != INSTANCE_ID:
                logger.warning(f"⚠️ New Bot Detected ({lock.get('active_id')[:8]}). Shutting down Old Bot...")
                os._exit(0) # Force kill this script
                
        except Exception as e:
            logger.error(f"Monitor Error: {e}")
            
        await asyncio.sleep(10)

async def main():
    # 1. CLAIM LEADERSHIP
    # Before logging in, tell the DB: "I am the new boss."
    db = client['gmail_otp_bot']
    await db['server_lock'].update_one(
        {"_id": "process_lock"},
        {"$set": {"active_id": INSTANCE_ID}},
        upsert=True
    )
    logger.info(f"👑 Claimed Process Lock. ID: {INSTANCE_ID[:8]}")

    # 2. WAIT FOR OLD BOT TO DIE
    # Give the old Railway instance 10 seconds to read the DB and kill itself.
    logger.info("⏳ Waiting 10s for old instance to stop...")
    await asyncio.sleep(10)

    # 3. START BOT
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Start the self-destruct monitor
    asyncio.create_task(monitor_deployment_conflict())

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Gmail Bot Started Successfully")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot Stopped")
