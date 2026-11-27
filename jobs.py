"""
jobs.py - Scheduled work per session: the day-before reminder and the automatic end.
"""

import logging
from datetime import datetime, timedelta

from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

import config
import session_messages
import state as bot_state
import texts
from time_parser import parse_session_datetime

logger = logging.getLogger(__name__)

REMINDER_BEFORE = timedelta(days=1)
AUTO_END_AFTER = timedelta(hours=2)


def _job_names(chat_id: int) -> tuple[str, str]:
    return f"session_reminder_{chat_id}", f"session_end_{chat_id}"


def clear_session_jobs(app: Application, chat_id: int) -> None:
    """Removes any pending reminder/end jobs for a chat (on cancel/end/edit)."""
    if not app.job_queue:
        return
    for name in _job_names(chat_id):
        for job in app.job_queue.get_jobs_by_name(name):
            job.schedule_removal()


def _session_start(session: dict, recompute: bool):
    """
    recompute=True (new session or time edited): parse session["time"] again and
    store it as ISO text in session["scheduled_dt"] so it survives restarts.
    recompute=False (bot restart): reuse the stored value, so a weekday that has
    already passed doesn't silently roll forward to next week.
    """
    if recompute:
        start = parse_session_datetime(session["time"])
        session["scheduled_dt"] = start.isoformat() if start else None
        return start
    stored = session.get("scheduled_dt")
    return datetime.fromisoformat(stored) if stored else None


def schedule_session_jobs(app: Application, chat_id: int, session: dict, recompute: bool = True) -> None:
    """Schedules the reminder (1 day before) and the auto-end (2 hours after start)."""
    if not app.job_queue:
        logger.warning(
            "JobQueue is not available (install python-telegram-bot[job-queue]); "
            "reminders and auto-end won't be scheduled."
        )
        return

    clear_session_jobs(app, chat_id)
    start = _session_start(session, recompute)
    if start is None:
        return

    now = config.now()
    reminder_name, end_name = _job_names(chat_id)
    job_data = {"chat_id": chat_id}

    reminder_at = start - REMINDER_BEFORE
    if reminder_at > now:
        app.job_queue.run_once(send_reminder, when=reminder_at, chat_id=chat_id, name=reminder_name, data=job_data)

    # If the end time passed while the bot was offline, end the session right away.
    end_at = max(start + AUTO_END_AFTER, now)
    app.job_queue.run_once(end_automatically, when=end_at, chat_id=chat_id, name=end_name, data=job_data)


async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data["chat_id"]
    state = bot_state.from_context(context)
    session = state.session(chat_id)
    if not session:
        return
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=texts.reminder_html(session, state.labeler(chat_id, session)),
            parse_mode="HTML",
        )
    except TelegramError as error:
        logger.warning("Could not send reminder for chat %s: %s", chat_id, error)


async def end_automatically(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data["chat_id"]
    state = bot_state.from_context(context)
    session = await state.close_session(chat_id)
    if session:
        await session_messages.close_as_ended(context.bot, state, chat_id, session)
