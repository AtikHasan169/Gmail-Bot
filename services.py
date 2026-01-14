import time
import re
import asyncio
import datetime
import aiohttp
from base64 import urlsafe_b64decode
from email import message_from_bytes
from config import CLIENT_ID, CLIENT_SECRET
from database import users, seen_msgs, update_user, get_user
from keyboards import get_dashboard_ui, get_main_menu

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
    """
    Fetches and decodes the email body.
    Returns None if the request fails or body is empty.
    """
    headers = {"Authorization": f"Bearer {access}"}
    async with session.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=raw", headers=headers) as r:
        if r.status != 200: return None
        res = await r.json()
        raw = res.get("raw")
        if not raw: return None
        
        try:
            msg = message_from_bytes(urlsafe_b64decode(raw))
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        return part.get_payload(decode=True).decode(errors="ignore")
            return msg.get_payload(decode=True).decode(errors="ignore")
        except Exception:
            return None

async def update_live_ui(bot, uid):
    """
    Updates the Inline Dashboard Message.
    """
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
    """
    Main logic to check emails, find OTPs, and notify user.
    """
    user = await get_user(uid)
    if not user: return
    if not manual and not user.get("is_active", True): return

    access = user.get("access")
    headers = {"Authorization": f"Bearer {access}"}
    
    new_messages_ids = []
    
    # 1. FETCH MESSAGE LIST (History Sync or Full Scan)
    if manual or not user.get("history_id"):
        # Full scan (slower, used for manual refresh or first run)
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
                 # Update history ID for next time
                 async with session.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers) as p:
                     prof = await p.json()
                     if "historyId" in prof: await update_user(uid, {"history_id": prof["historyId"]})
    else:
        # Fast History Check
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

    # If no new messages, just update timestamp if manual
    if not new_messages_ids:
        if manual: 
            await update_user(uid, {"last_check": datetime.datetime.now().strftime("%H:%M:%S")})
            await update_live_ui(bot, uid)
        return

    # 2. FILTER ALREADY SEEN MESSAGES
    to_fetch = [mid for mid in new_messages_ids if not await seen_msgs.find_one({"key": f"{uid}:{mid}"})]
    if not to_fetch: return

    # 3. FETCH BODIES CONCURRENTLY
    tasks = [fetch_body_task(access, mid, session) for mid in to_fetch]
    bodies = await asyncio.gather(*tasks)
    
    new_otp = False
    
    for mid, body in zip(to_fetch, bodies):
        if not body: continue
        
        # Regex for 5-8 digit codes
        codes = re.findall(r"\b\d{5,8}\b", body)
        
        if codes:
            otp_code = codes[0]
            
            # Smart Service Detection
            app_name = "Service"
            lower_body = body.lower()
            known_apps = ["telegram", "google", "whatsapp", "facebook", "instagram", "discord", "twitter", "amazon", "tiktok", "netflix", "apple", "microsoft"]
            for app in known_apps:
                if app in lower_body: 
                    app_name = app.capitalize()
                    break
            
            # Format for Dashboard
            formatted_otp = (
                f"🏢 <b>{app_name}</b>\n"
                f"🔢 <code>{otp_code}</code>\n"
                f"⏰ <i>{datetime.datetime.now().strftime('%H:%M:%S')}</i>"
            )
            
            # Update Database
            await update_user(uid, {
                "latest_otp": formatted_otp, 
                "last_otp_timestamp": time.time()
            })
            await users.update_one({"uid": uid}, {"$inc": {"captured": 1}})
            new_otp = True
            
            # --- SEND NOTIFICATION WITH COPY BUTTON ---
            # This is the key part: We send a message to force the bottom keyboard to update
            kb = get_main_menu(copy_type="otp", value=otp_code)
            
            try:
                await bot.send_message(
                    uid, 
                    f"🔔 <b>OTP Received!</b>", 
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Failed to send alert to {uid}: {e}")

        # Mark as seen to avoid re-processing
        if not manual: 
            await seen_msgs.update_one({"key": f"{uid}:{mid}"}, {"$set": {"at": time.time()}}, upsert=True)

    await update_user(uid, {"last_check": datetime.datetime.now().strftime("%H:%M:%S")})
    
    # Update the Inline Dashboard if something new came in or if requested manually
    if new_otp or manual: 
        await update_live_ui(bot, uid)

async def background_watcher(bot):
    """
    Infinite loop to check emails for all active users.
    """
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Find users who have an access token and are active
                cursor = users.find({"access": {"$exists": True}, "is_active": True})
                user_list = await cursor.to_list(None)
                
                if user_list:
                    # Run checks for all users in parallel
                    await asyncio.gather(*(process_user(bot, u["uid"], session) for u in user_list), return_exceptions=True)
            except Exception as e:
                print(f"Watcher Error: {e}")
            
            # Wait 2 seconds before next cycle (Fast Polling)
            await asyncio.sleep(2)
