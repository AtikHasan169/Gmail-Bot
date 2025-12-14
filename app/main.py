import asyncio
from fastapi import FastAPI, Request
import httpx

from app.bot.app import build_bot
from app.gmail.watcher import gmail_watcher
from app.db.memory import add_user
from app.core.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    REDIRECT_URI,
)

app = FastAPI()
bot = build_bot()


@app.on_event("startup")
async def startup():
    await bot.initialize()
    await bot.start()

    # 🔥 START BACKGROUND TASK PROPERLY
    asyncio.create_task(gmail_watcher(bot))


@app.get("/oauth/google")
async def google_oauth(request: Request):
    code = request.query_params.get("code")

    async with httpx.AsyncClient() as c:
        r = await c.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            },
        )

    data = r.json()

    # ⚠️ replace with real telegram_id + email later
    add_user(
        tg_id=123,
        email="user@gmail.com",
        access=data["access_token"],
        refresh=data.get("refresh_token"),
    )

    return "Login successful"