import random
import time
import datetime
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from database import update_user, get_user, users
from keyboards import get_main_menu, get_dashboard_ui
from services import update_live_ui, process_user
from auth import get_flow

router = Router()
BD_TZ = datetime.timezone(datetime.timedelta(hours=6))

async def check_login(bot: Bot, uid: str, message: Message = None):
    """Checks if user is logged in. If not, sends Login UI and returns False."""
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

@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    await update_user(uid, {"is_active": True}) 
    
    await message.answer("<b>System Initialized.</b>", reply_markup=get_main_menu())
    text, kb = await get_dashboard_ui(uid)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})

@router.message(F.text == "▶ Start")
async def btn_start(message: Message):
    await cmd_start(message)

@router.message(F.text.regexp(r"(?i)code=4/|4/"))
async def handle_code(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    code = message.text.split("code=")[1].split("&")[0].strip() if "code=" in message.text else message.text.strip()
    status = await message.answer("🔄 <b>Verifying...</b>")
    try:
        flow = get_flow(state=uid)
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
        
        await status.edit_text(f"✅ <b>Welcome, {user_name}!</b>")
        await refresh_and_repost(bot, uid)
        try: await message.delete()
        except: pass
    except Exception as e: await status.edit_text(f"❌ <b>Error:</b> {str(e)}")

@router.message(F.text == "ℹ Status")
async def btn_status(message: Message, bot: Bot):
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
    await message.answer(report, parse_mode="HTML")

@router.message(F.text == "↻ Refresh")
async def btn_refresh(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    if not await check_login(bot, uid, message): return
    try: await message.delete()
    except: pass
    await refresh_and_repost(bot, uid)

@router.callback_query(F.data.startswith("ui_"))
async def callbacks(q: CallbackQuery, bot: Bot):
    uid = str(q.from_user.id)
    action = q.data
    await q.answer()
    
    if action != "ui_logout":
        user = await get_user(uid)
        if not user or not user.get("email"):
            text, kb = await get_dashboard_ui(uid)
            try: await q.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except: await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
            return
    
    if action == "ui_refresh":
        async with aiohttp.ClientSession() as s: await process_user(bot, uid, s, manual=True)
        
    elif action == "ui_gen":
        user = await get_user(uid)
        if user and "email" in user:
            u, d = user["email"].split("@")
            mixed = "".join(c.upper() if random.getrandbits(1) else c.lower() for c in u)
            
            # --- CHANGED: AM/PM Format ---
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
        await update_live_ui(bot, uid)
        
    elif action == "ui_logout":
        await users.delete_one({"uid": uid})
        text, kb = await get_dashboard_ui(uid)
        try: 
            await q.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except:
            await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
