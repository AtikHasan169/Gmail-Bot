from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Login Gmail", callback_data="login")],
        [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("✉️ Alias Generator", callback_data="alias")],
        [InlineKeyboardButton("🛠 Admin", callback_data="admin")],
    ])