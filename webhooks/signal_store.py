"""
Persists incoming signals and triggers the analysis pipeline.
Runs in a FastAPI background task so the webhook returns 200 immediately.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from config.settings import COOLDOWN_MINUTES
from storage.database import get_db
from storage.queries import save_signal, get_last_signal_time
from webhooks.models import TradingViewSignal, signal_is_meaningful, is_strong_signal

logger = logging.getLogger(__name__)


async def process_signal(signal: TradingViewSignal) -> None:
    """
    Entry point called by the webhook server.
    1. Validate signal has meaningful TA data
    2. Check cooldown
    3. Store in SQLite
    4. Trigger analysis pipeline
    """
    if not signal_is_meaningful(signal):
        logger.warning(f"Skipping signal for {signal.ticker}: no TA data present")
        return

    async with await get_db() as db:
        # ------------------------------------------------------------------
        # Cooldown check (bypass for STRONG signals)
        # ------------------------------------------------------------------
        strong = is_strong_signal(signal)
        if not strong:
            last_ts = await get_last_signal_time(db, signal.ticker)
            if last_ts:
                try:
                    last_dt = datetime.fromisoformat(last_ts)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
                    if elapsed < COOLDOWN_MINUTES:
                        logger.info(
                            f"Cooldown active for {signal.ticker}: "
                            f"{elapsed:.0f}m elapsed, need {COOLDOWN_MINUTES}m"
                        )
                        # Still store the signal for history, but don't trigger analysis
                        await save_signal(db, signal.model_dump())
                        return
                except Exception as e:
                    logger.warning(f"Cooldown check failed: {e}")

        # ------------------------------------------------------------------
        # Persist signal
        # ------------------------------------------------------------------
        signal_id = await save_signal(db, signal.model_dump())
        logger.info(f"Signal stored: id={signal_id} ticker={signal.ticker} type={signal.signal_type}")

    # ------------------------------------------------------------------
    # Trigger analysis in a separate task to avoid blocking
    # ------------------------------------------------------------------
    # Import here to avoid circular imports at module load time
    from ai.claude_client import run_analysis
    asyncio.create_task(_run_analysis_safe(signal, signal_id))


async def _run_analysis_safe(signal: TradingViewSignal, signal_id: int) -> None:
    """Wrapper that catches and logs any analysis errors."""
    try:
        from ai.claude_client import run_analysis
        await run_analysis(signal, signal_id, trigger_type="webhook")
    except Exception as e:
        logger.error(f"Analysis pipeline failed for signal {signal_id}: {e}", exc_info=True)
