import time
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database import get_user
from auth import get_flow

def get_main_menu():
    kb = [
        [KeyboardButton(text="▶ Start"), KeyboardButton(text="⏹ Stop")],
        [KeyboardButton(text="↻ Refresh"), KeyboardButton(text="ℹ Status")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def get_dashboard_ui(uid_str: str):
    user = await get_user(uid_str)
    
    # --- 1. LOGIN BUTTON ---
    if not user or not user.get("email"):
        flow = get_flow(state=uid_str)
        auth_url, _ = flow.authorization_url(prompt='consent')
        text = "<b>⚠️ SYSTEM LOCKED</b>\nAuthorization required to access inbox."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Login with Google", url=auth_url)]
        ])
        return text, kb

    # --- 2. CLEAN DASHBOARD ---
    latest_otp = user.get("latest_otp", "<i>Waiting for new code...</i>")
    gen_alias = user.get("last_gen", "<i>No alias active</i>")
    is_active = user.get("is_active", True)
    
    state_icon = "🟢" if is_active else "🔴"
    
    # Badges
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
        f"💡 <i>Tap code above to copy</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="↻ Scan", callback_data="ui_refresh"),
            InlineKeyboardButton(text="🎲 New Alias", callback_data="ui_gen")
        ],
        [
            InlineKeyboardButton(text="🧹 Clear", callback_data="ui_clear"),
            InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")
        ]
    ])
    
    return text, kb
