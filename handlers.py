import random
import time
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database import update_user, get_user, users
from keyboards import get_main_menu, get_dashboard_ui
from services import update_live_ui, process_user

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    await message.answer("<b>System Initialized.</b>", reply_markup=get_main_menu())
    
    text, kb = await get_dashboard_ui(uid)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await update_user(uid, {"main_msg_id": sent.message_id})

@router.message(F.text.in_({"▶ Start", "⏹ Stop", "↻ Refresh", "ℹ Status"}))
async def handle_menu_buttons(message: Message, bot: Bot):
    uid = str(message.from_user.id)
    text = message.text

    if text == "▶ Start":
        await update_user(uid, {"is_active": True})
        await message.answer("<i>Monitoring Resumed</i>")
    elif text == "⏹ Stop":
        await update_user(uid, {"is_active": False})
        await message.answer("<i>Monitoring Paused</i>")
    elif text in ["↻ Refresh", "ℹ Status"]:
        await cmd_start(message)
        return

    await update_live_ui(bot, uid)

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
            await update_user(uid, {"last_gen": f"{mixed}@{domain}", "last_gen_timestamp": time.time()})
            await update_live_ui(bot, uid)
            
    elif action == "ui_clear":
        await update_user(uid, {"latest_otp": "Waiting for data...", "captured": 0, "last_gen": "None"})
        await update_live_ui(bot, uid)
        
    elif action == "ui_logout":
        await users.delete_one({"uid": uid})
        await update_live_ui(bot, uid)
