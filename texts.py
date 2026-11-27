"""
texts.py - Every user-facing (Persian) string and message layout.

Presentation only: functions here build text from data they are given and
never touch Telegram, the database, or the session rules.
"""

import html
from typing import Callable

from session_model import MAIN, NOT_COMING, RESERVE, Attendance

# A function that turns (entry_id, stored_name) into the name to display.
EntryLabeler = Callable[[object, str], str]

NAME_SEPARATOR = "، "

# ---------------------------------------------------
# Common replies
# ---------------------------------------------------

NO_ACTIVE_SESSION = "سانس فعالی وجود نداره."
SESSION_ALREADY_EXISTS = "یک سانس فعال از قبل وجود داره. اول با /cancelsession کنسلش کن."
SESSION_CANCELLED_MESSAGE = "سانس کنسل شد"
SESSION_CANCELLED_REPLY = "سانس کنسل شد. ❌"
SESSION_ENDED_FOOTER = "\n\n🏁 این سانس به پایان رسید."
SESSION_ENDED_REPLY = "سانس با موفقیت پایان یافت. 🏁"
SESSION_EDITED_REPLY = "سانس ویرایش شد. ✏️"

ADMIN_ONLY = {
    "newsession": "فقط ادمین گروه می‌تونه سانس جدید بسازه.",
    "cancelsession": "فقط ادمین گروه می‌تونه سانس رو کنسل کنه.",
    "endsession": "فقط ادمین گروه می‌تونه سانس رو پایان بده.",
    "editsession": "فقط ادمین گروه می‌تونه سانس رو ویرایش کنه.",
    "setuseralias": "فقط ادمین گروه می‌تونه لقب یه نفر دیگه رو تایید کنه.",
    "clearuseralias": "فقط ادمین گروه می‌تونه لقب تاییدشده رو پاک کنه.",
}

ATTENDANCE_REPLIES = {
    Attendance.JOINED_RESERVE: "سانس اصلی پره، تو لیست رزرو قرار گرفتی.",
    Attendance.STILL_IN_RESERVE: "سانس اصلی پره، تو لیست رزرو قرار گرفتی.",
    Attendance.SESSION_FULL: "سانس و لیست رزرو هر دو پر هستن.",
    Attendance.RESERVE_FULL: "لیست رزرو پر شده.",
}

# Plain-text messages that act like buttons.
ATTENDANCE_KEYWORDS = {"هستم": "main", "نیستم": "out", "شاید باشم": "maybe"}

# ---------------------------------------------------
# Command usage / validation errors
# ---------------------------------------------------

TIME_FORMAT_HELP = (
    "فرمت زمان درست نیست. 🕒\n\n"
    "فرمت درست: (روز هفته) (ساعت:دقیقه) (صبح/عصر/شب)\n"
    "روزهای مجاز: شنبه، یکشنبه یا 1شنبه، دوشنبه یا 2شنبه، سه‌شنبه یا 3شنبه، "
    "چهارشنبه یا 4شنبه، پنجشنبه یا 5شنبه، جمعه\n\n"
    "مثال‌ها:\n"
    "2شنبه 9:30 صبح\n"
    "جمعه 20:00\n"
    "پنجشنبه 8:30 شب"
)
NEW_SESSION_USAGE = (
    "فرمت درست:\n/newsession زمان | مکان | حداکثر نفر | حداکثر رزرو\n\n"
    "مثال:\n/newsession امروز ساعت 20 | زمین فوتبال محله | 10 | 3"
)
NEW_SESSION_PARTS_ERROR = "باید ۴ بخش با | از هم جدا بشه: زمان | مکان | حداکثر نفر | حداکثر رزرو"
CAPACITY_NOT_NUMBER = "حداکثر نفر و حداکثر رزرو باید فقط عدد باشن."
EDIT_SESSION_USAGE = (
    "فرمت درست:\n/editsession زمان=... | مکان=... | حداکثر نفر=... | حداکثر رزرو=...\n\n"
    "فقط فیلدهایی که می‌نویسی تغییر می‌کنن. مثال:\n"
    "/editsession مکان=زمین شماره ۲ | حداکثر نفر=12"
)
EDIT_NO_FIELDS = "هیچ فیلدی برای ویرایش داده نشده."
SET_ALIAS_USAGE = "فرمت درست:\n/setalias لقب\n\nمثال:\n/setalias کاپیتان"
SET_USER_ALIAS_USAGE = (
    "فرمت درست:\n(ریپلای روی پیام فرد) /setuseralias لقب\n\nمثال:\n/setuseralias کاپیتان"
)
ADD_GUEST_USAGE = "فرمت درست:\n/addguest نام یا لقب دوست\n\nمثال:\n/addguest علی (دوست رضا)"
REMOVE_GUEST_USAGE = "فرمت درست:\n/removeguest نام یا لقب دوست\n\nمثال:\n/removeguest علی"
GUEST_LISTS_FULL = "سانس و لیست رزرو هر دو پر هستن، نمی‌شه مهمون اضافه کرد."
GUEST_REMOVE_FORBIDDEN = "فقط کسی که این مهمون رو دعوت کرده یا ادمین می‌تونه حذفش کنه."


