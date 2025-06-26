from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ConversationHandler,
    ContextTypes,
)

from config.logger import logger
from config.settings import ADMIN_IDS, WEEKDAY_RU, DEFAULT_EVENT_NAMES, DEFAULT_EVENT_TIMES, DEFAULT_ROLES, SLOT_RU, \
    CHOOSING_DAY, CHOOSING_EVENT, CHOOSING_ROLE, CHOOSING_CANCEL, MANAGE_EVENT_SELECT, EDIT_EVENT_CHOICE, SET_EVENT_TIME
from db.db_client import db_connect
from db.db_structure import Role, Event, Participation
from utils.datetime_utils import week_dates, ru_date_string


def get_role(db_session, role_name):
    return db_session.query(Role).filter_by(name=role_name).first()


def get_events_for_week(db_session):
    """
    db_session передается, поскольку в sqlalchemy orm используется ленивая загрузка,
    т.е. часть полей инициализятся только в момент обращения и если это происходит в
    рамках другой сессии - возникает ошибка
    """
    dates = week_dates()
    events = (
        db_session.query(Event)
            .filter(Event.date.in_(dates))
            .order_by(Event.date, Event.slot)
            .all()
    )
    schedule = {d: {} for d in dates}
    for event in events:
        schedule[event.date][event.slot] = event
    return schedule


def ensure_week_events():
    dates = week_dates()
    with db_connect() as db_session:
        existing = db_session.query(Event).filter(Event.date.in_(dates)).count()
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
                        role = get_role(db_session, role_name)
                        event.roles.append(role)
                        db_session.add(event)


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


def build_schedule_text():
    lines = []
    with db_connect() as db_session:
        schedule = get_events_for_week(db_session)
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
    ensure_week_events()
    text = build_schedule_text()
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    await show_main_menu(update, context)


async def send_schedule_this_week(update, context):
    text = build_schedule_text()
    await update.effective_chat.send_message(text, parse_mode=ParseMode.MARKDOWN)


async def participate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_week_events()
    keyboard = []
    with db_connect() as db_session:
        schedule = get_events_for_week(db_session)
        for date in week_dates():
            events_today = [schedule[date].get(slot) for slot in ["morning", "evening"] if schedule[date].get(slot)]
            if events_today:
                date_str = ru_date_string(date)
                keyboard.append([InlineKeyboardButton(date_str, callback_data=f"chooseday|{date.isoformat()}")])
        if not keyboard:
            await update.message.reply_text(
                "Нет событий на этой неделе. Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            await show_main_menu(update, context)
            return ConversationHandler.END
        context.user_data["schedule"] = schedule
    await update.message.reply_text(
        "Выберите день для участия:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    # No main menu here (multi-button step)
    return CHOOSING_DAY


async def choose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await show_main_menu(update, context)
        return ConversationHandler.END
    await update.callback_query.edit_message_text(
        "Выберите событие для участия:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    # No main menu here (multi-button step)
    return CHOOSING_EVENT


async def choose_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, event_id = update.callback_query.data.split("|")
    context.user_data["chosen_event_id"] = int(event_id)
    with db_connect() as db_session:
        event = db_session.query(Event).filter_by(id=int(event_id)).first()
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
    await update.callback_query.edit_message_text(
        "Выберите вашу роль для этого события:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
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
    event_id = context.user_data["chosen_event_id"]
    with db_connect() as db_session:
        already = (
            db_session.query(Participation)
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
    with db_connect() as db_session:
        db_session.add(participation)
        # Notify admins
        event = db_session.query(Event).filter_by(id=event_id).first()
        role = db_session.query(Role).filter_by(id=int(role_id)).first()
    text = (f"🟢 @{username} записался на событие:\n"
            f"{ru_date_string(event.date)}, {SLOT_RU[event.slot]} ({event.time})\n"
            f"Роль: {role.name if role else 'Без роли'}")
    await notify_admins(context, text)
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
    with db_connect() as db_session:
        parts = (
            db_session.query(Participation)
                .join(Event)
                .filter(Participation.username == username)
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
            f"{ru_date_string(event.date)}, {SLOT_RU[event.slot]} ({event.time}) — {role}"
        )
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"cancelpart|{p.id}")])
    keyboard.append([InlineKeyboardButton("❌ Отменить все", callback_data="cancelall")])
    await update.message.reply_text(
        "Выберите участие для отмены, либо отмените все одним нажатием:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # No main menu here (multi-button step)
    return CHOOSING_CANCEL


async def cancel_participation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "cancelall":
        username = update.effective_user.username
        with db_connect() as db_session:
            canceled_parts = (
                db_session.query(Participation)
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
        with db_connect() as db_session:
            db_session.query(Participation).filter_by(username=username).delete()
        for msg in notify_msgs:
            await notify_admins(context, msg)
        await update.callback_query.edit_message_text("Все ваши участия отменены.\n\nТекущее расписание на эту неделю:")
        await send_schedule_this_week(update, context)
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        _, part_id = update.callback_query.data.split("|")
        with db_connect() as db_session:
            part = db_session.query(Participation).filter_by(id=int(part_id)).first()
        if not part:
            await update.callback_query.answer("Запись не найдена.")
            await show_main_menu(update, context)
            return ConversationHandler.END
        # Notify admins
        event = part.event
        role = part.role.name if part.role else "Без роли"
        username = part.username
        text = (f"🔴 @{username} отменил участие в событии:\n"
                f"{ru_date_string(event.date)}, {SLOT_RU[event.slot]} ({event.time})\n"
                f"Роль: {role}")
        with db_connect() as db_session:
            db_session.delete(part)
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
    ensure_week_events()
    keyboard = []
    with db_connect() as db_session:
        schedule = get_events_for_week(db_session)
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
    with db_connect() as db_session:
        event = db_session.query(Event).filter_by(id=event_id).first()
        if event:
            event.time = new_time
            await update.message.reply_text("Время события успешно изменено.")
        else:
            await update.message.reply_text("Событие не найдено.")

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
