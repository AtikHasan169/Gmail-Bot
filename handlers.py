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

async def refresh_and_repost(bot: Bot, uid: str):
    user = await get_user(uid)
    if user and user.get("main_msg_id"):
        try: await bot.delete_message(chat_id=uid, message_id=user["main_msg_id"])
        except: pass
    sent = await bot.send_message(uid, "🔄 <b>Syncing...</b>", parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})
    async with aiohttp.ClientSession() as s: await process_user(bot, uid, s, manual=True)

@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    await message.answer("<b>System Initialized.</b>", reply_markup=get_main_menu())
    text, kb = await get_dashboard_ui(uid)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})

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
            async with s.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers) as p:
                profile = await p.json()
                await update_user(uid, {
                    "email": profile.get("emailAddress"), "access": creds.token, "refresh": creds.refresh_token,
                    "captured": 0, "is_active": True, "history_id": None
                })
        await status.edit_text("✅ <b>Login Successful!</b>")
        await refresh_and_repost(bot, uid)
        try: await message.delete()
        except: pass
    except Exception as e: await status.edit_text(f"❌ <b>Error:</b> {str(e)}")

# --- BUTTONS ---
@router.message(F.text == "↻ Refresh")
async def btn_refresh(message: Message, bot: Bot):
    try: await message.delete()
    except: pass
    await refresh_and_repost(bot, str(message.from_user.id))

@router.message(F.text == "ℹ Status")
async def btn_status(message: Message):
    user = await get_user(str(message.from_user.id))
    if not user: return
    await message.answer(f"📧 <code>{user.get('email')}</code>\nHits: {user.get('captured',0)}", parse_mode="HTML")

@router.message(F.text == "▶ Start")
async def btn_start(message: Message):
    await update_user(str(message.from_user.id), {"is_active": True})
    await message.answer("<i>Resumed</i>")

@router.message(F.text == "⏹ Stop")
async def btn_stop(message: Message):
    await update_user(str(message.from_user.id), {"is_active": False})
    await message.answer("<i>Paused</i>")

# --- CALLBACKS ---
@router.callback_query(F.data.startswith("ui_"))
async def callbacks(q: CallbackQuery, bot: Bot):
    uid = str(q.from_user.id)
    action = q.data
    await q.answer()
    
    if action == "ui_refresh":
        async with aiohttp.ClientSession() as s: await process_user(bot, uid, s, manual=True)
    elif action == "ui_gen":
        user = await get_user(uid)
        if user and "email" in user:
            u, d = user["email"].split("@")
            mixed = "".join(c.upper() if random.getrandbits(1) else c.lower() for c in u)
            await update_user(uid, {"last_gen": f"{mixed}@{d}", "last_gen_timestamp": time.time()})
            await update_live_ui(bot, uid)
    elif action == "ui_clear":
        await update_user(uid, {"latest_otp": "<i>Cleared</i>", "last_otp_raw": None, "captured": 0, "last_gen": "None"})
        await update_live_ui(bot, uid)
    elif action == "ui_logout":
        await users.delete_one({"uid": uid})
        await update_live_ui(bot, uid)
        await bot.send_message(uid, "👋 <b>Logged Out.</b>")
