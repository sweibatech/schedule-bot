from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
)
from shared.cancel import cancel_handler
from shared.main_menu import show_main_menu
from shared.notifications import notify_admins
from service.schedule_service import ensure_week_events, get_week_schedule, week_dates
from utils.formatting import build_schedule_text, ru_date_string, get_slot_label
from db.context import db_session
from db.queries import get_event_by_id
from db_setup import Participation

CHOOSING_DAY, CHOOSING_EVENT, CHOOSING_ROLE = range(3)

async def schedule_handler(update, context):
    ensure_week_events()
    event_dtos = get_week_schedule()
    text = build_schedule_text(event_dtos, markdown=False)
    await update.message.reply_text(text)
    await show_main_menu(update, context)

async def participate_handler(update, context):
    ensure_week_events()
    event_dtos = get_week_schedule()
    schedule = {e.date: {} for e in event_dtos}
    for event in event_dtos:
        schedule[event.date][event.slot] = event
    keyboard = []
    for date in week_dates():
        events_today = [schedule.get(date.isoformat(), {}).get(slot) for slot in ["morning", "evening"] if schedule.get(date.isoformat(), {}).get(slot)]
        if events_today:
            date_str = ru_date_string(date.isoformat())
            keyboard.append([InlineKeyboardButton(date_str, callback_data=f"chooseday|{date.isoformat()}")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    if len(keyboard) == 1:  # Only cancel button present
        await update.message.reply_text(
            "Нет событий на этой неделе. Пожалуйста, попробуйте позже или обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await show_main_menu(update, context)
        return ConversationHandler.END
    context.user_data["schedule"] = schedule
    await update.message.reply_text(
        "Выберите день для участия:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_DAY

async def choose_day(update, context):
    if update.callback_query.data == "cancel":
        return await cancel_handler(update, context)
    _, day_iso = update.callback_query.data.split("|")
    chosen_date = day_iso
    context.user_data["chosen_date"] = chosen_date
    schedule = context.user_data["schedule"]
    keyboard = []
    for slot in ["morning", "evening"]:
        event = schedule.get(chosen_date, {}).get(slot)
        if event:
            btn_text = get_slot_label(slot, event.time)  # e.g. "Утро (08:00)"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"chooseevent|{event.id}")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    if len(keyboard) == 1:
        await update.callback_query.edit_message_text("Нет событий на этот день.", reply_markup=InlineKeyboardMarkup(keyboard))
        await show_main_menu(update, context)
        return ConversationHandler.END
    await update.callback_query.edit_message_text(
        "Выберите событие для участия:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_EVENT

async def choose_event(update, context):
    if update.callback_query.data == "cancel":
        return await cancel_handler(update, context)
    _, event_id = update.callback_query.data.split("|")
    context.user_data["chosen_event_id"] = int(event_id)
    with db_session() as session:
        event = get_event_by_id(session, int(event_id))
    if not event:
        await update.callback_query.answer("Событие не найдено.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    roles = event.roles
    if not roles:
        await update.callback_query.answer("В этом событии нет ролей.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton(role.name, callback_data=f"chooserole|{role.id}")]
        for role in roles
    ]
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    await update.callback_query.edit_message_text(
        "Выберите вашу роль для этого события:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_ROLE

async def choose_role(update, context):
    if update.callback_query.data == "cancel":
        return await cancel_handler(update, context)
    _, role_id = update.callback_query.data.split("|")
    username = update.effective_user.username
    if not username:
        await update.callback_query.edit_message_text(
            "У вас должен быть установлен username в Telegram для участия."
        )
        await show_main_menu(update, context)
        return ConversationHandler.END
    event_id = context.user_data["chosen_event_id"]
    with db_session() as session:
        already = (
            session.query(Participation)
            .filter_by(event_id=event_id, role_id=int(role_id), username=username)
            .first()
        )
        if already:
            await update.callback_query.edit_message_text(
                "Вы уже записаны на эту роль в этом событии."
            )
            await show_main_menu(update, context)
            return ConversationHandler.END
        participation = Participation(
            username=username, event_id=event_id, role_id=int(role_id)
        )
        session.add(participation)
        session.commit()
        from db.queries import get_event_by_id as get_event_dto_by_id
        event = get_event_dto_by_id(session, event_id)
        role = next((r for r in event.roles if r.id == int(role_id)), None)
    text = (f"🟢 @{username} записался на событие:\n"
            f"{ru_date_string(event.date)}, {event.time}\n"
            f"Роль: {role.name if role else 'Без роли'}")
    await notify_admins(context, text)
    await update.callback_query.edit_message_text(
        "Вы записаны на событие. Спасибо!\n\nТекущее расписание на эту неделю:"
    )
    await show_main_menu(update, context)
    return ConversationHandler.END

participate_conv = ConversationHandler(
    entry_points=[
        CommandHandler("participate", participate_handler),
        MessageHandler(filters.Regex("^Участвовать$"), participate_handler)
    ],
    states={
        CHOOSING_DAY: [
            CallbackQueryHandler(choose_day, pattern=r"^chooseday"),
            CallbackQueryHandler(cancel_handler, pattern="^cancel$")
        ],
        CHOOSING_EVENT: [
            CallbackQueryHandler(choose_event, pattern=r"^chooseevent"),
            CallbackQueryHandler(cancel_handler, pattern="^cancel$")
        ],
        CHOOSING_ROLE: [
            CallbackQueryHandler(choose_role, pattern=r"^chooserole"),
            CallbackQueryHandler(cancel_handler, pattern="^cancel$")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_handler),
        MessageHandler(filters.Regex("^Отмена$"), cancel_handler)
    ],
    per_message=False
)