"""
Scheduled background jobs.

- Daily 8:00 AM ET: Refresh Kraken balance snapshot
- Daily 9:00 AM ET: Morning digest → Telegram

Start with: python -m scheduler.jobs
Or call start_scheduler() from another entry point.
"""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import ANALYSIS_TIMEZONE

logger = logging.getLogger(__name__)


async def job_refresh_kraken() -> None:
    """Fetch live Kraken balances and store a snapshot."""
    logger.info("Running scheduled Kraken refresh...")
    try:
        from portfolio.kraken_portfolio import fetch_kraken_balances, fetch_crypto_prices
        from storage.database import get_db
        from storage.queries import save_kraken_snapshot

        balances = fetch_kraken_balances()
        prices = fetch_crypto_prices(list(balances.keys()))
        total = sum(balances.get(sym, 0) * prices.get(sym, 0) for sym in balances)
        snapshot = {
            "balances": balances,
            "prices": prices,
            "total_usd": total,
            "timestamp": datetime.utcnow().isoformat(),
        }
        async with await get_db() as db:
            await save_kraken_snapshot(db, snapshot, total)
        logger.info(f"Kraken snapshot saved: total=${total:,.2f}")
    except Exception as e:
        logger.error(f"Kraken refresh failed: {e}", exc_info=True)


async def job_morning_digest() -> None:
    """Send morning digest summary to Telegram."""
    logger.info("Running morning digest...")
    try:
        from storage.queries import sync_get_recent_recommendations
        from portfolio.aggregator import get_live_portfolio
        from output.telegram_bot import send_morning_digest, _format_morning_digest

        # Get last 24h recommendations
        recs = sync_get_recent_recommendations(limit=100)
        recent = [
            r for r in recs
            if (datetime.utcnow() - datetime.fromisoformat(r["generated_at"])).total_seconds() < 86400
        ]

        portfolio = get_live_portfolio()
        digest = _format_morning_digest(recent, portfolio)
        await send_morning_digest(digest)
        logger.info("Morning digest sent")
    except Exception as e:
        logger.error(f"Morning digest failed: {e}", exc_info=True)


def start_scheduler() -> AsyncIOScheduler:
    """Configure and start the APScheduler. Returns the scheduler instance."""
    scheduler = AsyncIOScheduler(timezone=ANALYSIS_TIMEZONE)

    scheduler.add_job(
        job_refresh_kraken,
        trigger=CronTrigger(hour=8, minute=0, timezone=ANALYSIS_TIMEZONE),
        id="kraken_refresh",
        name="Daily Kraken balance refresh",
        replace_existing=True,
    )

    scheduler.add_job(
        job_morning_digest,
        trigger=CronTrigger(hour=9, minute=0, timezone=ANALYSIS_TIMEZONE),
        id="morning_digest",
        name="Daily morning digest",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started (timezone: {ANALYSIS_TIMEZONE})")
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler = start_scheduler()
    asyncio.get_event_loop().run_forever()
