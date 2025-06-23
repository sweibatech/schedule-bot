import os
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
from db import init_db, SessionLocal, Event, Role, Participation

# Load environment variables from .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = set(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())

WEEKDAY_RU = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресение",
}
MONTH_RU = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "мая",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}
SLOT_RU = {
    "morning": "Утро",
    "evening": "Вечер",
}

DEFAULT_EVENT_TIMES = {
    "Понедельник":    {"morning": "08:00", "evening": "19:30"},
    "Вторник":        {"morning": "08:00", "evening": "19:30"},
    "Среда":          {"morning": "08:00", "evening": "20:30"},
    "Четверг":        {"morning": "08:00", "evening": "19:00"},
    "Пятница":        {"morning": "08:00", "evening": "17:30"},
    "Суббота":        {"morning": "10:00", "evening": "18:00"},
    "Воскресение":    {"morning": "10:00", "evening": "18:00"},
}
DEFAULT_EVENT_NAMES = {"morning": "Утреннее служение", "evening": "Вечернее служение"}
DEFAULT_ROLES = ["Ведущий молитвы", "Хор", "Ритм"]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSING_DAY, CHOOSING_EVENT, CHOOSING_ROLE = range(3)
(
    MANAGE_EVENT, MANAGE_EVENT_SELECT, EDIT_EVENT_CHOICE, SET_EVENT_TIME,
    SET_EVENT_ROLE_ASSIGN_METHOD, ADMIN_ROLE_CHOICE, ADMIN_ROLES_SELECTED
) = range(10, 17)
CHOOSING_CANCEL = 100

def week_dates():
    today = datetime.today()
    start = today - timedelta(days=today.weekday())  # Monday
    return [(start + timedelta(days=i)).date() for i in range(7)]

def get_or_create_role(session, role_name):
    role = session.query(Role).filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name)
        session.add(role)
        session.commit()
    return role

def get_events_for_week(session):
    dates = week_dates()
    events = (
        session.query(Event)
        .filter(Event.date.in_(dates))
        .order_by(Event.date, Event.slot)
        .all()
    )
    schedule = {d: {} for d in dates}
    for event in events:
        schedule[event.date][event.slot] = event
    return schedule

def ensure_week_events(session):
    dates = week_dates()
    existing = session.query(Event).filter(Event.date.in_(dates)).count()
    if existing == 0:
        for date in dates:
            weekday = WEEKDAY_RU[date.weekday()]
            for slot in ["morning", "evening"]:
                event = Event(
                    date=date,
                    slot=slot,
                    name=DEFAULT_EVENT_NAMES[slot],
                    time=DEFAULT_EVENT_TIMES[weekday][slot]
                )
                for role_name in DEFAULT_ROLES:
                    role = get_or_create_role(session, role_name)
                    event.roles.append(role)
                session.add(event)
        session.commit()

def ru_date_string(date):
    weekday = WEEKDAY_RU[date.weekday()]
    day = date.day
    month = MONTH_RU[date.month]
    return f"{weekday}, {day} {month}"

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
        "Меню:",  # Provide a single space to meet telegram API requirement
        reply_markup=main_menu_keyboard(is_admin)
    )

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")

def build_schedule_text(schedule):
    lines = []
    for date in week_dates():
        day_lines = []
        for slot in ["morning", "evening"]:
            event = schedule[date].get(slot)
            if event:
                if event.participations:
                    participations = [
                        (p.username, p.role.name if p.role else "Без роли")
                        for p in event.participations
                    ]
                    part_lines = [
                        f"      - @{username}: {role}" for username, role in participations
                    ]
                    participants_text = "\n".join(part_lines)
                    day_lines.append(
                        f"  - {SLOT_RU[slot]} ({event.time}):\n{participants_text}"
                    )
                else:
                    # show slot even if there are no participants, but no colon or list
                    day_lines.append(
                        f"  - {SLOT_RU[slot]} ({event.time})"
                    )
        if day_lines:
            lines.append(f"*{ru_date_string(date)}*")
            lines.extend(day_lines)
    return "\n".join(lines) if lines else "Нет событий на этой неделе."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in ADMIN_IDS
    await update.message.reply_text(
        "Добро пожаловать! Для просмотра расписания или записи используйте кнопки ниже:",
        reply_markup=main_menu_keyboard(is_admin)
    )

async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    ensure_week_events(session)
    schedule = get_events_for_week(session)
    text = build_schedule_text(schedule)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    session.close()
    await show_main_menu(update, context)

async def send_schedule_this_week(update, context):
    session = SessionLocal()
    schedule = get_events_for_week(session)
    text = build_schedule_text(schedule)
    await update.effective_chat.send_message(text, parse_mode=ParseMode.MARKDOWN)
    session.close()

