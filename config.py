"""
config.py - Runtime configuration: the bot token and the local clock.

Kept separate so that secrets and environment concerns never leak into the
business logic, and so they can be swapped (e.g. in tests) in one place.
"""

from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo

    TEHRAN_TZ = ZoneInfo("Asia/Tehran")
except Exception:  # pragma: no cover - fallback if tzdata isn't installed
    TEHRAN_TZ = None

TOKEN_FILE = Path(__file__).resolve().parent / "token-file.txt"


class ConfigError(RuntimeError):
    """Raised when the bot can't start because its configuration is missing or invalid."""


def load_bot_token(token_file: Path = TOKEN_FILE) -> str:
    """Reads the Telegram bot token from token_file (first non-empty line)."""
    if not token_file.is_file():
        raise ConfigError(
            f"Token file not found: {token_file}\n"
            "Create it and put your bot token (from @BotFather) on its first line."
        )

    lines = [line.strip() for line in token_file.read_text(encoding="utf-8").splitlines()]
    token = next((line for line in lines if line), "")
    if not token:
        raise ConfigError(f"Token file is empty: {token_file}")
    return token


def now() -> datetime:
    """Current time in Tehran (or naive local time if tzdata is unavailable)."""
    return datetime.now(TEHRAN_TZ) if TEHRAN_TZ else datetime.now()