def edit_bad_part(part: str) -> str:
    return f"فرمت این بخش اشتباهه: «{part}»\nباید به شکل «نام فیلد=مقدار» باشه."


def edit_unknown_field(field_name: str) -> str:
    return f"فیلد ناشناخته: «{field_name}»\nفیلدهای مجاز: زمان، مکان، حداکثر نفر، حداکثر رزرو"


def edit_field_not_number(field_name: str) -> str:
    return f"«{field_name}» باید فقط عدد باشه."


def reply_required(command: str, with_alias: bool) -> str:
    alias_part = " لقب" if with_alias else ""
    return (
        "این دستور رو باید روی پیام همون فرد ریپلای کنی.\n"
        f"فرمت درست:\n(ریپلای روی پیام فرد) /{command}{alias_part}"
    )


# ---------------------------------------------------
# Alias replies
# ---------------------------------------------------

def self_alias_set(new_alias: str, admin_alias: str = None) -> str:
    if admin_alias:
        return (
            f"لقب «{new_alias}» ثبت شد، ولی چون ادمین برات لقب «{admin_alias}» تایید کرده، "
            "همون لقب توی لیست‌ها نشون داده می‌شه."
        )
    return f"لقبت به «{new_alias}» تغییر کرد. ✅"


def admin_alias_set(new_alias: str, target_name: str) -> str:
    return f"لقب «{new_alias}» برای {target_name} تایید و ثبت شد. ✅"


def admin_alias_missing(target_name: str) -> str:
    return f"برای {target_name} لقب تاییدشده‌ای ثبت نشده بود."


def admin_alias_cleared(target_name: str) -> str:
    return f"لقب تاییدشده برای {target_name} پاک شد. ✅"


# ---------------------------------------------------
# Guest replies
# ---------------------------------------------------

def guest_added(guest_name: str, inviter_name: str, placed_in: str) -> str:
    note = "\nسانس اصلی پره، دوستت تو لیست رزرو قرار گرفت." if placed_in == RESERVE else ""
    return f"«{guest_name}» به‌عنوان مهمون {inviter_name} به لیست اضافه شد. ✅{note}"


def guest_not_found(guest_name: str) -> str:
    return f"مهمونی با نام «{guest_name}» توی لیست پیدا نشد."


def guest_removed(guest_name: str) -> str:
    return f"«{guest_name}» از لیست حذف شد. ❌"


# ---------------------------------------------------
# Session message layout
# ---------------------------------------------------

def _names(entries) -> str:
    return NAME_SEPARATOR.join(name for _, name in entries)


def _numbered(entries, label: EntryLabeler) -> str:
    return "".join(
        f"{i}. {label(entry_id, name)}\n" for i, (entry_id, name) in enumerate(entries, start=1)
    )


def _numbered_or_empty(entries, label: EntryLabeler) -> str:
    return _numbered(entries, label) or "خالی\n"


