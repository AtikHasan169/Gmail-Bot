# app/main.py

from app.bot.app import build_bot

def main():
    bot = build_bot()
    bot.run_polling(close_loop=False)

if __name__ == "__main__":
    main()