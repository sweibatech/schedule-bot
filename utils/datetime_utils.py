from datetime import datetime, timedelta

from config.settings import WEEKDAY_RU, MONTH_RU


def week_dates():
    today = datetime.today()
    start = today - timedelta(days=today.weekday())  # Monday
    return [(start + timedelta(days=i)).date() for i in range(7)]


def ru_date_string(date):
    weekday = WEEKDAY_RU[date.weekday()]
    day = date.day
    month = MONTH_RU[date.month]
    return f"{weekday}, {day} {month}"