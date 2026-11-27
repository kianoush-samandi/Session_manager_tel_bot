from datetime import datetime

import pytest

from config import TEHRAN_TZ
from time_parser import parse_session_datetime

# A Wednesday (weekday 2), 10:00 Tehran time.
NOW = datetime(2026, 11, 25, 10, 0, tzinfo=TEHRAN_TZ)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2شنبه 9:30 صبح", datetime(2026, 11, 30, 9, 30, tzinfo=TEHRAN_TZ)),
        ("جمعه 20:00", datetime(2026, 11, 27, 20, 0, tzinfo=TEHRAN_TZ)),
        ("پنجشنبه 8:30 شب", datetime(2026, 11, 26, 20, 30, tzinfo=TEHRAN_TZ)),
        ("سه‌شنبه ۷:۱۵ عصر", datetime(2026, 12, 1, 19, 15, tzinfo=TEHRAN_TZ)),
        ("یک شنبه 18:00", datetime(2026, 11, 29, 18, 0, tzinfo=TEHRAN_TZ)),
        ("شنبه 10:00", datetime(2026, 11, 28, 10, 0, tzinfo=TEHRAN_TZ)),
        ("چهارشنبه 9:00", datetime(2026, 12, 2, 9, 0, tzinfo=TEHRAN_TZ)),  # passed today -> next week
        ("چهارشنبه 11:00", datetime(2026, 11, 25, 11, 0, tzinfo=TEHRAN_TZ)),
    ],
)
def test_parses_weekday_and_time(text, expected):
    assert parse_session_datetime(text, NOW) == expected


@pytest.mark.parametrize("text", ["فردا 20:00", "جمعه ساعت ۸", "جمعه 25:00", ""])
def test_returns_none_for_invalid_text(text):
    assert parse_session_datetime(text, NOW) is None
