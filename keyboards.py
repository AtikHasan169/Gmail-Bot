import time
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
from database import get_user
from auth import get_flow

def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="▶ Start"), KeyboardButton(text="⏹ Stop")],
        [KeyboardButton(text="↻ Refresh"), KeyboardButton(text="ℹ Status")]
    ], resize_keyboard=True)

async def get_dashboard_ui(uid_str: str):
    user = await get_user(uid_str)
    
    # --- LOGIN UI ---
    if not user or not user.get("email"):
        flow = get_flow(state=uid_str)
        auth_url, _ = flow.authorization_url(prompt='consent')
        text = "<b>⚠️ Login Required</b>"
        return text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Google Login", url=auth_url)]])

    # --- MONITOR UI ---
    latest_otp_text = user.get("latest_otp", "<i>...</i>")
    raw_otp = user.get("last_otp_raw", None)
    gen_alias = user.get("last_gen", None)
    is_active = user.get("is_active", True)
    
    # Simple Status Dot
    status_icon = "🟢" if is_active else "🔴"

    # --- MINIMAL TEXT ---
    text = (
        f"<b>GMAIL MONITOR</b> {status_icon}\n"
        f"────────────────\n"
        f"{latest_otp_text}\n"
        f"────────────────"
    )

    # --- BUTTONS ---
    kb_rows = []
    
    # 1. OTP Button (Only if code exists)
    if raw_otp:
        kb_rows.append([InlineKeyboardButton(text=raw_otp, copy_text=CopyTextButton(text=raw_otp))])
        
    # 2. Email Button (Only if alias exists)
    if gen_alias:
        kb_rows.append([InlineKeyboardButton(text=gen_alias, copy_text=CopyTextButton(text=gen_alias))])

    # 3. Actions
    kb_rows.append([
        InlineKeyboardButton(text="↻ Scan", callback_data="ui_refresh"),
        InlineKeyboardButton(text="🔄 New Mail", callback_data="ui_gen")
    ])
    
    # 4. System
    kb_rows.append([
        InlineKeyboardButton(text="🧹 Clear", callback_data="ui_clear"),
        InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")
    ])

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)
