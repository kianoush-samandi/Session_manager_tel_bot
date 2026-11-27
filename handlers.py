"""
handlers.py - Telegram handlers: read the update, call the session rules, reply.

Business rules live in session_model.py, texts in texts.py, persistence in
state.py. Handlers only glue them together, guarded by two small decorators.
"""

import functools

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

import jobs
import session_messages
import session_model
import state as bot_state
import texts
from command_input import InputError, parse_new_session, parse_session_edits, require_argument

Context = ContextTypes.DEFAULT_TYPE

_ADMIN_STATUSES = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


# ---------------------------------------------------
# Shared guards and helpers
# ---------------------------------------------------

async def is_admin(update: Update, context: Context) -> bool:
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in _ADMIN_STATUSES


def admin_only(command: str):
    """Lets the handler run only for group admins; others get a polite refusal."""
    def decorator(handler):
        @functools.wraps(handler)
        async def wrapper(update: Update, context: Context):
            if not await is_admin(update, context):
                await update.effective_message.reply_text(texts.ADMIN_ONLY[command])
                return
            await handler(update, context)
        wrapper.admin_only = True  # read by commands.py to build the admins' command menu
        return wrapper
    return decorator


def is_admin_only(handler) -> bool:
    return getattr(handler, "admin_only", False)


def with_session(handler):
    """Runs the handler only if the chat has an active session, passing it in."""
    @functools.wraps(handler)
    async def wrapper(update: Update, context: Context, *args):
        session = bot_state.from_context(context).session(update.effective_chat.id)
        if session is None:
            await update.effective_message.reply_text(texts.NO_ACTIVE_SESSION)
            return
        await handler(update, context, session, *args)
    return wrapper


def replies_input_errors(handler):
    """Turns an InputError raised by command parsing into a reply to the user."""
    @functools.wraps(handler)
    async def wrapper(update: Update, context: Context, *args):
        try:
            await handler(update, context, *args)
        except InputError as error:
            await update.effective_message.reply_text(str(error))
    return wrapper


def _reply_target(update: Update):
    """The (user_id, full_name) of the user whose message was replied to, or None."""
    replied = update.effective_message.reply_to_message
    if replied and replied.from_user:
        return replied.from_user.id, replied.from_user.full_name
    return None


async def _refresh_if_active(context: Context, chat_id: int) -> None:
    state = bot_state.from_context(context)
    if state.session(chat_id):
        await session_messages.refresh(context.bot, state, chat_id)


# ---------------------------------------------------
# /help and the help-menu buttons
# ---------------------------------------------------

_HELP_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton(label, callback_data=data)] for label, data in texts.HELP_BUTTONS]
)


async def help_command(update: Update, context: Context):
    await update.effective_message.reply_text(texts.HELP_TEXT, reply_markup=_HELP_KEYBOARD)


async def handle_help_callback(update: Update, context: Context):
    """Help-menu taps: attendance and cancel/end run directly, others show a usage guide."""
    query = update.callback_query
    await query.answer()

    kind, _, action = (query.data or "").partition(":")
    if kind == "attend":
        user = update.effective_user
        await _apply_attendance(update, context, user.id, user.full_name, action)
    elif kind == "help":
        direct_actions = {"cancelsession": cancel_session, "endsession": end_session}
        if action in direct_actions:
            await direct_actions[action](update, context)
        elif action in texts.COMMAND_GUIDES:
            await query.message.reply_text(texts.COMMAND_GUIDES[action])


# ---------------------------------------------------
# Session lifecycle: /newsession /cancelsession /endsession /editsession
# ---------------------------------------------------

@admin_only("newsession")
@replies_input_errors
async def new_session(update: Update, context: Context):
    chat_id = update.effective_chat.id
    state = bot_state.from_context(context)
    if state.session(chat_id):
        await update.effective_message.reply_text(texts.SESSION_ALREADY_EXISTS)
        return

    parsed = parse_new_session(update.effective_message.text)
    session = session_model.create_session(parsed.time, parsed.place, parsed.max_main, parsed.max_reserve)
    jobs.schedule_session_jobs(context.application, chat_id, session)
    await session_messages.post_and_pin(context.bot, state, chat_id, session, update.effective_message)
    await state.start_session(chat_id, session)


async def _close_session(update: Update, context: Context, ended: bool) -> None:
    chat_id = update.effective_chat.id
    state = bot_state.from_context(context)
    session = await state.close_session(chat_id)
    jobs.clear_session_jobs(context.application, chat_id)

    if ended:
        await session_messages.close_as_ended(context.bot, state, chat_id, session)
        await update.effective_message.reply_text(texts.SESSION_ENDED_REPLY)
    else:
        await session_messages.close(context.bot, chat_id, session, texts.SESSION_CANCELLED_MESSAGE)
        await update.effective_message.reply_text(texts.SESSION_CANCELLED_REPLY)


@admin_only("cancelsession")
@with_session
async def cancel_session(update: Update, context: Context, session: dict):
    """Before the session happens: replace the list with "cancelled"."""
    await _close_session(update, context, ended=False)


@admin_only("endsession")
@with_session
async def end_session(update: Update, context: Context, session: dict):
    """After the session happened: keep the final lists and mark them as finished."""
    await _close_session(update, context, ended=True)


