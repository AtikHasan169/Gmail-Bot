from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔐 Login Gmail", callback_data="login"),
            ],
            [
                InlineKeyboardButton("📥 Inbox", callback_data="inbox"),
                InlineKeyboardButton("✉️ Generate Alias", callback_data="alias"),
            ],
            [
                InlineKeyboardButton("📊 Status", callback_data="status"),
            ],
        ]
    )