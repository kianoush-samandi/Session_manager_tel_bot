"""
command_input.py - Validates the arguments typed after a command.

Each parser either returns clean values or raises InputError carrying the
Persian message to show the user. Handlers stay thin: parse, act, reply.
"""

from dataclasses import dataclass

import texts
from time_parser import parse_session_datetime


class InputError(ValueError):
    """Invalid user input; str(error) is the reply to send back."""


@dataclass
class NewSessionInput:
    time: str
    place: str
    max_main: int
    max_reserve: int


_EDITABLE_FIELDS = {
    "زمان": "time",
    "مکان": "place",
    "حداکثر نفر": "max_main",
    "حداکثر رزرو": "max_reserve",
}
_NUMERIC_FIELDS = {"max_main", "max_reserve"}


def command_argument(message_text: str) -> str:
    """Returns everything after the command word ("/cmd args" -> "args"), stripped."""
    parts = (message_text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def require_argument(message_text: str, usage: str) -> str:
    argument = command_argument(message_text)
    if not argument:
        raise InputError(usage)
    return argument


def _split_fields(argument: str) -> list[str]:
    return [part.strip() for part in argument.split("|")]


def _validate_time(time_text: str) -> str:
    if parse_session_datetime(time_text) is None:
        raise InputError(texts.TIME_FORMAT_HELP)
    return time_text


def parse_new_session(message_text: str) -> NewSessionInput:
    argument = require_argument(message_text, texts.NEW_SESSION_USAGE)
    parts = _split_fields(argument)
    if len(parts) != 4:
        raise InputError(texts.NEW_SESSION_PARTS_ERROR)

    time_text, place, max_main, max_reserve = parts
    if not max_main.isdecimal() or not max_reserve.isdecimal():
        raise InputError(texts.CAPACITY_NOT_NUMBER)

    return NewSessionInput(_validate_time(time_text), place, int(max_main), int(max_reserve))


def parse_session_edits(message_text: str) -> dict:
    """Returns {internal_key: value} for the fields present in "/editsession field=value | ...". """
    argument = require_argument(message_text, texts.EDIT_SESSION_USAGE)
    parts = [part for part in _split_fields(argument) if part]
    if not parts:
        raise InputError(texts.EDIT_NO_FIELDS)

    updates = {}
    for part in parts:
        if "=" not in part:
            raise InputError(texts.edit_bad_part(part))
        field_name, value = (piece.strip() for piece in part.split("=", 1))

        key = _EDITABLE_FIELDS.get(field_name)
        if key is None:
            raise InputError(texts.edit_unknown_field(field_name))
        if key in _NUMERIC_FIELDS:
            if not value.isdecimal():
                raise InputError(texts.edit_field_not_number(field_name))
            value = int(value)
        updates[key] = value

    if "time" in updates:
        _validate_time(updates["time"])
    return updates
