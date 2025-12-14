import threading
from app.core.logging import setup_logging
from app.bot.app import build_app
from app.admin.dashboard import app as dashboard
import uvicorn

def run_dashboard():
    uvicorn.run(dashboard, host="0.0.0.0", port=8000)

def main():
    setup_logging()
    threading.Thread(target=run_dashboard, daemon=True).start()
    bot = build_app()
    bot.run_polling()

if __name__ == "__main__":
    main()