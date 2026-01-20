import time
import re
import asyncio
import datetime
import aiohttp
from base64 import urlsafe_b64decode
from email import message_from_bytes
from config import CLIENT_ID, CLIENT_SECRET
from database import users, seen_msgs, update_user, get_user
# We import UI update functions to refresh the dashboard when new mail arrives
# Note: We import inside functions or use standard imports to avoid circular dependency issues if possible
# But for this structure, we will assume keyboards/handlers are accessible.

# --- CONSTANTS ---
TIMEOUT = aiohttp.ClientTimeout(total=5) # 5 seconds max per request
BD_TZ = datetime.timezone(datetime.timedelta(hours=6))

async def refresh_google_token(uid, session):
    """
    If the access token expires (401 Error), this uses the Refresh Token to get a new one.
    """
    user = await get_user(uid)
    if not user or not user.get("refresh"): return None
    
    data = {
        "client_id": CLIENT_ID, 
        "client_secret": CLIENT_SECRET, 
        "refresh_token": user["refresh"], 
        "grant_type": "refresh_token"
    }
    
    try:
        async with session.post("https://oauth2.googleapis.com/token", data=data, timeout=TIMEOUT) as r:
            res = await r.json()
            if "access_token" in res:
                # Save the new token so we don't have to refresh again for an hour
                await update_user(uid, {"access": res["access_token"]})
                return res["access_token"]
    except: pass
    return None

async def fetch_body_task(access, mid, session):
    """
    Fetches the actual text content of a specific email ID.
    """
    headers = {"Authorization": f"Bearer {access}"}
    try:
        async with session.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=raw", headers=headers, timeout=TIMEOUT) as r:
            if r.status != 200: return None
            res = await r.json()
            raw = res.get("raw")
            if not raw: return None
            
            try:
                # Decode the raw email bytes
                msg = message_from_bytes(urlsafe_b64decode(raw))
                
                # If multipart, look for the text/plain part
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain": 
                            return part.get_payload(decode=True).decode(errors="ignore")
                
                # If simple email, just get payload
                return msg.get_payload(decode=True).decode(errors="ignore")
            except: return None
    except: return None

async def update_live_ui(bot, uid):
    """
    Refreshes the dashboard message in the chat.
    We import 'get_dashboard_ui' here to avoid circular imports at top level.
    """
    from keyboards import get_dashboard_ui
    text, kb = await get_dashboard_ui(uid)
    
    user = await get_user(uid)
    if not user or not user.get("main_msg_id"): return
    
    try: 
        await bot.edit_message_text(
            chat_id=uid, 
            message_id=user["main_msg_id"], 
            text=text, 
            reply_markup=kb, 
            parse_mode="HTML"
        )
    except: pass

async def process_user(bot, uid, session, manual=False):
    """
    The Core Worker: Checks Gmail for new messages.
    """
    user = await get_user(uid)
    if not user: return
    # If not manual check, skip inactive users
    if not manual and not user.get("is_active", True): return

    access = user.get("access")
    if not access: return

    headers = {"Authorization": f"Bearer {access}"}
    new_ids = []
    
    try:
        # Fetch only the LATEST unread message (maxResults=1) for speed
        params = {"q": "is:unread newer_than:1d", "maxResults": 1}
        
        async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=params, headers=headers, timeout=TIMEOUT) as r:
                # If token expired, refresh and try once more
                if r.status == 401:
                    access = await refresh_google_token(uid, session)
                    if not access: return
                    headers["Authorization"] = f"Bearer {access}"
                    async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=params, headers=headers, timeout=TIMEOUT) as r2: 
                        res = await r2.json()
                else: 
                    res = await r.json()
                
                if "messages" in res:
                    new_ids = [m['id'] for m in res["messages"]]

    except: pass

    if not new_ids:
        if manual: 
            # Just update timestamp if manual check found nothing
            await update_user(uid, {"last_check": datetime.datetime.now(BD_TZ).strftime("%I:%M:%S %p")})
        return

    # Filter out messages we have already processed
    to_fetch = [mid for mid in new_ids if not await seen_msgs.find_one({"key": f"{uid}:{mid}"})]
    if not to_fetch: return

    # Fetch bodies in parallel
    tasks = [fetch_body_task(access, mid, session) for mid in to_fetch]
    bodies = await asyncio.gather(*tasks)
    
    new_otp = False
    for mid, body in zip(to_fetch, bodies):
        if not body: continue
        
        # Regex to find OTPs (5-8 digits)
        codes = re.findall(r"\b\d{5,8}\b", body)
        if codes:
            otp_code = codes[0]
            
            formatted = (
                f"✨ <b>New OTP Received</b>\n"
                f"⏰ {datetime.datetime.now(BD_TZ).strftime('%I:%M:%S %p')}"
            )
            
            await update_user(uid, {
                "latest_otp": formatted, 
                "last_otp_raw": otp_code,
                "last_otp_timestamp": time.time()
            })
            # Increment total hits
            await users.update_one({"uid": uid}, {"$inc": {"captured": 1}})
            new_otp = True

        # Mark message as seen so we don't alert again
        if not manual: 
            await seen_msgs.update_one({"key": f"{uid}:{mid}"}, {"$set": {"at": time.time()}}, upsert=True)

    await update_user(uid, {"last_check": datetime.datetime.now(BD_TZ).strftime("%I:%M:%S %p")})
    
    # If we found a new OTP, update the user's screen immediately
    if new_otp: await update_live_ui(bot, uid)

async def background_watcher(bot):
    """
    Runs forever in the background, checking all users every 2 seconds.
    """
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Find all users who have an access token
                cursor = users.find({"access": {"$exists": True}, "is_active": True})
                user_list = await cursor.to_list(None)
                
                # Process them all in parallel
                if user_list: 
                    await asyncio.gather(*(process_user(bot, u["uid"], session) for u in user_list), return_exceptions=True)
            except: pass
            
            await asyncio.sleep(2)
