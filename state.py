"""
state.py - The bot's in-memory state (sessions + aliases), kept in sync with db.py.

Handlers talk only to BotState; they never call the database directly. That way
the storage strategy can change without touching any Telegram code.
"""

from typing import Optional

import db
from session_model import EntryId, guest_inviter, is_guest


class BotState:
    def __init__(self):
        self._sessions: dict[int, dict] = {}
        # aliases[chat_id][user_id] = {"self": str|None, "admin": str|None}
        self._aliases: dict[int, dict[int, dict]] = {}

    async def load(self) -> None:
        """Creates the database if needed and loads everything into memory."""
        await db.init_db()
        self._sessions.update(await db.load_all_sessions())
        self._aliases.update(await db.load_all_aliases())

    @property
    def sessions(self) -> dict[int, dict]:
        return self._sessions

    @property
    def alias_chat_count(self) -> int:
        return len(self._aliases)

    # ---------------- Sessions ----------------

    def session(self, chat_id: int) -> Optional[dict]:
        return self._sessions.get(chat_id)

    async def start_session(self, chat_id: int, session: dict) -> None:
        self._sessions[chat_id] = session
        await self.save_session(chat_id)

    async def save_session(self, chat_id: int) -> None:
        session = self._sessions.get(chat_id)
        if session is None:
            await db.delete_session(chat_id)
        else:
            await db.save_session(chat_id, session)

    async def close_session(self, chat_id: int) -> Optional[dict]:
        """Removes and returns the chat's session (None if there wasn't one)."""
        session = self._sessions.pop(chat_id, None)
        if session is not None:
            await db.delete_session(chat_id)
        return session

    # ---------------- Aliases ----------------

    def display_name(self, chat_id: int, user_id: int, fallback: str) -> str:
        """Admin alias > self alias > real name."""
        entry = self._aliases.get(chat_id, {}).get(user_id) or {}
        return entry.get("admin") or entry.get("self") or fallback

    def entry_label(self, chat_id: int, session: dict, entry_id: EntryId, name: str) -> str:
        """Display text for a list entry; guests also show who invited them."""
        if not is_guest(entry_id):
            return self.display_name(chat_id, entry_id, name)
        inviter = guest_inviter(session, entry_id)
        if not inviter:
            return name
        return f"{name}({self.display_name(chat_id, inviter['user_id'], inviter['name'])})"

    def labeler(self, chat_id: int, session: dict):
        """entry_label bound to one chat/session, for texts.py layouts."""
        return lambda entry_id, name: self.entry_label(chat_id, session, entry_id, name)

    def admin_alias(self, chat_id: int, user_id: int) -> Optional[str]:
        return self._aliases.get(chat_id, {}).get(user_id, {}).get("admin")

    async def set_alias(self, chat_id: int, user_id: int, kind: str, alias: Optional[str]) -> None:
        """Sets the "self" or "admin" alias of a user (None clears it) and persists the chat."""
        chat_aliases = self._aliases.setdefault(chat_id, {})
        chat_aliases.setdefault(user_id, {"self": None, "admin": None})[kind] = alias
        await db.save_aliases_for_chat(chat_id, chat_aliases)


_STATE_KEY = "state"


def attach(application, state: BotState) -> None:
    """Stores the state on the Application so handlers and jobs can reach it."""
    application.bot_data[_STATE_KEY] = state


def from_context(context) -> BotState:
    return context.application.bot_data[_STATE_KEY]
