from telegram import KeyboardButton, ReplyKeyboardMarkup
from db_setup import ADMIN_IDS  # Or load this from your .env as needed

def main_menu_keyboard(is_admin):
    kb = [
        [KeyboardButton("Участвовать"), KeyboardButton("Расписание")],
        [KeyboardButton("Отменить участие")]
    ]
    if is_admin:
        kb.append([KeyboardButton("Редактировать события")])
        kb.append([KeyboardButton("Отмена")])
    return ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)

async def show_main_menu(update, context):
    is_admin = update.effective_user.id in ADMIN_IDS
    await update.effective_chat.send_message(
        "Меню:",
        reply_markup=main_menu_keyboard(is_admin)
    )

async def start(update, context):
    is_admin = update.effective_user.id in ADMIN_IDS
    await update.message.reply_text(
        "Добро пожаловать! Для просмотра расписания или записи используйте кнопки ниже:",
        reply_markup=main_menu_keyboard(is_admin)
    )