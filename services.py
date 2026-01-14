import time
import re
import asyncio
import datetime
import aiohttp
from base64 import urlsafe_b64decode
from email import message_from_bytes
from config import CLIENT_ID, CLIENT_SECRET
from database import users, seen_msgs, update_user, get_user
from keyboards import get_dashboard_ui

async def refresh_google_token(uid, session):
    user = await get_user(uid)
    if not user or not user.get("refresh"): return None
    
    data = {
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "refresh_token": user["refresh"], "grant_type": "refresh_token"
    }
    async with session.post("https://oauth2.googleapis.com/token", data=data) as r:
        res = await r.json()
        if "access_token" in res:
            await update_user(uid, {"access": res["access_token"]})
            return res["access_token"]
    return None

async def fetch_body_task(access, mid, session):
    headers = {"Authorization": f"Bearer {access}"}
    async with session.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=raw", headers=headers) as r:
        if r.status != 200: return None
        res = await r.json()
        raw = res.get("raw")
        if not raw: return None
        msg = message_from_bytes(urlsafe_b64decode(raw))
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(errors="ignore")
        return msg.get_payload(decode=True).decode(errors="ignore")

async def update_live_ui(bot, uid):
    text, kb = await get_dashboard_ui(uid)
    user = await get_user(uid)
    if not user or not user.get("main_msg_id"): return
    try:
        await bot.edit_message_text(
            chat_id=uid, message_id=user["main_msg_id"],
            text=text, reply_markup=kb, parse_mode="HTML"
        )
    except Exception: pass

async def process_user(bot, uid, session, manual=False):
    user = await get_user(uid)
    if not user: return
    if not manual and not user.get("is_active", True): return

    access = user.get("access")
    headers = {"Authorization": f"Bearer {access}"}
    
    new_messages_ids = []
    
    # 1. HISTORY CHECK (Fast) or FULL SCAN (Manual/First Run)
    if manual or not user.get("history_id"):
        params = {"q": "is:unread", "maxResults": 5}
        async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=params, headers=headers) as r:
             if r.status == 401:
                 access = await refresh_google_token(uid, session)
                 if not access: return
                 headers["Authorization"] = f"Bearer {access}"
                 async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=params, headers=headers) as r2:
                     res = await r2.json()
             else:
                 res = await r.json()
             
             if "messages" in res:
                 new_messages_ids = [m['id'] for m in res["messages"]]
                 async with session.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers) as p:
                     prof = await p.json()
                     if "historyId" in prof: await update_user(uid, {"history_id": prof["historyId"]})
    else:
        history_id = user.get("history_id")
        params = {"startHistoryId": history_id, "historyTypes": "messageAdded"}
        async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/history", params=params, headers=headers) as r:
            if r.status == 401:
                access = await refresh_google_token(uid, session)
                if not access: return
                headers["Authorization"] = f"Bearer {access}"
                async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/history", params=params, headers=headers) as r2:
                    res = await r2.json()
            else:
                res = await r.json()

            if "historyId" in res: await update_user(uid, {"history_id": res["historyId"]})
            if "history" in res:
                for h in res["history"]:
                    if "messagesAdded" in h:
                        for m in h["messagesAdded"]:
                            new_messages_ids.append(m["message"]["id"])

    if not new_messages_ids:
        if manual: 
            await update_user(uid, {"last_check": datetime.datetime.now().strftime("%H:%M:%S")})
            await update_live_ui(bot, uid)
        return

    # 2. PROCESS NEW MESSAGES
    to_fetch = [mid for mid in new_messages_ids if not await seen_msgs.find_one({"key": f"{uid}:{mid}"})]
    if not to_fetch: return

    tasks = [fetch_body_task(access, mid, session) for mid in to_fetch]
    bodies = await asyncio.gather(*tasks)
    
    new_otp = False
    for mid, body in zip(to_fetch, bodies):
        if not body: continue
        codes = re.findall(r"\b\d{5,8}\b", body)
        if codes:
            app_name = "Service"
            lower_body = body.lower()
            for app in ["telegram", "google", "whatsapp", "facebook", "instagram", "discord", "twitter", "amazon", "tiktok"]:
                if app in lower_body: app_name = app.capitalize(); break
            
            formatted_otp = (
                f"📨 <b>Service:</b> {app_name}\n"
                f"🔢 <b>Code:</b> <code>{codes[0]}</code>\n"
                f"⏰ <i>{datetime.datetime.now().strftime('%H:%M:%S')}</i>"
            )
            await update_user(uid, {"latest_otp": formatted_otp, "last_otp_timestamp": time.time()})
            await users.update_one({"uid": uid}, {"$inc": {"captured": 1}})
            new_otp = True
        
        if not manual: await seen_msgs.update_one({"key": f"{uid}:{mid}"}, {"$set": {"at": time.time()}}, upsert=True)

    await update_user(uid, {"last_check": datetime.datetime.now().strftime("%H:%M:%S")})
    if new_otp or manual: await update_live_ui(bot, uid)

async def background_watcher(bot):
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                cursor = users.find({"access": {"$exists": True}, "is_active": True})
                user_list = await cursor.to_list(None)
                if user_list:
                    await asyncio.gather(*(process_user(bot, u["uid"], session) for u in user_list), return_exceptions=True)
            except Exception as e:
                print(f"Watcher Error: {e}")
            await asyncio.sleep(1)
