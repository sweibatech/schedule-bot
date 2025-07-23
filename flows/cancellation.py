from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
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
        callback_data = f"cancelpart|{p.id}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("❌ Отменить все", callback_data="cancelall")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    
    await update.message.reply_text(
        "Выберите участие для отмены, либо отмените все одним нажатием:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_CANCEL

async def cancel_participation(update, context):
    if not update.callback_query:
        return
        
    data = update.callback_query.data
    await update.callback_query.answer()
    
    if data == "cancel":
        await update.callback_query.edit_message_text("Отмена операции.", reply_markup=None)
        await show_main_menu(update, context)
        return ConversationHandler.END
    
    username = update.effective_user.username
    today = datetime.today().date()
    
    if data == "cancelall":
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
        
        for msg in notify_msgs:
            await notify_admins(context, msg)
        await update.callback_query.edit_message_text("Все ваши участия отменены.", reply_markup=None)
        await show_main_menu(update, context)
        return ConversationHandler.END
    elif data.startswith("cancelpart|"):
        _, part_id = data.split("|")
        with db_session() as session:
            part = session.query(Participation).filter_by(id=int(part_id)).first()
            if not part:
                await update.callback_query.answer("Запись не найдена.")
                await update.callback_query.edit_message_text("Запись не найдена.", reply_markup=None)
                await show_main_menu(update, context)
                return ConversationHandler.END
            event = part.event
            role = part.role.name if part.role else "Без роли"
            text = (f"🔴 @{username} отменил участие в событии:\n"
                    f"{ru_date_string(event.date)}, {event.time}\n"
                    f"Роль: {role}")
            session.delete(part)
            session.commit()
        
        await notify_admins(context, text)
        await update.callback_query.edit_message_text("Ваше участие отменено.", reply_markup=None)
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.callback_query.edit_message_text("Неизвестная команда.", reply_markup=None)
        await show_main_menu(update, context)
        return ConversationHandler.END

cancel_conv = ConversationHandler(
    entry_points=[
        CommandHandler("cancel", show_cancel_participation_menu),
        MessageHandler(filters.Regex("^Отменить участие$"), show_cancel_participation_menu)
    ],
    states={
        CHOOSING_CANCEL: [
            CallbackQueryHandler(cancel_participation)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_handler),
        MessageHandler(filters.Regex("^Отмена$"), cancel_handler)
    ],
    per_message=False,
    name="cancel_participation_conv"
)