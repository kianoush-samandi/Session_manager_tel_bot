"""
db.py - Persistent storage layer (SQLite) for the bot.

Each chat's session and each chat's alias collection is stored as one JSON
record (not a normalized schema). This keeps the in-memory structures simple
and makes this module a thin save/load layer with no business rules.
"""

import json
import logging

import aiosqlite

DB_PATH = "bot_data.db"

logger = logging.getLogger(__name__)

_TABLES = ("sessions", "aliases")
# JSON turns tuples into lists; these session lists hold (id, name) tuples.
_ENTRY_LISTS = ("main", "reserve", "not_coming")


async def init_db(db_path: str = DB_PATH):
    """Creates the tables if they don't exist. Must be called once at startup."""
    async with aiosqlite.connect(db_path) as db:
        for table in _TABLES:
            await db.execute(
                f"CREATE TABLE IF NOT EXISTS {table} (chat_id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
            )
        await db.commit()
    logger.info("Database initialized at %s", db_path)


async def _upsert(table: str, chat_id: int, data, db_path: str):
    payload = json.dumps(data, ensure_ascii=False)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT INTO {table} (chat_id, data) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET data = excluded.data
            """,
            (chat_id, payload),
        )
        await db.commit()


async def _load_all(table: str, db_path: str) -> dict:
    """Returns {chat_id: decoded_json} for every row of table."""
    rows = {}
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(f"SELECT chat_id, data FROM {table}") as cursor:
            async for chat_id, data in cursor:
                rows[chat_id] = json.loads(data)
    return rows


# ---------------------------------------------------
# Sessions
# ---------------------------------------------------

async def save_session(chat_id: int, session: dict, db_path: str = DB_PATH):
    """Saves or fully replaces one chat's session."""
    await _upsert("sessions", chat_id, session, db_path)


async def delete_session(chat_id: int, db_path: str = DB_PATH):
    """Deletes a chat's session (e.g. on /cancelsession)."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def load_all_sessions(db_path: str = DB_PATH) -> dict:
    """Returns {chat_id: session}, with (id, name) entries restored as tuples."""
    sessions = await _load_all("sessions", db_path)
    for session in sessions.values():
        for list_name in _ENTRY_LISTS:
            session[list_name] = [tuple(entry) for entry in session.get(list_name, [])]
    return sessions


# ---------------------------------------------------
# Aliases
# ---------------------------------------------------

async def save_aliases_for_chat(chat_id: int, chat_aliases: dict, db_path: str = DB_PATH):
    """Saves one chat's {user_id: {"self":..., "admin":...}} (JSON keys must be str)."""
    await _upsert("aliases", chat_id, {str(uid): entry for uid, entry in chat_aliases.items()}, db_path)


async def load_all_aliases(db_path: str = DB_PATH) -> dict:
    """Returns {chat_id: {user_id: {"self":..., "admin":...}}}."""
    rows = await _load_all("aliases", db_path)
    return {chat_id: {int(uid): entry for uid, entry in raw.items()} for chat_id, raw in rows.items()}
