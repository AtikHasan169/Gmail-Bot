import time
import uuid
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
from database import get_user, db
from auth import get_flow

# Setup logging
logger = logging.getLogger(__name__)

def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Account"), KeyboardButton(text="↻ Refresh")]
    ], resize_keyboard=True)

def get_account_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Logout", callback_data="ui_logout")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ui_back")]
    ])


async def get_dashboard_ui(uid_str: str):
    user = await get_user(uid_str)
    
    # CASE 1: User NOT logged in (Generate the Login Link)
    if not user or not user.get("email"):
        # 1. Generate a unique "Secret ID" (State)
        state_token = uuid.uuid4().hex
        
        # 2. SAVE to Database
        try:
            await db.oauth_states.insert_one({
                "state": state_token,
                "user_id": int(uid_str),
                "created_at": time.time()
            })
            print(f"✅ DEBUG: Saved State {state_token} for User {uid_str}") 
        except Exception as e:
            print(f"❌ CRITICAL ERROR: Could not save state to DB: {e}")
        
        # 3. Generate Link (FORCE STATE)
        flow = get_flow(state=state_token)
        
        # --- THE FIX IS HERE ---
        # We explicitly pass 'state=state_token' to ensure Google uses OUR id, not a random one.
        auth_url, _ = flow.authorization_url(prompt='consent', state=state_token)
        
        text = (
            "<b>🔒 AUTHENTICATION REQUIRED</b>\n"
            "────────────────────────\n"
            "Click the button below to connect your Gmail account.\n"
            "You will be redirected to Google and then automatically back here.\n"
            "────────────────────────"
        )
        return text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Connect Gmail", url=auth_url)]])

    # CASE 2: User IS logged in (Show Dashboard)
    latest_otp_text = user.get("latest_otp", "<i>...</i>")
    raw_otp = user.get("last_otp_raw", None)
    gen_alias = user.get("last_gen", None)
    
    text = (
        f"<b>Zenox Mail</b> 🟢\n"
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
