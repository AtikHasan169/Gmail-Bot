import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.bot.app import build_bot
from app.gmail.watcher import gmail_watcher

bot_app = build_bot()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ START TELEGRAM BOT (NO run_polling)
    await bot_app.initialize()
    await bot_app.start()

    # ✅ START GMAIL WATCHER
    asyncio.create_task(gmail_watcher(bot_app, interval=10))

    yield

    # ✅ CLEAN SHUTDOWN
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok"}