async def participate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    ensure_week_events(session)
    schedule = get_events_for_week(session)
    keyboard = []
    for date in week_dates():
        events_today = [schedule[date].get(slot) for slot in ["morning", "evening"] if schedule[date].get(slot)]
        if events_today:
            date_str = ru_date_string(date)
            keyboard.append([InlineKeyboardButton(date_str, callback_data=f"chooseday|{date.isoformat()}")])
    if not keyboard:
        await update.message.reply_text(
            "Нет событий на этой неделе. Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
        session.close()
        await show_main_menu(update, context)
        return ConversationHandler.END
    context.user_data["schedule"] = schedule
    await update.message.reply_text(
        "Выберите день для участия:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    session.close()
    # No main menu here (multi-button step)
    return CHOOSING_DAY

async def choose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    _, day_iso = update.callback_query.data.split("|")
    chosen_date = datetime.fromisoformat(day_iso).date()
    context.user_data["chosen_date"] = chosen_date
    schedule = context.user_data["schedule"]
    keyboard = []
    for slot in ["morning", "evening"]:
        event = schedule[chosen_date].get(slot)
        if event:
            btn_text = f"{SLOT_RU[slot]} ({event.time})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"chooseevent|{event.id}")])
    if not keyboard:
        await update.callback_query.edit_message_text("Нет событий на этот день.")
        session.close()
        await show_main_menu(update, context)
        return ConversationHandler.END
    await update.callback_query.edit_message_text(
        "Выберите событие для участия:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    session.close()
    # No main menu here (multi-button step)
    return CHOOSING_EVENT

async def choose_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    _, event_id = update.callback_query.data.split("|")
    context.user_data["chosen_event_id"] = int(event_id)
    event = session.query(Event).filter_by(id=int(event_id)).first()
    if not event:
        await update.callback_query.answer("Событие не найдено.")
        session.close()
        await show_main_menu(update, context)
        return ConversationHandler.END
    roles = event.roles
    if not roles:
        await update.callback_query.answer("В этом событии нет ролей.")
        session.close()
        await show_main_menu(update, context)
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton(role.name, callback_data=f"chooserole|{role.id}")]
        for role in roles
    ]
    await update.callback_query.edit_message_text(
        "Выберите вашу роль для этого события:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    session.close()
    # No main menu here (multi-button step)
    return CHOOSING_ROLE

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, role_id = update.callback_query.data.split("|")
    username = update.effective_user.username
    if not username:
        await update.callback_query.edit_message_text(
            "У вас должен быть установлен username в Telegram для участия."
        )
        await show_main_menu(update, context)
        return ConversationHandler.END
    session = SessionLocal()
    event_id = context.user_data["chosen_event_id"]
    already = (
        session.query(Participation)
        .filter_by(event_id=event_id, role_id=int(role_id), username=username)
        .first()
    )
    if already:
        await update.callback_query.edit_message_text(
            "Вы уже записаны на эту роль в этом событии."
        )
        session.close()
        await show_main_menu(update, context)
        return ConversationHandler.END
    participation = Participation(
        username=username, event_id=event_id, role_id=int(role_id)
    )
    session.add(participation)
    session.commit()
    # Notify admins
    event = session.query(Event).filter_by(id=event_id).first()
    role = session.query(Role).filter_by(id=int(role_id)).first()
    text = (f"🟢 @{username} записался на событие:\n"
            f"{ru_date_string(event.date)}, {SLOT_RU[event.slot]} ({event.time})\n"
            f"Роль: {role.name if role else 'Без роли'}")
    await notify_admins(context, text)
    session.close()
    await update.callback_query.edit_message_text(
        "Вы записаны на событие. Спасибо!\n\nТекущее расписание на эту неделю:"
    )
    await send_schedule_this_week(update, context)
    await show_main_menu(update, context)
    return ConversationHandler.END

async def show_cancel_participation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("У вас должен быть установлен username в Telegram для отмены участия.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    session = SessionLocal()
    parts = (
        session.query(Participation)
        .join(Event)
        .filter(Participation.username == username)
        .order_by(Event.date, Event.slot)
        .all()
    )
    if not parts:
        await update.message.reply_text("У вас нет активных записей для отмены.")
        session.close()
        await show_main_menu(update, context)
        return ConversationHandler.END
    keyboard = []
    for p in parts:
        event = p.event
        role = p.role.name if p.role else "Без роли"
        btn_text = (
            f"{ru_date_string(event.date)}, {SLOT_RU[event.slot]} ({event.time}) — {role}"
        )
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"cancelpart|{p.id}")])
    keyboard.append([InlineKeyboardButton("❌ Отменить все", callback_data="cancelall")])
    await update.message.reply_text(
        "Выберите участие для отмены, либо отмените все одним нажатием:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    session.close()
    # No main menu here (multi-button step)
    return CHOOSING_CANCEL

async def cancel_participation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "cancelall":
        username = update.effective_user.username
        session = SessionLocal()
        canceled_parts = (
            session.query(Participation)
            .join(Event)
            .filter(Participation.username == username)
            .all()
        )
        notify_msgs = []
        for p in canceled_parts:
            event = p.event
            role = p.role.name if p.role else "Без роли"
            notify_msgs.append(
                f"🔴 @{username} отменил участие в событии:\n"
                f"{ru_date_string(event.date)}, {SLOT_RU[event.slot]} ({event.time})\n"
                f"Роль: {role}"
            )
        session.query(Participation).filter_by(username=username).delete()
        session.commit()
        session.close()
        for msg in notify_msgs:
            await notify_admins(context, msg)
        await update.callback_query.edit_message_text("Все ваши участия отменены.\n\nТекущее расписание на эту неделю:")
        await send_schedule_this_week(update, context)
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        _, part_id = update.callback_query.data.split("|")
        session = SessionLocal()
        part = session.query(Participation).filter_by(id=int(part_id)).first()
        if not part:
            await update.callback_query.answer("Запись не найдена.")
            session.close()
            await show_main_menu(update, context)
            return ConversationHandler.END
        # Notify admins
        event = part.event
        role = part.role.name if part.role else "Без роли"
        username = part.username
        text = (f"🔴 @{username} отменил участие в событии:\n"
                f"{ru_date_string(event.date)}, {SLOT_RU[event.slot]} ({event.time})\n"
                f"Роль: {role}")
        session.delete(part)
        session.commit()
        session.close()
        await notify_admins(context, text)
        await update.callback_query.edit_message_text("Ваше участие отменено.\n\nТекущее расписание на эту неделю:")
        await send_schedule_this_week(update, context)
        await show_main_menu(update, context)
        return ConversationHandler.END

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Вы не администратор.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    # Show event select menu for manage
    session = SessionLocal()
    ensure_week_events(session)
    schedule = get_events_for_week(session)
    keyboard = []
    for date in week_dates():
        for slot in ["morning", "evening"]:
            event = schedule[date].get(slot)
            if event:
                btn_text = f"{ru_date_string(date)}, {SLOT_RU[slot]} ({event.time})"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"manageevent|{event.id}")])
    await update.message.reply_text(
        "Выберите событие для изменения времени:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    session.close()
    await show_main_menu(update, context)
    return MANAGE_EVENT_SELECT

async def admin_manage_event_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Select event for edit, offer only time change
    _, event_id = update.callback_query.data.split("|")
    context.user_data["admin_event_id"] = int(event_id)
    keyboard = [
        [InlineKeyboardButton("Изменить время", callback_data="edittime")],
        [InlineKeyboardButton("Отмена", callback_data="canceladmin")]
    ]
    await update.callback_query.edit_message_text(
        "Что вы хотите изменить?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # No main menu here (multi-button step)
    return EDIT_EVENT_CHOICE

async def admin_edit_event_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "edittime":
        await update.callback_query.edit_message_text("Введите новое время события (HH:MM):")
        # No main menu here (multi-button step)
        return SET_EVENT_TIME
    else:
        await update.callback_query.edit_message_text("Редактирование отменено.")
        await show_main_menu(update, context)
        return ConversationHandler.END

async def admin_set_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_time = update.message.text.strip()
    event_id = context.user_data.get("admin_event_id")
    session = SessionLocal()
    event = session.query(Event).filter_by(id=event_id).first()
    if event:
        event.time = new_time
        session.commit()
        await update.message.reply_text("Время события успешно изменено.")
    else:
        await update.message.reply_text("Событие не найдено.")
    session.close()
    await show_main_menu(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    await show_main_menu(update, context)
    return ConversationHandler.END

def user_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Участвовать":
        return participate_handler(update, context)
    elif text == "Расписание":
        return schedule_handler(update, context)
    elif text == "Отменить участие":
        return show_cancel_participation_menu(update, context)
    else:
        return None

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    participate_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Участвовать$"), participate_handler)
        ],
        states={
            CHOOSING_DAY: [CallbackQueryHandler(choose_day, pattern=r"^chooseday")],
            CHOOSING_EVENT: [CallbackQueryHandler(choose_event, pattern=r"^chooseevent")],
            CHOOSING_ROLE: [CallbackQueryHandler(choose_role, pattern=r"^chooserole")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(participate_conv)

    cancel_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Отменить участие$"), show_cancel_participation_menu)],
        states={
            CHOOSING_CANCEL: [CallbackQueryHandler(cancel_participation, pattern=r"^(cancelpart\||cancelall$)")],
        },
        fallbacks=[],
    )
    app.add_handler(cancel_conv)

    app.add_handler(MessageHandler(filters.Regex("^Расписание$"), schedule_handler))

    admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Редактировать события$"), admin)],
        states={
            MANAGE_EVENT_SELECT: [
                CallbackQueryHandler(admin_manage_event_select, pattern=r"^manageevent\|")
            ],
            EDIT_EVENT_CHOICE: [
                CallbackQueryHandler(admin_edit_event_choice, pattern=r"^(edittime|canceladmin)$")
            ],
            SET_EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_event_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(admin_conv)
    app.add_handler(MessageHandler(
        filters.Regex("^(Участвовать|Расписание|Отменить участие)$"),
        user_menu_handler
    ))

    app.run_polling()

if __name__ == "__main__":
    main()