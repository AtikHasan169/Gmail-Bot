import random
import time
import datetime
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

# --- IMPORTS ---
from database import update_user, get_user, delete_user_data
from keyboards import get_main_menu, get_dashboard_ui, get_account_kb
from services import update_live_ui, process_user

router = Router()
# Timezone for Bangladesh (GMT+6)
BD_TZ = datetime.timezone(datetime.timedelta(hours=6))

# --- HELPER FUNCTIONS ---

async def check_login(bot: Bot, uid: str, message: Message = None):
    """
    Checks if user is logged in. 
    If not, sends the Automatic Login UI (Link Button).
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
    """
    Refreshes the dashboard message.
    Deletes the old message and sends a new one to keep the chat clean.
    """
    user = await get_user(uid)
    
    # Delete old message if it exists
    if user and user.get("main_msg_id"):
        try: await bot.delete_message(chat_id=uid, message_id=user["main_msg_id"])
        except: pass
    
    # Send temporary syncing message
    sent = await bot.send_message(uid, "🔄 <b>Syncing...</b>", parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})
    
    # Run a manual process check
    try:
        async with aiohttp.ClientSession() as s: 
            await process_user(bot, uid, s, manual=True)
    except: pass
    finally:
        # Update the message with the final Dashboard UI
        await update_live_ui(bot, uid)

# --- COMMAND HANDLERS ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    # Activate user in DB
    await update_user(uid, {"is_active": True}) 
    
    # Send the Bottom Menu (Account / Refresh)
    await message.answer("<b>System Initialized.</b>", reply_markup=get_main_menu())
    
    # Get the Dashboard UI
    # If logged out -> Returns "Connect Gmail" button (Web Link)
    # If logged in -> Returns the standard Dashboard
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
    
    # Delete the user's "Refresh" text command to keep chat clean
    try: await message.delete()
    except: pass

    user = await get_user(uid)
    
    # Show "Syncing..." status
    if user and user.get("main_msg_id"):
        try:
            await bot.edit_message_text(
                chat_id=uid, 
                message_id=user["main_msg_id"], 
                text="🔄 <b>Syncing...</b>", 
                parse_mode="HTML"
            )
        except: pass

    # Run the check
    try:
        async with aiohttp.ClientSession() as s: 
            await process_user(bot, uid, s, manual=True)
    except: 
        pass
    finally:
        # Restore the dashboard
        await update_live_ui(bot, uid)

# --- CALLBACK QUERY HANDLERS (Inline Buttons) ---

@router.callback_query(F.data.startswith("ui_"))
async def callbacks(q: CallbackQuery, bot: Bot):
    uid = str(q.from_user.id)
    action = q.data
    
    # If user tries to click buttons but is logged out (except logout button)
    if action != "ui_logout":
        user = await get_user(uid)
        if not user or not user.get("email"):
            text, kb = await get_dashboard_ui(uid)
            try: await q.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except: await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
            await q.answer()
            return
    
    if action == "ui_gen":
        # Generate a new "Dot Trick" alias
        await q.answer()
        user = await get_user(uid)
        if user and "email" in user:
            u, d = user["email"].split("@")
            # Randomly capitalize/lowercase letters to create a unique-looking alias
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
        # Clear the dashboard stats
        await update_user(uid, {
            "latest_otp": "<i>Cleared</i>", 
            "last_otp_raw": None, 
            "captured": 0, 
            "last_gen": "None"
        })
        await q.answer("✅ Dashboard Cleared") 
        await update_live_ui(bot, uid)
        
    elif action == "ui_logout":
        # Logout Logic
        await q.answer()
        user = await get_user(uid)
        main_id = user.get("main_msg_id") if user else None
        
        # Completely wipe data from RAM and DB
        await delete_user_data(uid)
        
        # Get the "Login Page" UI
        login_text, login_kb = await get_dashboard_ui(uid)
        
        if main_id:
            try: await bot.edit_message_text(text=login_text, chat_id=uid, message_id=main_id, reply_markup=login_kb, parse_mode="HTML")
            except: pass
        else:
             await bot.send_message(uid, login_text, reply_markup=login_kb, parse_mode="HTML")

        try: await q.message.delete()
        except: pass
        
    elif action == "ui_back":
        # Just close the menu
        await q.answer()
        try: await q.message.delete()
        except: pass
