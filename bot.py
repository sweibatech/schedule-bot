import os
import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters
)
from dotenv import load_dotenv

from shared.main_menu import start
from flows.participation import participate_conv, schedule_handler, participate_handler
from flows.cancellation import cancel_conv, show_cancel_participation_menu
from flows.admin import admin_conv, admin

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add conversation handlers first
    app.add_handler(cancel_conv)
    app.add_handler(participate_conv)
    app.add_handler(admin_conv)

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule_handler))
    app.add_handler(CommandHandler("cancel", show_cancel_participation_menu))
    app.add_handler(CommandHandler("participate", participate_handler))
    app.add_handler(CommandHandler("admin", admin))
    
    # Add keyboard button handlers (these will work with your existing main menu)
    app.add_handler(MessageHandler(filters.Regex("^Расписание$"), schedule_handler))
    app.add_handler(MessageHandler(filters.Regex("^Участвовать$"), participate_handler))
    app.add_handler(MessageHandler(filters.Regex("^Отменить участие$"), show_cancel_participation_menu))
    app.add_handler(MessageHandler(filters.Regex("^Редактировать события$"), admin))
    
    app.run_polling()

if __name__ == "__main__":
    main()