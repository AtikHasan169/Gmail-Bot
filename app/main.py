import asyncio
from fastapi import FastAPI

from app.bot.app import build_bot
from app.gmail.watcher import gmail_watcher

app = FastAPI()
bot = build_bot()


@app.on_event("startup")
async def startup():
    # 🔹 Start Telegram polling in background
    asyncio.create_task(bot.run_polling())

    # 🔹 Start Gmail watcher
    asyncio.create_task(gmail_watcher(bot))


@app.get("/")
async def root():
    return {"status": "ok"}