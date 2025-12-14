from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔐 Connect Gmail", callback_data="login")],
            [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        ]
    )