@admin_only("editsession")
@with_session
@replies_input_errors
async def edit_session(update: Update, context: Context, session: dict):
    chat_id = update.effective_chat.id
    updates = parse_session_edits(update.effective_message.text)

    session.update(updates)
    notes = texts.capacity_notes(session_model.apply_capacity_limits(session))
    if "time" in updates:
        jobs.schedule_session_jobs(context.application, chat_id, session)

    await session_messages.refresh(context.bot, bot_state.from_context(context), chat_id)
    reply = texts.SESSION_EDITED_REPLY
    if notes:
        reply += "\n\n" + "\n".join(notes)
    await update.effective_message.reply_text(reply)


# ---------------------------------------------------
# Aliases: /setalias /setuseralias /clearuseralias
# ---------------------------------------------------

@replies_input_errors
async def set_alias(update: Update, context: Context):
    chat_id, user_id = update.effective_chat.id, update.effective_user.id
    state = bot_state.from_context(context)
    new_alias = require_argument(update.effective_message.text, texts.SET_ALIAS_USAGE)

    await state.set_alias(chat_id, user_id, "self", new_alias)
    await update.effective_message.reply_text(texts.self_alias_set(new_alias, state.admin_alias(chat_id, user_id)))
    await _refresh_if_active(context, chat_id)


@admin_only("setuseralias")
@replies_input_errors
async def set_user_alias(update: Update, context: Context):
    target = _reply_target(update)
    if not target:
        raise InputError(texts.reply_required("setuseralias", with_alias=True))
    new_alias = require_argument(update.effective_message.text, texts.SET_USER_ALIAS_USAGE)

    chat_id = update.effective_chat.id
    target_id, target_name = target
    await bot_state.from_context(context).set_alias(chat_id, target_id, "admin", new_alias)
    await update.effective_message.reply_text(texts.admin_alias_set(new_alias, target_name))
    await _refresh_if_active(context, chat_id)


@admin_only("clearuseralias")
@replies_input_errors
async def clear_user_alias(update: Update, context: Context):
    target = _reply_target(update)
    if not target:
        raise InputError(texts.reply_required("clearuseralias", with_alias=False))

    chat_id = update.effective_chat.id
    target_id, target_name = target
    state = bot_state.from_context(context)
    if not state.admin_alias(chat_id, target_id):
        await update.effective_message.reply_text(texts.admin_alias_missing(target_name))
        return

    await state.set_alias(chat_id, target_id, "admin", None)
    await update.effective_message.reply_text(texts.admin_alias_cleared(target_name))
    await _refresh_if_active(context, chat_id)


# ---------------------------------------------------
# Guests: /addguest /removeguest
# ---------------------------------------------------

@with_session
@replies_input_errors
async def add_guest(update: Update, context: Context, session: dict):
    chat_id, inviter = update.effective_chat.id, update.effective_user
    guest_name = require_argument(update.effective_message.text, texts.ADD_GUEST_USAGE)

    placed_in = session_model.add_guest(session, chat_id, inviter.id, inviter.full_name, guest_name)
    if placed_in is None:
        await update.effective_message.reply_text(texts.GUEST_LISTS_FULL)
        return

    await update.effective_message.reply_text(texts.guest_added(guest_name, inviter.full_name, placed_in))
    await session_messages.refresh(context.bot, bot_state.from_context(context), chat_id)


@with_session
@replies_input_errors
async def remove_guest(update: Update, context: Context, session: dict):
    """Only the member who invited the guest, or an admin, can remove them."""
    guest_name = require_argument(update.effective_message.text, texts.REMOVE_GUEST_USAGE)
    match = session_model.find_guest(session, guest_name)
    if not match:
        await update.effective_message.reply_text(texts.guest_not_found(guest_name))
        return

    guest_id, matched_name = match
    inviter = session_model.guest_inviter(session, guest_id) or {}
    if inviter.get("user_id") != update.effective_user.id and not await is_admin(update, context):
        await update.effective_message.reply_text(texts.GUEST_REMOVE_FORBIDDEN)
        return

    session_model.remove_guest(session, guest_id)
    await update.effective_message.reply_text(texts.guest_removed(matched_name))
    await session_messages.refresh(context.bot, bot_state.from_context(context), update.effective_chat.id)


# ---------------------------------------------------
# Attendance: "هستم" / "نیستم" / "شاید باشم" (text or button)
# ---------------------------------------------------

@with_session
async def _apply_attendance(update: Update, context: Context, session: dict, user_id: int, name: str, action: str):
    rule = session_model.ATTENDANCE_ACTIONS.get(action)
    if rule is None:
        return

    outcome = rule(session, user_id, name)
    reply = texts.ATTENDANCE_REPLIES.get(outcome)
    if reply:
        await update.effective_message.reply_text(reply)
    if outcome.changed_session:
        await session_messages.refresh(context.bot, bot_state.from_context(context), update.effective_chat.id)


async def handle_text(update: Update, context: Context):
    action = texts.ATTENDANCE_KEYWORDS.get(update.effective_message.text.strip())
    if action is None or not bot_state.from_context(context).session(update.effective_chat.id):
        return  # ordinary chat message, or no active session: stay silent
    user = update.effective_user
    await _apply_attendance(update, context, user.id, user.full_name, action)


# ---------------------------------------------------
# New members
# ---------------------------------------------------

async def welcome_new_members(update: Update, context: Context):
    for member in update.effective_message.new_chat_members:
        if not member.is_bot:  # don't welcome bots (including this bot itself)
            await update.effective_message.reply_text(texts.welcome(member.full_name))
