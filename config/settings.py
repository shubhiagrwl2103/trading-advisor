"""
Global settings loaded from .env file.
All configuration is read from environment variables — nothing hardcoded.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level up from config/)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


# Kraken (read-only API key)
KRAKEN_API_KEY: str = _require("KRAKEN_API_KEY")
KRAKEN_API_SECRET: str = _require("KRAKEN_API_SECRET")

# Anthropic
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
CLAUDE_MODEL: str = "claude-opus-4-6"

# Telegram
TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str = _require("TELEGRAM_CHAT_ID")

# Webhook security
WEBHOOK_SECRET_TOKEN: str = _require("WEBHOOK_SECRET_TOKEN")

# Storage
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(_ROOT / "advisor.db"))

# Timezone for digest scheduling
ANALYSIS_TIMEZONE: str = os.getenv("ANALYSIS_TIMEZONE", "America/New_York")

# Per-ticker cooldown: don't re-analyze same ticker within this many minutes
# (STRONG signals bypass this)
COOLDOWN_MINUTES: int = int(os.getenv("COOLDOWN_MINUTES", "120"))

# How many days before Robinhood snapshot is considered stale
ROBINHOOD_STALE_DAYS: int = int(os.getenv("ROBINHOOD_STALE_DAYS", "7"))
