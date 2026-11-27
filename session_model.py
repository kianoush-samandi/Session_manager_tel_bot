"""
session_model.py - Business rules for a session's lists (pure, no Telegram, no I/O).

A session is a plain dict so it serializes to the database unchanged:
    {
        "time": str, "place": str, "max_main": int, "max_reserve": int,
        "main": [(id, name)], "reserve": [(id, name)], "not_coming": [(id, name)],
        "maybe_ids": [user_id],          # joined reserve on purpose ("شاید باشم")
        "guest_owners": {guest_id: {"user_id": int, "name": str}},
        "guest_seq": int,                # counter for unique guest ids
        "message_id": int | None,        # the pinned session message
        "scheduled_dt": str | None,      # ISO datetime, set by the scheduler
    }
An entry id is a Telegram user id (int) or a guest id (str "guest:<chat>:<n>").
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Union

EntryId = Union[int, str]
Entry = tuple[EntryId, str]

MAIN = "main"
RESERVE = "reserve"
NOT_COMING = "not_coming"
_CAPACITY_KEY = {MAIN: "max_main", RESERVE: "max_reserve"}
_GUEST_PREFIX = "guest:"


class Attendance(Enum):
    JOINED_MAIN = auto()
    JOINED_RESERVE = auto()
    STILL_IN_RESERVE = auto()
    MARKED_OUT = auto()
    MARKED_MAYBE = auto()
    UNCHANGED = auto()
    SESSION_FULL = auto()
    RESERVE_FULL = auto()

    @property
    def changed_session(self) -> bool:
        return self in _CHANGING_OUTCOMES


_CHANGING_OUTCOMES = {
    Attendance.JOINED_MAIN,
    Attendance.JOINED_RESERVE,
    Attendance.MARKED_OUT,
    Attendance.MARKED_MAYBE,
}


@dataclass
class CapacityChanges:
    """What happened to people when an admin changed the session's capacities."""

    moved_to_reserve: list[Entry] = field(default_factory=list)
    dropped_from_main: list[Entry] = field(default_factory=list)
    dropped_from_reserve: list[Entry] = field(default_factory=list)
    promoted: list[Entry] = field(default_factory=list)


def create_session(time: str, place: str, max_main: int, max_reserve: int) -> dict:
    return {
        "time": time,
        "place": place,
        "max_main": max_main,
        "max_reserve": max_reserve,
        MAIN: [],
        RESERVE: [],
        NOT_COMING: [],
        "maybe_ids": [],
        "guest_owners": {},
        "guest_seq": 0,
        "message_id": None,
    }


# ---------------------------------------------------
# Small helpers
# ---------------------------------------------------

def is_guest(entry_id: EntryId) -> bool:
    return isinstance(entry_id, str) and entry_id.startswith(_GUEST_PREFIX)


def _ids(session: dict, list_name: str) -> list[EntryId]:
    return [entry_id for entry_id, _ in session.get(list_name, [])]


def _without(entries: list[Entry], entry_id: EntryId) -> list[Entry]:
    return [entry for entry in entries if entry[0] != entry_id]


def _has_room(session: dict, list_name: str, ignoring: Optional[EntryId] = None) -> bool:
    """True if list_name has a free spot (not counting `ignoring`, who is about to move)."""
    occupied = len(_without(session[list_name], ignoring))
    return occupied < session[_CAPACITY_KEY[list_name]]


def _is_maybe(session: dict, user_id: EntryId) -> bool:
    return user_id in session.get("maybe_ids", [])


def remove_everywhere(session: dict, entry_id: EntryId) -> None:
    """Removes an entry from every list and clears its maybe-flag."""
    for list_name in (MAIN, RESERVE, NOT_COMING):
        session[list_name] = _without(session.get(list_name, []), entry_id)
    session["maybe_ids"] = [uid for uid in session.get("maybe_ids", []) if uid != entry_id]


def promote_from_reserve(session: dict) -> list[Entry]:
    """
    Fills free main spots from the reserve, in order. People who chose "maybe"
    on purpose are skipped; they only move up by writing "هستم" themselves.
    Returns the promoted entries.
    """
    promoted = []
    while _has_room(session, MAIN):
        candidate = next(
            (entry for entry in session[RESERVE] if not _is_maybe(session, entry[0])), None
        )
        if candidate is None:
            break
        session[RESERVE].remove(candidate)
        session[MAIN].append(candidate)
        promoted.append(candidate)
    return promoted


# ---------------------------------------------------
# Attendance: "هستم" / "نیستم" / "شاید باشم"
# ---------------------------------------------------

