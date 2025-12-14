from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Login", callback_data="login")],
        [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("📧 Aliases", callback_data="alias")]
    ])