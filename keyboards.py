import time
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
from database import get_user
from auth import get_flow

def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Account"), KeyboardButton(text="↻ Refresh")]
    ], resize_keyboard=True)

def get_account_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Clear Dashboard", callback_data="ui_clear")],
        [InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ui_back")]
    ])

async def get_dashboard_ui(uid_str: str):
    user = await get_user(uid_str)
    
    if not user or not user.get("email"):
        flow = get_flow(state=uid_str)
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        # --- UPDATED INSTRUCTIONS FOR LOCALHOST ---
        text = (
            "<b>⚠️ AUTHENTICATION REQUIRED</b>\n"
            "────────────────────────\n"
            "1. Tap <b>Google Login</b> below.\n"
            "2. Authorize the app (Click <b>Advanced > Go to...</b> if warned).\n"
            "3. You will see a page saying <b>'This site can't be reached'</b>.\n"
            "4. <b>THIS IS NORMAL.</b>\n"
            "5. Copy the <b>ENTIRE LINK</b> from your browser's address bar.\n"
            "6. Paste that link here.\n"
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
            label = f"🚨 Last: {raw_otp}"
        else:
            label = f"✨ New: {raw_otp}"
            
        kb_rows.append([InlineKeyboardButton(text=label, copy_text=CopyTextButton(text=raw_otp))])
        
    if gen_alias:
        kb_rows.append([InlineKeyboardButton(text=gen_alias, copy_text=CopyTextButton(text=gen_alias))])

    kb_rows.append([
        InlineKeyboardButton(text="🔄 Gen New", callback_data="ui_gen")
    ])

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)
