import asyncio
from unittest.mock import AsyncMock, MagicMock

from telegram import BotCommandScopeAllChatAdministrators, BotCommandScopeDefault

import commands
import texts

ADMIN_COMMANDS = {"newsession", "cancelsession", "endsession", "editsession", "setuseralias", "clearuseralias"}


def test_every_command_has_a_short_description():
    for command in commands.COMMANDS:
        assert 0 < len(texts.COMMAND_DESCRIPTIONS[command.name]) <= 256


def test_admin_flags_follow_the_decorator():
    assert {c.name for c in commands.COMMANDS if c.admin_only} == ADMIN_COMMANDS


def test_menu_shows_admin_commands_only_to_admins():
    app = MagicMock()
    app.bot.set_my_commands = AsyncMock()
    asyncio.run(commands.publish_command_menu(app))

    menus = {type(call.kwargs["scope"]): {c.command for c in call.args[0]} for call in app.bot.set_my_commands.call_args_list}
    all_names = {c.name for c in commands.COMMANDS}
    assert menus[BotCommandScopeDefault] == all_names - ADMIN_COMMANDS
    assert menus[BotCommandScopeAllChatAdministrators] == all_names
