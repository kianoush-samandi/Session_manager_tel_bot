"""
time_parser.py - Turns free Persian text like "2شنبه 9:30 صبح" into a datetime.

Pure functions only (no Telegram, no I/O), so the parsing rules are easy to test.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

import config

_ZWNJ = "‌"

# Every written form of a Persian weekday -> Python's weekday() (Monday=0 ... Sunday=6).
_WEEKDAY_MAP = {
    "شنبه": 5,
    "یکشنبه": 6, "یک شنبه": 6, "1شنبه": 6,
    "دوشنبه": 0, "دو شنبه": 0, "2شنبه": 0,
    "سه‌شنبه": 1, "سه شنبه": 1, "3شنبه": 1,
    "چهارشنبه": 2, "چهار شنبه": 2, "4شنبه": 2,
    "پنجشنبه": 3, "پنج شنبه": 3, "5شنبه": 3,
    "جمعه": 4,
}
# Longest forms first, so "یک شنبه" is matched before a bare "شنبه".
_WEEKDAY_FORMS = sorted(
    ((form.replace(_ZWNJ, " "), weekday) for form, weekday in _WEEKDAY_MAP.items()),
    key=lambda item: len(item[0]),
    reverse=True,
)
_AFTERNOON_MARKERS = ("عصر", "بعد از ظهر", "ظهر", "شب")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_CLOCK_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")


def _find_weekday(text: str) -> Optional[int]:
    return next((weekday for form, weekday in _WEEKDAY_FORMS if form in text), None)


def _find_clock(text: str) -> Optional[tuple[int, int]]:
    match = _CLOCK_PATTERN.search(text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    if hour < 12 and any(marker in text for marker in _AFTERNOON_MARKERS):
        hour += 12
    return hour, minute


def parse_session_datetime(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Returns the next datetime matching the weekday and HH:MM in text,
    or None if either part is missing/invalid.
    """
    now = now or config.now()
    flat = text.translate(_PERSIAN_DIGITS).replace(_ZWNJ, " ")

    weekday = _find_weekday(flat)
    clock = _find_clock(flat)
    if weekday is None or clock is None:
        return None

    hour, minute = clock
    days_ahead = (weekday - now.weekday()) % 7
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if days_ahead == 0 and candidate <= now:
        days_ahead = 7  # same weekday but the time already passed -> next week

    return candidate + timedelta(days=days_ahead)
