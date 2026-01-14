import random
import time
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database import update_user, get_user, users
from keyboards import get_main_menu, get_dashboard_ui
from services import update_live_ui, process_user
from auth import get_flow

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    await message.answer("<b>System Initialized.</b>", reply_markup=get_main_menu())
    
    text, kb = await get_dashboard_ui(uid)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})

# --- GOOGLE AUTH HANDLER ---
@router.message(F.text.startswith("4/"))
async def handle_google_code(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    code = message.text.strip()
    status_msg = await message.answer(f"🔄 <b>Verifying Code...</b>")

    try:
        flow = get_flow(state=uid)
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        async with aiohttp.ClientSession() as s:
            headers = {"Authorization": f"Bearer {creds.token}"}
            async with s.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers) as p:
                profile = await p.json()
                
                await update_user(uid, {
                    "email": profile.get("emailAddress"),
                    "access": creds.token,
                    "refresh": creds.refresh_token,
                    "captured": 0,
                    "is_active": True,
                    "history_id": None
                })
        
        await status_msg.edit_text(f"✅ <b>Login Successful!</b>")
        await update_live_ui(bot, uid)
        try: await message.delete()
        except: pass

    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Login Failed:</b> {str(e)}")

# --- STATUS COMMAND ---
@router.message(F.text == "ℹ Status")
async def handle_status(message: Message):
    uid = str(message.from_user.id)
    user = await get_user(uid)
    
    if not user:
        await message.answer("❌ No account found.")
        return

    email = user.get("email", "Disconnected")
    hits = user.get("captured", 0)
    last_check = user.get("last_check", "Never")
    
    report = (
        f"📊 <b>ACCOUNT STATUS</b>\n"
        f"────────────────\n"
        f"📧 <b>Email:</b> <code>{email}</code>\n"
        f"🎯 <b>Total Hits:</b> <code>{hits}</code>\n"
        f"⏳ <b>Last Sync:</b> {last_check}\n"
        f"────────────────"
    )
    await message.answer(report, parse_mode="HTML")

# --- CONTROL BUTTONS ---
@router.message(F.text == "↻ Refresh")
async def handle_refresh(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    async with aiohttp.ClientSession() as s: 
        await process_user(bot, uid, s, manual=True)
    temp = await message.answer("🔄 Scanning...")
    time.sleep(1)
    await temp.delete()

@router.message(F.text == "▶ Start")
async def handle_start(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    await update_user(uid, {"is_active": True})
    await message.answer("<i>Monitor Resumed</i>")
    await update_live_ui(bot, uid)

@router.message(F.text == "⏹ Stop")
async def handle_stop(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    await update_user(uid, {"is_active": False})
    await message.answer("<i>Monitor Paused</i>")
    await update_live_ui(bot, uid)

# --- CALLBACKS (Including Gen Mail Copy) ---
@router.callback_query(F.data.startswith("ui_"))
async def handle_callbacks(callback: CallbackQuery, bot: Bot):
    uid = str(callback.from_user.id)
    action = callback.data
    await callback.answer("Updating...")
    
    if action == "ui_refresh":
        async with aiohttp.ClientSession() as s: await process_user(bot, uid, s, manual=True)
            
    elif action == "ui_gen":
        user = await get_user(uid)
        if user and "email" in user:
            user_part, domain = user["email"].split("@")
            mixed = "".join(c.upper() if random.getrandbits(1) else c.lower() for c in user_part)
            new_alias = f"{mixed}@{domain}"
            
            await update_user(uid, {
                "last_gen": new_alias, 
                "last_gen_timestamp": time.time()
            })
            
            # Update Dashboard
            await update_live_ui(bot, uid)
            
            # --- NEW: SEND COPY BUTTON FOR MAIL ---
            kb = get_main_menu(copy_type="mail", value=new_alias)
            await bot.send_message(
                uid, 
                f"📧 <b>Alias Generated:</b> <code>{new_alias}</code>", 
                reply_markup=kb,
                parse_mode="HTML"
            )
            
    elif action == "ui_clear":
        await update_user(uid, {"latest_otp": "<i>Log Cleared</i>", "captured": 0, "last_gen": "None"})
        await update_live_ui(bot, uid)
        
    elif action == "ui_logout":
        await users.delete_one({"uid": uid})
        await update_live_ui(bot, uid)
