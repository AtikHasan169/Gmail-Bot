import time
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, 
    CopyTextButton
)
from database import get_user
from auth import get_flow

def get_main_menu(copy_type=None, value=None):
    row1 = [KeyboardButton(text="▶ Start"), KeyboardButton(text="⏹ Stop")]
    row2 = [KeyboardButton(text="↻ Refresh"), KeyboardButton(text="ℹ Status")]
    
    rows = [row1, row2]
    
    # --- DYNAMIC COPY BUTTON ---
    if copy_type and value:
        if copy_type == "otp":
            text = f"📋 Copy OTP: {value}"
        elif copy_type == "mail":
            text = f"📋 Copy Mail"
        
        rows.append([
            KeyboardButton(
                text=text, 
                copy_text=CopyTextButton(text=value)
            )
        ])
    
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

async def get_dashboard_ui(uid_str: str):
    user = await get_user(uid_str)
    
    # --- LOGIN INSTRUCTIONS ---
    if not user or not user.get("email"):
        flow = get_flow(state=uid_str)
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        text = (
            "<b>⚠️ AUTHENTICATION REQUIRED</b>\n"
            "───────────────────────\n"
            "1. Click the button below.\n"
            "2. Authorize Google.\n"
            "3. <b>Copy the code</b> shown on the screen.\n"
            "4. <b>Paste the code</b> here in the chat.\n"
            "───────────────────────"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Get Login Code", url=auth_url)]
        ])
        return text, kb

    # --- DASHBOARD ---
    latest_otp = user.get("latest_otp", "<i>Waiting for new code...</i>")
    gen_alias = user.get("last_gen", "<i>No alias active</i>")
    is_active = user.get("is_active", True)
    
    state_icon = "🟢" if is_active else "🔴"
    
    now = time.time()
    otp_fresh = (now - user.get("last_otp_timestamp", 0)) < 30
    alias_fresh = (now - user.get("last_gen_timestamp", 0)) < 30
    
    otp_header = "🔥 <b>NEW CODE</b>" if otp_fresh else "📨 <b>LATEST MESSAGE</b>"
    alias_header = "✨ <b>NEW ALIAS</b>" if alias_fresh else "👤 <b>YOUR ALIAS</b>"

    text = (
        f"🛡️ <b>LIVE MONITOR</b> {state_icon}\n"
        f"────────────────\n\n"
        f"{otp_header}\n"
        f"{latest_otp}\n\n"
        f"{alias_header}\n"
        f"<code>{gen_alias}</code>\n\n"
        f"────────────────\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Force Scan", callback_data="ui_refresh"),
            # --- UPDATED BUTTON HERE ---
            InlineKeyboardButton(text="🔄 Get New", callback_data="ui_gen")
        ],
        [
            InlineKeyboardButton(text="🧹 Clear", callback_data="ui_clear"),
            InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")
        ]
    ])
    
    return text, kb
