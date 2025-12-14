from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Login", callback_data="login")],
        [InlineKeyboardButton("📧 Case Variants", callback_data="case")]
    ])