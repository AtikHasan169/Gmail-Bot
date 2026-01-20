import random
import time
import datetime
import aiohttp
import re
from urllib.parse import unquote
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

# --- IMPORTS ---
from database import update_user, get_user, delete_user_data
from keyboards import get_main_menu, get_dashboard_ui, get_account_kb
from services import update_live_ui, process_user
from auth import get_flow

router = Router()
BD_TZ = datetime.timezone(datetime.timedelta(hours=6))

# --- HELPER: Code Hunter (For Manual Fallback) ---
def extract_google_code(text):
    """
    Hunts for the Google Auth Code pattern (starting with 4/)
    anywhere in the text, ignoring surrounding URL junk.
    """
    if not text: return None
    clean_text = unquote(text) # Fix %2F to /
    match = re.search(r"(4/[a-zA-Z0-9_-]+)", clean_text)
    if match:
        return match.group(1)
    return None

# --- HELPER: UI Checks ---
async def check_login(bot: Bot, uid: str, message: Message = None):
    """
    Checks if user is logged in. 
    If not, sends the Automatic Login UI.
    """
    user = await get_user(uid)
    if not user or not user.get("email"):
        text, kb = await get_dashboard_ui(uid)
        if message:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
        return False
    return True

async def refresh_and_repost(bot: Bot, uid: str):
    """Refreshes the dashboard message."""
    user = await get_user(uid)
    
    if user and user.get("main_msg_id"):
        try: await bot.delete_message(chat_id=uid, message_id=user["main_msg_id"])
        except: pass
    
    sent = await bot.send_message(uid, "🔄 <b>Syncing...</b>", parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})
    
    try:
        async with aiohttp.ClientSession() as s: 
            await process_user(bot, uid, s, manual=True)
    except: pass
    finally:
        await update_live_ui(bot, uid)

# --- COMMAND HANDLERS ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    await update_user(uid, {"is_active": True}) 
    
    await message.answer("<b>System Initialized.</b>", reply_markup=get_main_menu())
    
    # Returns the Web Login button
    text, kb = await get_dashboard_ui(uid)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})

# --- BUTTON HANDLERS ---

@router.message(F.text == "👤 Account")
async def btn_account(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    if not await check_login(bot, uid, message): return

    user = await get_user(uid)
    name = user.get("name", "Unknown")
    email = user.get("email")
    hits = user.get("captured", 0)
    
    report = (
        f"📊 <b>ACCOUNT STATS</b>\n"
        f"────────────────\n"
        f"👤 <b>Name:</b> {name}\n"
        f"📧 <b>Email:</b> <code>{email}</code>\n"
        f"🎯 <b>Hits:</b> {hits}\n"
        f"────────────────"
    )
    await message.answer(report, reply_markup=get_account_kb(), parse_mode="HTML")

@router.message(F.text == "↻ Refresh")
async def btn_refresh(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    if not await check_login(bot, uid, message): return
    
    try: await message.delete()
    except: pass

    user = await get_user(uid)
    
    if user and user.get("main_msg_id"):
        try:
            await bot.edit_message_text(
                chat_id=uid, 
                message_id=user["main_msg_id"], 
                text="🔄 <b>Syncing...</b>", 
                parse_mode="HTML"
            )
        except: pass

    try:
        async with aiohttp.ClientSession() as s: 
            await process_user(bot, uid, s, manual=True)
    except: 
        pass
    finally:
        await update_live_ui(bot, uid)

# --- MANUAL FALLBACK HANDLER (The Copy-Paste Logic) ---
# This runs if the user pastes a code manually instead of using the web link
@router.message(F.text)
async def handle_manual_code_paste(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    text = message.text.strip()
    
    # 1. Hunt for the code
    code = extract_google_code(text)
    
    # 2. If no code found, ignore it (it's just regular chat)
    if not code:
        return

    # 3. Code found -> Manual Login Logic
    status = await message.answer("🔄 <b>Verifying Manual Code...</b>")
    try:
        # We retrieve the flow but we MUST force localhost for manual copy-paste
        flow = get_flow(state=uid)
        flow.redirect_uri = "http://localhost"  # Override Railway URL for manual mode
        
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        async with aiohttp.ClientSession() as s:
            headers = {"Authorization": f"Bearer {creds.token}"}
            async with s.get("https://www.googleapis.com/oauth2/v1/userinfo?alt=json", headers=headers) as r:
                profile = await r.json()
                user_name = profile.get("name", "User")
                
                await update_user(uid, {
                    "email": profile.get("email"), 
                    "name": user_name,
                    "access": creds.token, 
                    "refresh": creds.refresh_token,
                    "captured": 0, 
                    "is_active": True, 
                    "history_id": None
                })
        
        await status.edit_text(f"✅ <b>Manual Login Success!</b>\nWelcome, {user_name}!")
        await refresh_and_repost(bot, uid)
        try: await message.delete()
        except: pass
        
    except Exception as e: 
        await status.edit_text(f"❌ <b>Manual Login Failed:</b>\n{str(e)}\n\n(Ensure you used the 'localhost' link if pasting manually)")

# --- CALLBACK QUERY HANDLERS ---

@router.callback_query(F.data.startswith("ui_"))
async def callbacks(q: CallbackQuery, bot: Bot):
    uid = str(q.from_user.id)
    action = q.data
    
    if action != "ui_logout":
        user = await get_user(uid)
        if not user or not user.get("email"):
            text, kb = await get_dashboard_ui(uid)
            try: await q.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except: await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
            await q.answer()
            return
    
    if action == "ui_gen":
        await q.answer()
        user = await get_user(uid)
        if user and "email" in user:
            u, d = user["email"].split("@")
            mixed = "".join(c.upper() if random.getrandbits(1) else c.lower() for c in u)
            
            formatted_status = (
                f"✨ <b>New Mail Generated</b>\n"
                f"⏰ {datetime.datetime.now(BD_TZ).strftime('%I:%M:%S %p')}"
            )
            
            await update_user(uid, {
                "last_gen": f"{mixed}@{d}", 
                "latest_otp": formatted_status, 
                "last_gen_timestamp": time.time()
            })
            await update_live_ui(bot, uid)
            
    elif action == "ui_clear":
        await update_user(uid, {"latest_otp": "<i>Cleared</i>", "last_otp_raw": None, "captured": 0, "last_gen": "None"})
        await q.answer("✅ Dashboard Cleared") 
        await update_live_ui(bot, uid)
        
    elif action == "ui_logout":
        await q.answer()
        user = await get_user(uid)
        main_id = user.get("main_msg_id") if user else None
        
        await delete_user_data(uid)
        
        login_text, login_kb = await get_dashboard_ui(uid)
        if main_id:
            try: await bot.edit_message_text(text=login_text, chat_id=uid, message_id=main_id, reply_markup=login_kb, parse_mode="HTML")
            except: pass
        else:
             await bot.send_message(uid, login_text, reply_markup=login_kb, parse_mode="HTML")

        try: await q.message.delete()
        except: pass
        
    elif action == "ui_back":
        await q.answer()
        try: await q.message.delete()
        except: pass
