from datetime import datetime, timedelta
from typing import List
from db.queries import (
    get_events_for_dates, get_or_create_role
)
from db.dto import EventDTO
from db.context import db_session
from db_setup import Event

WEEKDAY_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
    4: "Пятница", 5: "Суббота", 6: "Воскресенье",
}
DEFAULT_EVENT_TIMES = {
    "Понедельник":    {"morning": "08:00", "evening": "19:30"},
    "Вторник":        {"morning": "08:00", "evening": "19:30"},
    "Среда":          {"morning": "08:00", "evening": "20:30"},
    "Четверг":        {"morning": "08:00", "evening": "19:30"},
    "Пятница":        {"morning": "08:00", "evening": "19:00"},
    "Суббота":        {"morning": "10:00", "evening": "18:00"},
    "Воскресенье":    {"morning": "10:00", "evening": "18:00"},
}
DEFAULT_EVENT_NAMES = {"morning": "Утреннее служение", "evening": "Вечернее служение"}
DEFAULT_ROLES = ["Ведущий молитвы", "Хор", "Ритм"]

def week_dates() -> List[datetime.date]:
    today = datetime.today().date()
    return [(today + timedelta(days=i)) for i in range(7)]

def ensure_week_events():
    with db_session() as session:
        dates = week_dates()
        existing = set((e.date, e.slot) for e in session.query(Event).filter(Event.date.in_(dates)).all())
        for date in dates:
            weekday = WEEKDAY_RU[date.weekday()]
            for slot in ["morning", "evening"]:
                if (date, slot) not in existing:
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

def get_week_schedule() -> List[EventDTO]:
    with db_session() as session:
        return get_events_for_dates(session, week_dates())