def attend(session: dict, user_id: int, name: str) -> Attendance:
    if user_id in _ids(session, MAIN):
        return Attendance.UNCHANGED  # keep their place in the list
    if _has_room(session, MAIN):
        remove_everywhere(session, user_id)
        session[MAIN].append((user_id, name))
        return Attendance.JOINED_MAIN
    if user_id in _ids(session, RESERVE) and not _is_maybe(session, user_id):
        return Attendance.STILL_IN_RESERVE  # already waiting; keep their place
    if _has_room(session, RESERVE, ignoring=user_id):
        remove_everywhere(session, user_id)
        session[RESERVE].append((user_id, name))
        return Attendance.JOINED_RESERVE
    return Attendance.SESSION_FULL


def mark_not_coming(session: dict, user_id: int, name: str) -> Attendance:
    if user_id in _ids(session, NOT_COMING):
        return Attendance.UNCHANGED
    remove_everywhere(session, user_id)
    session[NOT_COMING].append((user_id, name))
    promote_from_reserve(session)
    return Attendance.MARKED_OUT


def mark_maybe(session: dict, user_id: int, name: str) -> Attendance:
    if user_id in _ids(session, RESERVE) and _is_maybe(session, user_id):
        return Attendance.UNCHANGED
    if not _has_room(session, RESERVE, ignoring=user_id):
        return Attendance.RESERVE_FULL
    remove_everywhere(session, user_id)
    session[RESERVE].append((user_id, name))
    session["maybe_ids"].append(user_id)
    promote_from_reserve(session)  # they may have freed a main spot
    return Attendance.MARKED_MAYBE


ATTENDANCE_ACTIONS = {
    "main": attend,
    "out": mark_not_coming,
    "maybe": mark_maybe,
}


# ---------------------------------------------------
# Guests (friends who aren't members of the group)
# ---------------------------------------------------

def add_guest(
    session: dict, chat_id: int, inviter_id: int, inviter_name: str, guest_name: str
) -> Optional[str]:
    """Adds a guest to main (or reserve if main is full). Returns the list name, or None if both are full."""
    target = next((name for name in (MAIN, RESERVE) if _has_room(session, name)), None)
    if target is None:
        return None

    session["guest_seq"] = session.get("guest_seq", 0) + 1
    guest_id = f"{_GUEST_PREFIX}{chat_id}:{session['guest_seq']}"
    session[target].append((guest_id, guest_name))
    session.setdefault("guest_owners", {})[guest_id] = {"user_id": inviter_id, "name": inviter_name}
    return target


def find_guest(session: dict, guest_name: str) -> Optional[Entry]:
    """Finds a guest in main or reserve by name (case-insensitive)."""
    wanted = guest_name.strip().lower()
    return next(
        (
            entry
            for entry in session[MAIN] + session[RESERVE]
            if is_guest(entry[0]) and entry[1].lower() == wanted
        ),
        None,
    )


def guest_inviter(session: dict, guest_id: str) -> Optional[dict]:
    """Returns {"user_id", "name"} of whoever invited the guest, if known."""
    return session.get("guest_owners", {}).get(guest_id)


def remove_guest(session: dict, guest_id: str) -> None:
    remove_everywhere(session, guest_id)
    session.get("guest_owners", {}).pop(guest_id, None)
    promote_from_reserve(session)


# ---------------------------------------------------
# Capacity changes (/editsession)
# ---------------------------------------------------

def apply_capacity_limits(session: dict) -> CapacityChanges:
    """
    Re-balances the lists after max_main / max_reserve changed:
    main overflow moves to the front of the reserve (or is dropped if it doesn't fit),
    reserve overflow is dropped, and free main spots are filled from the reserve.
    """
    changes = CapacityChanges()

    main_overflow = session[MAIN][session["max_main"]:]
    if main_overflow:
        session[MAIN] = session[MAIN][:session["max_main"]]
        room_in_reserve = max(session["max_reserve"] - len(session[RESERVE]), 0)
        changes.moved_to_reserve = main_overflow[:room_in_reserve]
        changes.dropped_from_main = main_overflow[room_in_reserve:]
        session[RESERVE] = changes.moved_to_reserve + session[RESERVE]

    changes.dropped_from_reserve = session[RESERVE][session["max_reserve"]:]
    session[RESERVE] = session[RESERVE][:session["max_reserve"]]

    changes.promoted = promote_from_reserve(session)
    _forget_dropped_entries(session)
    return changes


def _forget_dropped_entries(session: dict) -> None:
    """Clears guest owners and maybe-flags of entries that are no longer in main or reserve."""
    remaining = set(_ids(session, MAIN) + _ids(session, RESERVE))
    guest_owners = session.get("guest_owners", {})
    for guest_id in [gid for gid in guest_owners if gid not in remaining]:
        del guest_owners[guest_id]
    session["maybe_ids"] = [uid for uid in session.get("maybe_ids", []) if uid in remaining]
