"""
bot.py - Entry point: reads the token, wires handlers, starts polling.

Run with:  python bot.py
"""

import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import handlers
import jobs
import state as bot_state
from config import ConfigError, load_bot_token

logger = logging.getLogger(__name__)

# Only react to new messages: editing an old "/addguest ..." or "هستم" must not run it again.
NEW_MESSAGES = filters.UpdateType.MESSAGE

COMMANDS = {
    "help": handlers.help_command,
    "newsession": handlers.new_session,
    "cancelsession": handlers.cancel_session,
    "endsession": handlers.end_session,
    "editsession": handlers.edit_session,
    "setalias": handlers.set_alias,
    "setuseralias": handlers.set_user_alias,
    "clearuseralias": handlers.clear_user_alias,
    "addguest": handlers.add_guest,
    "removeguest": handlers.remove_guest,
}


async def restore_state(app: Application) -> None:
    """On startup: load sessions/aliases from the database and re-schedule their jobs."""
    state = bot_state.BotState()
    await state.load()
    bot_state.attach(app, state)

    for chat_id, session in state.sessions.items():
        jobs.schedule_session_jobs(app, chat_id, session, recompute=False)

    logger.info(
        "Loaded %d session(s) and %d chat(s) with aliases from database.",
        len(state.sessions),
        state.alias_chat_count,
    )


async def log_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error while processing %s", update, exc_info=context.error)


def build_application(token: str) -> Application:
    app = ApplicationBuilder().token(token).post_init(restore_state).build()

    for command, callback in COMMANDS.items():
        app.add_handler(CommandHandler(command, callback, filters=NEW_MESSAGES))
    app.add_handler(CallbackQueryHandler(handlers.handle_help_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handlers.welcome_new_members))
    app.add_handler(MessageHandler(NEW_MESSAGES & filters.TEXT & ~filters.COMMAND, handlers.handle_text))
    app.add_error_handler(log_error)
    return app


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    # httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        token = load_bot_token()
    except ConfigError as error:
        sys.exit(f"Error: {error}")

    print("Bot is running...  Ctrl+C for stop.")
    build_application(token).run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
