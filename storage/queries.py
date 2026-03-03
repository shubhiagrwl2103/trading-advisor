"""
Read/write helpers for all SQLite tables.
All async — for use inside FastAPI background tasks and the scheduler.
Sync wrappers are provided for Streamlit (which is not async).
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from config.settings import DATABASE_PATH


# ---------------------------------------------------------------------------
# Synchronous helpers (used by Streamlit)
# ---------------------------------------------------------------------------

def _sync_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sync_get_recent_signals(limit: int = 50) -> List[Dict]:
    with _sync_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tv_signals ORDER BY received_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def sync_get_recent_recommendations(limit: int = 50) -> List[Dict]:
    with _sync_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM recommendations ORDER BY generated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def sync_get_latest_robinhood_snapshot() -> Optional[Dict]:
    with _sync_conn() as conn:
        row = conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE source='robinhood_csv' ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def sync_mark_acted_on(rec_id: int, acted: bool = True) -> None:
    with _sync_conn() as conn:
        conn.execute(
            "UPDATE recommendations SET acted_on=? WHERE id=?",
            (1 if acted else 0, rec_id),
        )
        conn.commit()


def sync_save_robinhood_snapshot(snapshot_json: Dict, total_value: float) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with _sync_conn() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (timestamp, source, total_value_usd, snapshot_json) VALUES (?,?,?,?)",
            (ts, "robinhood_csv", total_value, json.dumps(snapshot_json)),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Async helpers (used by FastAPI + scheduler)
# ---------------------------------------------------------------------------

async def save_signal(db: aiosqlite.Connection, signal: Dict[str, Any]) -> int:
    """Insert a tv_signal row and return its new ID."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        """
        INSERT INTO tv_signals (
            received_at, ticker, exchange, timeframe, close_price,
            signal_type, indicator,
            rsi_14, macd_line, macd_signal_line, macd_histogram,
            ema_50, ema_200, bb_upper, bb_lower, bb_position,
            luxalgo_signal, luxalgo_confidence, volume, raw_payload
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            now,
            signal.get("ticker"),
            signal.get("exchange"),
            signal.get("timeframe"),
            signal.get("close"),
            signal.get("signal_type"),
            signal.get("indicator"),
            signal.get("rsi_14"),
            signal.get("macd_line"),
            signal.get("macd_signal"),
            signal.get("macd_histogram"),
            signal.get("ema_50"),
            signal.get("ema_200"),
            signal.get("bb_upper"),
            signal.get("bb_lower"),
            signal.get("bb_position"),
            signal.get("luxalgo_signal"),
            signal.get("luxalgo_confidence"),
            signal.get("volume"),
            json.dumps(signal),
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def save_recommendation(
    db: aiosqlite.Connection,
    ticker: str,
    rec_json: Dict,
    trigger_signal_id: Optional[int],
    trigger_type: str,
    portfolio_value: float,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        """
        INSERT INTO recommendations (
            generated_at, trigger_signal_id, trigger_type, ticker,
            portfolio_value_at_time, recommendation_json, model,
            input_tokens, output_tokens
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            now,
            trigger_signal_id,
            trigger_type,
            ticker,
            portfolio_value,
            json.dumps(rec_json),
            model,
            input_tokens,
            output_tokens,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def get_recent_signals_for_ticker(
    db: aiosqlite.Connection, ticker: str, limit: int = 10
) -> List[Dict]:
    async with db.execute(
        "SELECT * FROM tv_signals WHERE ticker=? ORDER BY received_at DESC LIMIT ?",
        (ticker, limit),
    ) as cursor:
        rows = await cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


async def get_last_signal_time(db: aiosqlite.Connection, ticker: str) -> Optional[str]:
    """Return ISO timestamp of the most recent signal for this ticker."""
    async with db.execute(
        "SELECT received_at FROM tv_signals WHERE ticker=? ORDER BY received_at DESC LIMIT 1",
        (ticker,),
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row else None


async def save_kraken_snapshot(db: aiosqlite.Connection, snapshot: Dict, total_value: float) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO portfolio_snapshots (timestamp, source, total_value_usd, snapshot_json) VALUES (?,?,?,?)",
        (ts, "kraken_live", total_value, json.dumps(snapshot)),
    )
    await db.commit()


async def get_latest_robinhood_snapshot(db: aiosqlite.Connection) -> Optional[Dict]:
    async with db.execute(
        "SELECT * FROM portfolio_snapshots WHERE source='robinhood_csv' ORDER BY timestamp DESC LIMIT 1"
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))
