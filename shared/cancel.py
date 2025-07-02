from telegram.ext import ConversationHandler
from shared.main_menu import show_main_menu

async def cancel_handler(update, context):
    try:
        if hasattr(update, "callback_query") and update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text("Действие отменено.")
        elif hasattr(update, "message") and update.message:
            await update.message.reply_text("Действие отменено.")
    except Exception:
        pass
    await show_main_menu(update, context)
    return ConversationHandler.END