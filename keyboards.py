import time
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
from database import get_user
from auth import get_flow

def get_main_menu():
    # --- CHANGED: Account on left, Refresh on right ---
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Account"), KeyboardButton(text="↻ Refresh")]
    ], resize_keyboard=True)

# --- ADDED: New Keyboard for Account Menu ---
def get_account_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Clear Dashboard", callback_data="ui_clear")],
        [InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")]
    ])

async def get_dashboard_ui(uid_str: str):
    user = await get_user(uid_str)
    
    if not user or not user.get("email"):
        flow = get_flow(state=uid_str)
        auth_url, _ = flow.authorization_url(prompt='consent')
        text = (
            "<b>⚠️ AUTHENTICATION REQUIRED</b>\n"
            "────────────────────────\n"
            "1. Tap <b>Google Login</b> below.\n"
            "2. Select your Google Account.\n"
            "3. Allow the permissions.\n"
            "4. You will see a code on the screen.\n"
            "5. <b>Copy that code</b> and paste it here.\n"
            "────────────────────────"
        )
        return text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Google Login", url=auth_url)]])

    latest_otp_text = user.get("latest_otp", "<i>...</i>")
    raw_otp = user.get("last_otp_raw", None)
    gen_alias = user.get("last_gen", None)
    
    text = (
        f"<b>GMAIL MONITOR</b> 🟢\n"
        f"────────────────\n"
        f"{latest_otp_text}\n"
        f"────────────────"
    )

    kb_rows = []
    
    if raw_otp:
        otp_ts = user.get("last_otp_timestamp", 0)
        gen_ts = user.get("last_gen_timestamp", 0)
        
        if otp_ts < gen_ts:
            label = f"🚨 Last OTP: {raw_otp}"
        else:
            label = f"✨ Code {raw_otp}"
            
        kb_rows.append([InlineKeyboardButton(text=label, copy_text=CopyTextButton(text=raw_otp))])
        
    if gen_alias:
        kb_rows.append([InlineKeyboardButton(text=gen_alias, copy_text=CopyTextButton(text=gen_alias))])

    kb_rows.append([
        InlineKeyboardButton(text="↻ Scan", callback_data="ui_refresh"),
        InlineKeyboardButton(text="🔄 Gen New", callback_data="ui_gen")
    ])
    
    # --- CHANGED: Removed Clear/Logout row from here ---

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)
