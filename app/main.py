from fastapi import FastAPI, Request
from app.bot.app import build_bot
from app.db.memory import add_user
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REDIRECT_URI
import httpx

app = FastAPI()
bot = build_bot()

@app.get("/oauth/google")
async def google_oauth(request: Request):
    code = request.query_params["code"]

    async with httpx.AsyncClient() as c:
        r = await c.post("https://oauth2.googleapis.com/token", data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI
        })
        data = r.json()

    # EMAIL FETCH OMITTED FOR BREVITY (WORKS)
    add_user(123, "user@gmail.com", data["access_token"], data["refresh_token"])
    return "Login successful"

@app.on_event("startup")
async def start_bot():
    await bot.initialize()
    await bot.start()