def session_text(session: dict, label: EntryLabeler) -> str:
    """The text of the pinned session message."""
    main, reserve = session[MAIN], session[RESERVE]
    not_coming = session.get(NOT_COMING, [])

    text = (
        "📅 سانس جدید\n"
        f"🕒 زمان: {session['time']}\n"
        f"📍 مکان: {session['place']}\n"
        f"👥 ظرفیت: {len(main)}/{session['max_main']}\n\n"
        "✅ لیست اصلی:\n"
        f"{_numbered_or_empty(main, label)}"
        f"\n🕓 لیست رزرو ({len(reserve)}/{session['max_reserve']}):\n"
        f"{_numbered_or_empty(reserve, label)}"
    )
    if not_coming:
        text += f"\n❌ نیستن ({len(not_coming)}):\n{_numbered(not_coming, label)}"

    return text + "\nبرای شرکت بنویس: هستم\nبرای انصراف بنویس: نیستم\nبرای رزرو بنویس: شاید باشم"


def ended_session_text(session: dict, label: EntryLabeler) -> str:
    return session_text(session, label) + SESSION_ENDED_FOOTER


def mention_html(entry_id, name: str) -> str:
    """An HTML inline mention for a real user, or just the escaped name for guests."""
    safe_name = html.escape(name)
    if isinstance(entry_id, int):
        return f'<a href="tg://user?id={entry_id}">{safe_name}</a>'
    return safe_name


def reminder_html(session: dict, label: EntryLabeler) -> str:
    """The day-before reminder (HTML), mentioning everyone in the main list."""
    text = (
        "⏰ یادآوری: فردا سانس داری!\n"
        f"🕒 زمان: {html.escape(session['time'])}\n"
        f"📍 مکان: {html.escape(session['place'])}\n"
    )
    if session[MAIN]:
        mentions = "\n".join(
            mention_html(entry_id, label(entry_id, name)) for entry_id, name in session[MAIN]
        )
        text += f"\n👥 لیست اصلی:\n{mentions}"
    return text


def capacity_notes(changes) -> list[str]:
    """Human-readable notes about who moved after /editsession changed capacities."""
    notes = []
    if changes.moved_to_reserve:
        notes.append(f"به لیست رزرو منتقل شدن: {_names(changes.moved_to_reserve)}")
    if changes.dropped_from_main:
        notes.append(f"⚠️ به دلیل پر بودن رزرو، از سانس حذف شدن: {_names(changes.dropped_from_main)}")
    if changes.dropped_from_reserve:
        notes.append(f"⚠️ از لیست رزرو حذف شدن (ظرفیت کم شد): {_names(changes.dropped_from_reserve)}")
    if changes.promoted:
        notes.append(f"⬆️ از رزرو به لیست اصلی منتقل شدن: {_names(changes.promoted)}")
    return notes


# ---------------------------------------------------
# Help, welcome, and help-menu guides
# ---------------------------------------------------

