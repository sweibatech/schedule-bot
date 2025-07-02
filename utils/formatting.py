import re
from datetime import datetime, date as dt_date
from service.schedule_service import week_dates

WEEKDAY_RU = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}
MONTH_RU = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "мая", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}
SLOT_RU = {
    "morning": "Утро",
    "evening": "Вечер",
}

def get_slot_label(slot, time):
    return f"{SLOT_RU.get(slot, slot)} ({time})"

def ru_date_string(date_input) -> str:
    if isinstance(date_input, dt_date):
        date_obj = date_input
    else:
        date_obj = datetime.fromisoformat(date_input).date()
    weekday = WEEKDAY_RU[date_obj.weekday()]
    day = date_obj.day
    month = MONTH_RU[date_obj.month]
    return f"{weekday}, {day} {month}"

def escape_username_md2(username: str) -> str:
    # Escapes only special characters needed for MarkdownV2 in usernames (especially _)
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', username)

def build_schedule_text(event_dtos):
    lines = []
    dates = week_dates()
    events_by_date = {date: [] for date in dates}
    for event in event_dtos:
        event_date = datetime.fromisoformat(event.date).date()
        events_by_date[event_date].append(event)

    for date in dates:
        day_lines = []
        for slot in ["morning", "evening"]:
            event = next((e for e in events_by_date[date] if e.slot == slot), None)
            if event:
                if event.participations:
                    part_lines = [
                        f"      - @{escape_username_md2(p.username)}: {p.role.name if p.role else 'Без роли'}"
                        for p in event.participations
                    ]
                    participants_text = "\n".join(part_lines)
                    day_lines.append(
                        f"  - {SLOT_RU[slot]} ({event.time}):\n{participants_text}"
                    )
                else:
                    day_lines.append(
                        f"  - {SLOT_RU[slot]} ({event.time})"
                    )
        if day_lines:
            lines.append(ru_date_string(date.isoformat()))
            lines.extend(day_lines)
    return "\n".join(lines) if lines else "Нет событий на ближайшие 7 дней."