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

    # --- DATA ---
    latest_otp_text = user.get("latest_otp", "<i>No code yet</i>") # Only Service Name + Time
    raw_otp = user.get("last_otp_raw", None)
    gen_alias = user.get("last_gen", None)
    
    is_active = user.get("is_active", True)
    status_icon = "🟢" if is_active else "🔴"
    hits = user.get("captured", 0)

    # --- MINIMAL DASHBOARD TEXT ---
    text = (
        f"{status_icon} <b>Hits:</b> {hits}\n"
        f"────────────────\n"
        f"{latest_otp_text}\n"
        f"────────────────"
    )

    # --- BUTTONS ---
    kb_rows = []
    
    # Row 1: OTP Code (ONLY THE CODE)
    if raw_otp:
        kb_rows.append([InlineKeyboardButton(text=raw_otp, copy_text=CopyTextButton(text=raw_otp))])
        
    # Row 2: Email (ONLY THE EMAIL)
    if gen_alias:
        kb_rows.append([InlineKeyboardButton(text=gen_alias, copy_text=CopyTextButton(text=gen_alias))])

    # Row 3: Actions
    kb_rows.append([
        InlineKeyboardButton(text="↻ Scan", callback_data="ui_refresh"),
        InlineKeyboardButton(text="🔄 New Mail", callback_data="ui_gen")
    ])
    
    # Row 4: Settings
    kb_rows.append([
        InlineKeyboardButton(text="🧹 Clear", callback_data="ui_clear"),
        InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")
    ])

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)
