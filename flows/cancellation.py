from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from shared.cancel import cancel_handler
from shared.main_menu import show_main_menu
from shared.notifications import notify_admins
from db.context import db_session
from db_setup import Participation, Event
from utils.formatting import ru_date_string
from datetime import datetime
from sqlalchemy.orm import joinedload

CHOOSING_CANCEL = 100

async def show_cancel_participation_menu(update, context):
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("У вас должен быть установлен username в Telegram для отмены участия.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    today = datetime.today().date()
    with db_session() as session:
        parts = (
            session.query(Participation)
            .options(joinedload(Participation.event), joinedload(Participation.role))
            .join(Event)
            .filter(
                Participation.username == username,
                Event.date >= today
            )
            .order_by(Event.date, Event.slot)
            .all()
        )
    if not parts:
        await update.message.reply_text("У вас нет активных записей для отмены.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    keyboard = []
    for p in parts:
        event = p.event
        role = p.role.name if p.role else "Без роли"
        btn_text = (
            f"{ru_date_string(event.date)}, {event.time} — {role}"
        )
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"cancelpart|{p.id}")])
    keyboard.append([InlineKeyboardButton("❌ Отменить все", callback_data="cancelall")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    await update.message.reply_text(
        "Выберите участие для отмены, либо отмените все одним нажатием:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_CANCEL

async def cancel_participation(update, context):
    if update.callback_query.data == "cancel":
        return await cancel_handler(update, context)
    username = update.effective_user.username
    today = datetime.today().date()
    if update.callback_query.data == "cancelall":
        notify_msgs = []
        with db_session() as session:
            canceled_parts = (
                session.query(Participation)
                .join(Event)
                .filter(
                    Participation.username == username,
                    Event.date >= today
                )
                .all()
            )
            for p in canceled_parts:
                event = p.event
                role = p.role.name if p.role else "Без роли"
                notify_msgs.append(
                    f"🔴 @{username} отменил участие в событии:\n"
                    f"{ru_date_string(event.date)}, {event.time}\n"
                    f"Роль: {role}"
                )
            for p in canceled_parts:
                session.delete(p)
            session.commit()
        # Optionally, notify admins (implement if needed)
        for msg in notify_msgs:
            await notify_admins(context, msg)
        await update.callback_query.edit_message_text("Все ваши участия отменены.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        _, part_id = update.callback_query.data.split("|")
        with db_session() as session:
            part = session.query(Participation).filter_by(id=int(part_id)).first()
            if not part:
                await update.callback_query.answer("Запись не найдена.")
                await show_main_menu(update, context)
                return ConversationHandler.END
            event = part.event
            role = part.role.name if part.role else "Без роли"
            text = (f"🔴 @{username} отменил участие в событии:\n"
                    f"{ru_date_string(event.date)}, {event.time}\n"
                    f"Роль: {role}")
            session.delete(part)
            session.commit()
        # Optionally, notify admins (implement if needed)
        await notify_admins(context, text)
        await update.callback_query.edit_message_text("Ваше участие отменено.")
        await show_main_menu(update, context)
        return ConversationHandler.END

cancel_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Отменить участие$"), show_cancel_participation_menu)],
    states={
        CHOOSING_CANCEL: [
            CallbackQueryHandler(cancel_participation, pattern=r"^(cancelpart\||cancelall$)"),
            CallbackQueryHandler(cancel_handler, pattern="^cancel$")
        ],
    },
    fallbacks=[MessageHandler(filters.Regex("^Отмена$"), cancel_handler)],
)