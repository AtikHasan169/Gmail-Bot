import asyncio
from app.bot.app import build_bot

def main():
    bot_app = build_bot()
    bot_app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()