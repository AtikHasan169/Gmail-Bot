import time
import uuid
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
from database import get_user, db
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
    
    # CASE 1: User NOT logged in
    if not user or not user.get("email"):
        # Generate a unique state ID for this specific login attempt
        state_token = uuid.uuid4().hex
        
        # Save it to DB so 'main.py' knows who this user is when they return from Google
        await db.oauth_states.insert_one({
            "state": state_token,
            "user_id": int(uid_str),
            "created_at": time.time()
        })
        
        # Generate the Official Google Login Link
        flow = get_flow(state=state_token)
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        text = (
            "<b>🔒 AUTHENTICATION REQUIRED</b>\n"
            "────────────────────────\n"
            "Click the button below to connect your Gmail account.\n"
            "You will be redirected to Google and then automatically back here.\n"
            "────────────────────────"
        )
        # The button sends them to your Railway Server
        return text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Connect Gmail", url=auth_url)]])

    # CASE 2: User IS logged in (Show Dashboard)
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
