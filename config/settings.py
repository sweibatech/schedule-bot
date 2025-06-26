import os

from dotenv import load_dotenv

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
    "Понедельник": {"morning": "08:00", "evening": "19:30"},
    "Вторник": {"morning": "08:00", "evening": "19:30"},
    "Среда": {"morning": "08:00", "evening": "20:30"},
    "Четверг": {"morning": "08:00", "evening": "19:00"},
    "Пятница": {"morning": "08:00", "evening": "17:30"},
    "Суббота": {"morning": "10:00", "evening": "18:00"},
    "Воскресение": {"morning": "10:00", "evening": "18:00"},
}
DEFAULT_EVENT_NAMES = {"morning": "Утреннее служение", "evening": "Вечернее служение"}
DEFAULT_ROLES = ["Ведущий молитвы", "Хор", "Ритм"]

CHOOSING_DAY, CHOOSING_EVENT, CHOOSING_ROLE = range(3)
(
    MANAGE_EVENT, MANAGE_EVENT_SELECT, EDIT_EVENT_CHOICE, SET_EVENT_TIME,
    SET_EVENT_ROLE_ASSIGN_METHOD, ADMIN_ROLE_CHOICE, ADMIN_ROLES_SELECTED
) = range(10, 17)
CHOOSING_CANCEL = 100
