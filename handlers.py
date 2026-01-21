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
async def cmd_start(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    
    # 1. Fetch User Data
    user = await get_user(uid)
    
    # 2. CLEANUP: Delete Old Dashboard (if it exists)
    if user and user.get("main_msg_id"):
        try:
            await bot.delete_message(chat_id=uid, message_id=user["main_msg_id"])
        except:
            pass 

    # 3. LOGIC: Auto-Generate New Alias (Only if logged in)
    if user and user.get("email"):
        try:
            u, d = user["email"].split("@")
            mixed = "".join(c.upper() if random.getrandbits(1) else c.lower() for c in u)
            formatted_status = (
                f"✨ <b>New Mail Generated</b>\n"
                f"⏰ {datetime.datetime.now(BD_TZ).strftime('%I:%M:%S %p')}"
            )
            await update_user(uid, {
                "last_gen": f"{mixed}@{d}", 
                "latest_otp": formatted_status, 
                "last_gen_timestamp": time.time(),
                "is_active": True
            })
        except:
            await update_user(uid, {"is_active": True})
    else:
        await update_user(uid, {"is_active": True}) 
    
    # 4. UI PART 1: Send the Main Menu (The Bottom Buttons)
    # We send a text message with 'reply_markup=get_main_menu()' to open the keyboard.
    await message.answer("<b>Menu</b>", reply_markup=get_main_menu(), parse_mode="HTML")
    
    # 5. UI PART 2: Send the Dashboard (The Inline Buttons)
    text, kb = await get_dashboard_ui(uid)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    
    # 6. Save new Message ID (So we can refresh the Dashboard later)
    await update_user(uid, {"main_msg_id": sent.message_id})

    # 7. Delete the user's "/start" command to keep chat clean
    try: await message.delete()
    except: pass


# --- BUTTON HANDLERS ---

@router.message(F.text == "👤 Account")
async def btn_account(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    
    # 1. Delete User Input (Clean Chat)
    try: await message.delete()
    except: pass

    user = await get_user(uid)

    # 2. Delete Old Dashboard (Clean UI)
    if user and user.get("main_msg_id"):
        try:
            await bot.delete_message(chat_id=uid, message_id=user["main_msg_id"])
        except: pass

    # 3. Check Login (Manually handled here to control message ID)
    if not user or not user.get("email"):
        text, kb = await get_dashboard_ui(uid)
        sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
        await update_user(uid, {"main_msg_id": sent.message_id})
        return

    # 4. Send Account Info
    name = user.get("name", "Unknown")
    email = user.get("email")
    
    report = (
        f"📊 <b>ACCOUNT INFO</b>\n"
        f"────────────────\n"
        f"👤 <b>Name:</b> {name}\n"
        f"📧 <b>Email:</b> <code>{email}</code>\n"
        f"────────────────"
    )
    sent = await message.answer(report, reply_markup=get_account_kb(), parse_mode="HTML")
    
    # 5. Save this as the new Main Message
    await update_user(uid, {"main_msg_id": sent.message_id})

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
@router.message(F.text)
async def handle_manual_code_paste(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    text = message.text.strip()
    
    code = extract_google_code(text)
    if not code: return

    status = await message.answer("🔄 <b>Verifying Manual Code...</b>")
    try:
        flow = get_flow(state=uid)
        flow.redirect_uri = "http://localhost"
        
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
        await status.edit_text(f"❌ <b>Manual Login Failed:</b>\n{str(e)}")

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
        
        # 1. Delete the Account Message
        try: await q.message.delete()
        except: pass
        
        # 2. Send the Main Dashboard
        text, kb = await get_dashboard_ui(uid)
        sent = await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
        
        # 3. Update main_msg_id
        await update_user(uid, {"main_msg_id": sent.message_id})
