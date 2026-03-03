"""
SQLite database initialization and schema management.
"""

import aiosqlite
import sqlite3
from config.settings import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    total_value_usd REAL,
    snapshot_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tv_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    ticker TEXT NOT NULL,
    exchange TEXT,
    timeframe TEXT,
    close_price REAL,
    signal_type TEXT,
    indicator TEXT,
    rsi_14 REAL,
    macd_line REAL,
    macd_signal_line REAL,
    macd_histogram REAL,
    ema_50 REAL,
    ema_200 REAL,
    bb_upper REAL,
    bb_lower REAL,
    bb_position REAL,
    luxalgo_signal TEXT,
    luxalgo_confidence REAL,
    volume REAL,
    raw_payload TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    trigger_signal_id INTEGER,
    trigger_type TEXT,
    ticker TEXT NOT NULL,
    portfolio_value_at_time REAL,
    recommendation_json TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    acted_on INTEGER DEFAULT 0,
    FOREIGN KEY (trigger_signal_id) REFERENCES tv_signals(id)
);

CREATE INDEX IF NOT EXISTS idx_signals_ticker ON tv_signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_received ON tv_signals(received_at);
CREATE INDEX IF NOT EXISTS idx_recs_ticker ON recommendations(ticker);
CREATE INDEX IF NOT EXISTS idx_recs_generated ON recommendations(generated_at);
"""


def init_db_sync() -> None:
    """Synchronous init — call once at startup."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


async def init_db() -> None:
    """Async init — idempotent, safe to call every startup."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Open a fresh async DB connection (caller must close)."""
    return await aiosqlite.connect(DATABASE_PATH)
