import asyncio
from fastapi import FastAPI
from app.bot.app import build_bot
from app.gmail.watcher import gmail_watcher
from app.admin.dashboard import router as admin_router
from app.gmail.watcher_push import router as gmail_push_router

app = FastAPI()
app.include_router(admin_router)
app.include_router(gmail_push_router)
bot_app = build_bot()

@app.on_event("startup")
async def startup():
    asyncio.create_task(bot_app.initialize())
    asyncio.create_task(bot_app.start())
    asyncio.create_task(gmail_watcher(bot_app))

@app.get("/")
async def root():
    return {"status": "ok"}