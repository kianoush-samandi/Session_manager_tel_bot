"""
commands.py - The bot's slash commands: one list that drives both the handlers
and the "/" menu Telegram shows users, so the two can never drift apart.
"""

import logging
from dataclasses import dataclass
from typing import Callable

from telegram import BotCommand, BotCommandScopeAllChatAdministrators, BotCommandScopeDefault
from telegram.error import TelegramError
from telegram.ext import Application

import handlers
import texts

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Command:
    name: str
    callback: Callable

    @property
    def admin_only(self) -> bool:
        # Derived from the @admin_only decorator, so the menu always matches what is enforced.
        return handlers.is_admin_only(self.callback)

    def as_bot_command(self) -> BotCommand:
        return BotCommand(self.name, texts.COMMAND_DESCRIPTIONS[self.name])


COMMANDS = [
    Command("help", handlers.help_command),
    Command("newsession", handlers.new_session),
    Command("cancelsession", handlers.cancel_session),
    Command("endsession", handlers.end_session),
    Command("editsession", handlers.edit_session),
    Command("setalias", handlers.set_alias),
    Command("setuseralias", handlers.set_user_alias),
    Command("clearuseralias", handlers.clear_user_alias),
    Command("addguest", handlers.add_guest),
    Command("removeguest", handlers.remove_guest),
]


async def publish_command_menu(app: Application) -> None:
    """
    Registers the "/" menu with Telegram: everyone sees the general commands,
    group admins additionally see the admin-only ones.
    """
    everyone = [command.as_bot_command() for command in COMMANDS if not command.admin_only]
    admins = [command.as_bot_command() for command in COMMANDS]
    try:
        await app.bot.set_my_commands(everyone, scope=BotCommandScopeDefault())
        await app.bot.set_my_commands(admins, scope=BotCommandScopeAllChatAdministrators())
    except TelegramError as error:
        logger.warning("Could not publish the command menu: %s", error)