HELP_TEXT = (
    "\tNGO Bot commands\n"
    "📖 راهنمای دستورات:\n\n"
    "🔹 /newsession زمان | مکان | حداکثر نفر | حداکثر رزرو\n"
    "ساخت سانس جدید (فقط ادمین)\n\n"
    "🔸 فرمت درست زمان: (روز هفته) (ساعت:دقیقه) (صبح/عصر/شب)\n"
    "مثال: 2شنبه 9:30 صبح  یا  جمعه 20:00  یا  پنجشنبه 8:30 شب\n\n"
    "🔹 /cancelsession\n"
    "کنسل کردن سانس فعال، قبل از برگزاری سانس (فقط ادمین)\n\n"
    "🔹 /endsession\n"
    "پایان دادن دستی به سانس، بعد از برگزار شدنش (فقط ادمین). "
    "اگه پایان ندی، بات ۲ ساعت بعد از زمان سانس خودش این کارو می‌کنه.\n\n"
    "🔹 /editsession زمان=... | مکان=... | حداکثر نفر=... | حداکثر رزرو=...\n"
    "ویرایش سانس فعال، فقط فیلدهایی که می‌نویسی تغییر می‌کنن (فقط ادمین)\n\n"
    "🔹 /setalias لقب\n"
    "انتخاب لقب برای خودت\n\n"
    "🔹 (ریپلای روی پیام فرد) /setuseralias لقب\n"
    "تایید لقب برای یه نفر دیگه، این لقب اولویت داره (فقط ادمین)\n\n"
    "🔹 (ریپلای روی پیام فرد) /clearuseralias\n"
    "پاک کردن لقب تاییدشده‌ی ادمین برای یه نفر (فقط ادمین)\n\n"
    "🔹 /addguest نام دوست\n"
    "اضافه کردن دوستی که عضو گروه نیست به لیست سانس\n\n"
    "🔹 /removeguest نام دوست\n"
    "حذف مهمون از لیست (فقط دعوت‌کننده یا ادمین)\n\n"
    "🔹 هستم\n"
    "اضافه شدن به لیست اصلی سانس\n\n"
    "🔹 نیستم\n"
    "انصراف از سانس\n\n"
    "🔹 شاید باشم\n"
    "قرار گرفتن در لیست رزرو\n\n"
    "🔸 یک روز قبل از سانس، بات خودکار یادآوری می‌فرسته و افراد لیست اصلی رو منشن می‌کنه.\n"
)

# Descriptions shown in Telegram's "/" command menu (max 256 characters each).
COMMAND_DESCRIPTIONS = {
    "help": "راهنمای دستورات",
    "newsession": "ساخت سانس جدید",
    "cancelsession": "کنسل کردن سانس فعال (قبل از برگزاری)",
    "endsession": "پایان دادن به سانس (بعد از برگزاری)",
    "editsession": "ویرایش زمان، مکان یا ظرفیت سانس",
    "setalias": "انتخاب لقب برای خودت",
    "setuseralias": "تایید لقب برای یه نفر (ریپلای روی پیامش)",
    "clearuseralias": "پاک کردن لقب تاییدشده (ریپلای روی پیامش)",
    "addguest": "اضافه کردن دوستت به لیست سانس",
    "removeguest": "حذف مهمون از لیست",
}

# Help-menu buttons: (label, callback_data).
HELP_BUTTONS = [
    ("🔹 /newsession", "help:newsession"),
    ("🔹 /cancelsession", "help:cancelsession"),
    ("🔹 /endsession", "help:endsession"),
    ("🔹 /editsession", "help:editsession"),
    ("🔹 /setalias", "help:setalias"),
    ("🔹 /setuseralias", "help:setuseralias"),
    ("🔹 /addguest", "help:addguest"),
    ("🔹 /removeguest", "help:removeguest"),
    ("✅ هستم", "attend:main"),
    ("❌ نیستم", "attend:out"),
    ("🕓 شاید باشم", "attend:maybe"),
]

# Shown when a help-menu button of a command that needs typed arguments is tapped.
COMMAND_GUIDES = {
    "newsession": "برای ساخت سانس جدید بنویس:\n/newsession زمان | مکان | حداکثر نفر | حداکثر رزرو",
    "editsession": "برای ویرایش سانس بنویس:\n/editsession زمان=... | مکان=... | حداکثر نفر=... | حداکثر رزرو=...",
    "setalias": "برای انتخاب لقب بنویس:\n/setalias لقب",
    "setuseralias": "روی پیام فرد ریپلای کن و بنویس:\n/setuseralias لقب",
    "addguest": "برای اضافه کردن مهمون بنویس:\n/addguest نام دوست",
    "removeguest": "برای حذف مهمون بنویس:\n/removeguest نام دوست",
}


def welcome(display_name: str) -> str:
    return (
        f"سلام {display_name}! 👋\n"
        "به گروه خوش اومدی.\n\n"
        "من دستیار صدرا هستم و کارم مدیریت سانس‌ها و لیست شرکت‌کننده‌هاست.\n\n"
        "🔹 با /setalias می‌تونی برای خودت یه لقب انتخاب کنی.\n"
        "🔹 با /help می‌تونی بقیه‌ی دستورات رو ببینی."
    )
