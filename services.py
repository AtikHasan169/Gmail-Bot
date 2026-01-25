import time
import re
import asyncio
import datetime
import aiohttp
from base64 import urlsafe_b64decode
from email import message_from_bytes
from config import CLIENT_ID, CLIENT_SECRET
from database import users, seen_msgs, update_user, get_user

# --- CONSTANTS ---
TIMEOUT = aiohttp.ClientTimeout(total=5)
BD_TZ = datetime.timezone(datetime.timedelta(hours=6))

# Tracks active sessions so we only trigger the "Welcome" message once per login
ACTIVE_SESSION_CACHE = {}

async def refresh_google_token(uid, session, refresh_token):
    """Refreshes the Google Access Token if expired."""
    if not refresh_token: return None
    
    data = {
        "client_id": CLIENT_ID, 
        "client_secret": CLIENT_SECRET, 
        "refresh_token": refresh_token, 
        "grant_type": "refresh_token"
    }
    
    try:
        async with session.post("https://oauth2.googleapis.com/token", data=data, timeout=TIMEOUT) as r:
            res = await r.json()
            if "access_token" in res:
                await update_user(uid, {"access": res["access_token"]})
                return res["access_token"]
    except: pass
    return None

async def fetch_body_task(access, mid, session):
    """Fetches a single email body (Runs in Parallel for speed)."""
    headers = {"Authorization": f"Bearer {access}"}
    try:
        async with session.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=raw", headers=headers, timeout=TIMEOUT) as r:
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
            except: return None
    except: return None

async def send_fresh_dashboard(bot, uid, user_data):
    """
    THE FIX: Deletes the old message and sends a BRAND NEW Dashboard.
    This ensures the user sees the menu immediately after login.
    """
    from keyboards import get_dashboard_ui
    text, kb = await get_dashboard_ui(uid, user_data=user_data)
    
    # 1. Try to delete the old "Auth Required" message to clean up chat
    old_msg_id = user_data.get("main_msg_id")
    if old_msg_id:
        try:
            await bot.delete_message(chat_id=uid, message_id=old_msg_id)
        except:
            pass # If message is too old or missing, ignore error

    # 2. SEND NEW MESSAGE
    try:
        sent_msg = await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
        
        # 3. Save the NEW ID so future OTP updates edit THIS message
        await update_user(uid, {"main_msg_id": sent_msg.message_id})
    except Exception as e:
        print(f"Failed to send dashboard: {e}")

async def update_live_ui(bot, uid, fresh_user=None):
    """Standard UI update for OTPs (Edits existing message)."""
    from keyboards import get_dashboard_ui
    text, kb = await get_dashboard_ui(uid, user_data=fresh_user)
    
    if fresh_user:
        msg_id = fresh_user.get("main_msg_id")
    else:
        u = await get_user(uid)
        msg_id = u.get("main_msg_id") if u else None

    if not msg_id: return
    
    try: 
        await bot.edit_message_text(
            chat_id=uid, 
            message_id=msg_id, 
            text=text, 
            reply_markup=kb, 
            parse_mode="HTML"
        )
    except: pass

async def process_user(bot, uid, session, manual=False, user_data=None):
    """Main Logic: Checks user status and emails."""
    # Use passed user_data if available (FRESH), otherwise fetch from DB
    if user_data:
        user = user_data
    else:
        user = await get_user(uid)

    if not user: return
    if not manual and not user.get("is_active", True): return

    access = user.get("access")
    refresh_token = user.get("refresh")
    
    # --- LOGOUT HANDLER ---
    if not access: 
        # If user logs out, remove from cache so we treat them as new next time
        if uid in ACTIVE_SESSION_CACHE:
             del ACTIVE_SESSION_CACHE[uid]
        return

    # --- THE FIX: FRESH START ON LOGIN ---
    # If we detect you are logged in, but we haven't set up the session yet:
    if uid not in ACTIVE_SESSION_CACHE:
        # SEND A FRESH MESSAGE (Simulates /start)
        await send_fresh_dashboard(bot, uid, user_data=user)
        ACTIVE_SESSION_CACHE[uid] = True

    # --- EMAIL CHECKING ---
    headers = {"Authorization": f"Bearer {access}"}
    new_ids = []
    
    try:
        params = {"q": "is:unread newer_than:1d", "maxResults": 1}
        
        async with session.get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params=params, headers=headers, timeout=TIMEOUT) as r:
                if r.status == 401:
                    access = await refresh_google_token(uid, session, refresh_token)
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
            await update_user(uid, {"last_check": datetime.datetime.now(BD_TZ).strftime("%I:%M:%S %p")})
        return

    # Filter out messages we have already processed
    to_fetch = [mid for mid in new_ids if not await seen_msgs.find_one({"key": f"{uid}:{mid}"})]
    if not to_fetch: return

    # --- Fetch all new bodies in parallel ---
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
            await users.update_one({"uid": uid}, {"$inc": {"captured": 1}})
            new_otp = True

        if not manual: 
            await seen_msgs.update_one({"key": f"{uid}:{mid}"}, {"$set": {"at": time.time()}}, upsert=True)

    await update_user(uid, {"last_check": datetime.datetime.now(BD_TZ).strftime("%I:%M:%S %p")})
    
    # If OTP comes, we edit the EXISTING message
    if new_otp: await update_live_ui(bot, uid, fresh_user=user)

async def background_watcher(bot):
    """
    Background Worker. Runs every 0.5 seconds.
    """
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # 1. Fetch FRESH data from MongoDB
                cursor = users.find({"is_active": True})
                user_list = await cursor.to_list(None)
                
                if user_list: 
                    # 2. Pass this FRESH data directly to process_user
                    await asyncio.gather(*(process_user(bot, u["uid"], session, user_data=u) for u in user_list), return_exceptions=True)
            except: pass
            
            await asyncio.sleep(0.5)
