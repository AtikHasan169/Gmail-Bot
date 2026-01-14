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
    
    # --- 1. LOGIN BUTTON (Auto-Generated via Module) ---
    if not user or not user.get("email"):
        flow = get_flow(state=uid_str)
        auth_url, _ = flow.authorization_url(prompt='consent')

        text = (
            "<b>⚠️ AUTHENTICATION REQUIRED</b>\n"
            "───────────────────────\n"
            "System needs access to read OTPs.\n\n"
            "👇 <b>Tap the button below to Auto-Login.</b>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Connect Google Account", url=auth_url)]
        ])
        return text, kb

    # --- 2. MAIN DASHBOARD ---
    email = user.get("email", "Unknown")
    captured = user.get("captured", 0)
    last_check = user.get("last_check", "--:--:--")
    latest_otp = user.get("latest_otp", "Waiting for data...")
    gen_alias = user.get("last_gen", "None")
    is_active = user.get("is_active", True)
    
    status_str = "🟢 Online" if is_active else "🔴 Paused"
    
    now = time.time()
    otp_fresh = (now - user.get("last_otp_timestamp", 0)) < 30
    alias_fresh = (now - user.get("last_gen_timestamp", 0)) < 30
    
    otp_label = "🔥 <b>NEW CODE RECEIVED</b>" if otp_fresh else "🔐 <b>LATEST CODE</b>"
    alias_label = "✨ <b>NEW ALIAS GENERATED</b>" if alias_fresh else "🎭 <b>CURRENT ALIAS</b>"

    text = (
        f"🛡️ <b>GMAIL COMMANDER</b>\n"
        f"───────────────────────\n"
        f"👤 <b>Account:</b> <code>{email}</code>\n"
        f"📡 <b>Status:</b> {status_str}\n"
        f"🎯 <b>Hits:</b> <code>{captured}</code>   |   ⏳ <b>Sync:</b> <code>{last_check}</code>\n"
        f"───────────────────────\n\n"
        f"{otp_label}\n"
        f"{latest_otp}\n\n"
        f"{alias_label}\n"
        f"<code>{gen_alias}</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Force Scan", callback_data="ui_refresh"),
            InlineKeyboardButton(text="🎲 Gen Mail", callback_data="ui_gen")
        ],
        [
            InlineKeyboardButton(text="🧹 Clear Log", callback_data="ui_clear"),
            InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")
        ]
    ])
    
    return text, kb
