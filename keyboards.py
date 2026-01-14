import time
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, 
    CopyTextButton
)
from database import get_user
from auth import get_flow

def get_main_menu():
    """Simple Bottom Menu (Control Only)."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="▶ Start"), KeyboardButton(text="⏹ Stop")],
        [KeyboardButton(text="↻ Refresh"), KeyboardButton(text="ℹ Status")]
    ], resize_keyboard=True)

async def get_dashboard_ui(uid_str: str):
    user = await get_user(uid_str)
    
    # --- LOGIN ---
    if not user or not user.get("email"):
        flow = get_flow(state=uid_str)
        auth_url, _ = flow.authorization_url(prompt='consent')
        text = "<b>⚠️ AUTH REQUIRED</b>\n────────────────\nLogin below to start."
        return text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Login Google", url=auth_url)]])

    # --- DASHBOARD DATA ---
    latest_otp_text = user.get("latest_otp", "<i>Waiting...</i>")
    gen_alias = user.get("last_gen", None)
    
    # Extract Raw OTP for the button
    # We stored the raw code in 'last_otp_raw' in services.py (we will add this logic)
    raw_otp = user.get("last_otp_raw", None)
    
    is_active = user.get("is_active", True)
    status = "🟢" if is_active else "🔴"
    
    # --- BUILD INLINE KEYBOARD ---
    kb_rows = []
    
    # Row 1: Copy Buttons (The Feature You Wanted)
    copy_row = []
    if raw_otp:
        copy_row.append(InlineKeyboardButton(
            text=f"📋 OTP: {raw_otp}", 
            copy_text=CopyTextButton(text=raw_otp)
        ))
    if gen_alias:
        copy_row.append(InlineKeyboardButton(
            text="📋 Copy Mail", 
            copy_text=CopyTextButton(text=gen_alias)
        ))
    if copy_row:
        kb_rows.append(copy_row)

    # Row 2: Controls
    kb_rows.append([
        InlineKeyboardButton(text="↻ Scan", callback_data="ui_refresh"),
        InlineKeyboardButton(text="🔄 New Mail", callback_data="ui_gen")
    ])
    
    # Row 3: Account
    kb_rows.append([
        InlineKeyboardButton(text="🧹 Clear", callback_data="ui_clear"),
        InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")
    ])

    text = (
        f"🛡️ <b>GMAIL BOT</b> {status}\n"
        f"────────────────\n\n"
        f"<b>LATEST CODE:</b>\n"
        f"{latest_otp_text}\n\n"
        f"<b>CURRENT MAIL:</b>\n"
        f"<code>{gen_alias if gen_alias else 'None'}</code>\n\n"
        f"────────────────"
    )

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)
