from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from shared.cancel import cancel_handler
from shared.main_menu import show_main_menu
from service.schedule_service import ensure_week_events, get_week_schedule, week_dates
from utils.formatting import ru_date_string
from db.context import db_session
from db_setup import Event

from datetime import datetime

MANAGE_EVENT_SELECT, EDIT_EVENT_CHOICE, SET_EVENT_TIME = range(10, 13)

async def admin(update, context):
    ensure_week_events()
    event_dtos = get_week_schedule()
    keyboard = []
    for date in week_dates():
        for slot in ["morning", "evening"]:
            event = next(
                (
                    e
                    for e in event_dtos
                    if datetime.fromisoformat(e.date).date() == date and e.slot == slot
                ),
                None,
            )
            if event:
                btn_text = f"{ru_date_string(event.date)}, {slot.capitalize()} ({event.time})"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"manageevent|{event.id}")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    await update.message.reply_text(
        "Выберите событие для изменения времени:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    await show_main_menu(update, context)
    return MANAGE_EVENT_SELECT

async def admin_manage_event_select(update, context):
    if update.callback_query.data == "cancel":
        return await cancel_handler(update, context)
    _, event_id = update.callback_query.data.split("|")
    context.user_data["admin_event_id"] = int(event_id)
    keyboard = [
        [InlineKeyboardButton("Изменить время", callback_data="edittime")],
        [InlineKeyboardButton("Отмена", callback_data="cancel")]
    ]
    await update.callback_query.edit_message_text(
        "Что вы хотите изменить?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_EVENT_CHOICE

async def admin_edit_event_choice(update, context):
    data = update.callback_query.data
    if data == "edittime":
        await update.callback_query.edit_message_text("Введите новое время события (HH:MM):")
        return SET_EVENT_TIME
    else:
        await update.callback_query.edit_message_text("Редактирование отменено.")
        await show_main_menu(update, context)
        return ConversationHandler.END

async def admin_set_event_time(update, context):
    new_time = update.message.text.strip()
    event_id = context.user_data.get("admin_event_id")
    with db_session() as session:
        event = session.query(Event).filter_by(id=event_id).first()
        if event:
            event.time = new_time
            session.commit()
            await update.message.reply_text("Время события успешно изменено.")
        else:
            await update.message.reply_text("Событие не найдено.")
    await show_main_menu(update, context)
    return ConversationHandler.END

admin_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Редактировать события$"), admin)],
    states={
        MANAGE_EVENT_SELECT: [
            CallbackQueryHandler(admin_manage_event_select, pattern=r"^manageevent\|"),
            CallbackQueryHandler(cancel_handler, pattern="^cancel$")
        ],
        EDIT_EVENT_CHOICE: [
            CallbackQueryHandler(admin_edit_event_choice, pattern=r"^(edittime|cancel)$")
        ],
        SET_EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_event_time)],
    },
    fallbacks=[MessageHandler(filters.Regex("^Отмена$"), cancel_handler)],
)