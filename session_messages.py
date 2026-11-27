"""
session_messages.py - Keeps the pinned session message in Telegram up to date.

Shared by the command handlers and the scheduled jobs, so "refresh the list",
"cancel" and "end" all go through one implementation.
"""

import logging

from telegram import Bot
from telegram.error import TelegramError

import texts
from state import BotState

logger = logging.getLogger(__name__)


async def _edit(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    except TelegramError as error:
        logger.warning("Could not edit session message in chat %s: %s", chat_id, error)


async def _unpin(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.unpin_chat_message(chat_id, message_id)
    except TelegramError as error:
        logger.warning("Could not unpin session message in chat %s: %s", chat_id, error)


async def post_and_pin(bot: Bot, state: BotState, chat_id: int, session: dict, reply_to) -> None:
    """Sends the session message as a reply, remembers its id, and pins it."""
    sent = await reply_to.reply_text(texts.session_text(session, state.labeler(chat_id, session)))
    session["message_id"] = sent.message_id
    try:
        await bot.pin_chat_message(chat_id, sent.message_id)
    except TelegramError as error:
        logger.warning("Could not pin session message in chat %s: %s", chat_id, error)


async def refresh(bot: Bot, state: BotState, chat_id: int) -> None:
    """Persists the chat's session and re-renders its pinned message."""
    session = state.session(chat_id)
    if not session:
        return
    await state.save_session(chat_id)
    if session.get("message_id"):
        await _edit(bot, chat_id, session["message_id"], texts.session_text(session, state.labeler(chat_id, session)))


async def close(bot: Bot, chat_id: int, session: dict, final_text: str) -> None:
    """Replaces the pinned message with final_text and unpins it."""
    message_id = session.get("message_id")
    if not message_id:
        return
    await _edit(bot, chat_id, message_id, final_text)
    await _unpin(bot, chat_id, message_id)


async def close_as_ended(bot: Bot, state: BotState, chat_id: int, session: dict) -> None:
    await close(bot, chat_id, session, texts.ended_session_text(session, state.labeler(chat_id, session)))
