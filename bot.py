import os
import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters
)
from dotenv import load_dotenv

from shared.main_menu import start
from flows.participation import participate_conv, schedule_handler
from flows.cancellation import cancel_conv
from flows.admin import admin_conv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Расписание$"), schedule_handler))
    app.add_handler(participate_conv)
    app.add_handler(cancel_conv)
    app.add_handler(admin_conv)
    app.run_polling()

if __name__ == "__main__":
    main()