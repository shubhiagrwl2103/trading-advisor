"""
Anthropic API client.
Model: claude-opus-4-6
Handles the full analysis pipeline: portfolio → prompt → Claude → parse → store → notify.
"""

import asyncio
import logging
from typing import Optional

import anthropic

from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL
from config.assets import get_asset_type
from portfolio.aggregator import get_live_portfolio
from ai.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from ai.recommendation_parser import parse_recommendation
from storage.database import get_db
from storage.queries import save_recommendation, get_recent_signals_for_ticker
from webhooks.models import TradingViewSignal

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def run_analysis(
    signal: TradingViewSignal,
    signal_id: Optional[int],
    trigger_type: str = "webhook",
) -> Optional[dict]:
    """
    Full analysis pipeline:
    1. Fetch live portfolio
    2. Load signal history
    3. Build prompt
    4. Call Claude
    5. Parse response
    6. Store recommendation
    7. Send Telegram notification

    Returns the parsed recommendation dict, or None on failure.
    """
    ticker = signal.ticker.upper()
    asset_type = get_asset_type(ticker)

    # ----------------------------------------------------------------
    # 1. Live portfolio
    # ----------------------------------------------------------------
    portfolio = await asyncio.to_thread(get_live_portfolio, signal.model_dump())

    # ----------------------------------------------------------------
    # 2. Signal history
    # ----------------------------------------------------------------
    async with await get_db() as db:
        signal_history = await get_recent_signals_for_ticker(db, ticker, limit=10)

    # ----------------------------------------------------------------
    # 3. Build prompt
    # ----------------------------------------------------------------
    user_prompt = build_user_prompt(signal, portfolio, signal_history, asset_type)

    logger.info(f"Sending {ticker} analysis to Claude ({CLAUDE_MODEL})...")

    # ----------------------------------------------------------------
    # 4. Call Claude (sync SDK wrapped in thread)
    # ----------------------------------------------------------------
    try:
        response = await asyncio.to_thread(
            _client.messages.create,
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as e:
        logger.error(f"Claude API call failed: {e}", exc_info=True)
        return None

    raw_text = response.content[0].text if response.content else ""
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    logger.info(f"Claude response: {input_tokens} in / {output_tokens} out tokens")

    # ----------------------------------------------------------------
    # 5. Parse
    # ----------------------------------------------------------------
    rec, error = parse_recommendation(raw_text)
    if error or rec is None:
        logger.error(f"Failed to parse Claude response: {error}\nRaw: {raw_text[:500]}")
        return None

    # ----------------------------------------------------------------
    # 6. Store
    # ----------------------------------------------------------------
    async with await get_db() as db:
        rec_id = await save_recommendation(
            db=db,
            ticker=ticker,
            rec_json=rec,
            trigger_signal_id=signal_id,
            trigger_type=trigger_type,
            portfolio_value=portfolio.total_value_usd,
            model=CLAUDE_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    logger.info(f"Recommendation stored: id={rec_id}")

    # ----------------------------------------------------------------
    # 7. Telegram push
    # ----------------------------------------------------------------
    try:
        from output.telegram_bot import send_recommendation
        await send_recommendation(rec, portfolio)
    except Exception as e:
        logger.error(f"Telegram push failed: {e}")

    return rec


async def run_manual_analysis(ticker: str) -> Optional[dict]:
    """
    Trigger analysis for a ticker without an incoming signal.
    Used by scripts/run_analysis.py and the Telegram /analyze command.
    """
    # Build a minimal signal with just the ticker
    signal = TradingViewSignal(ticker=ticker, signal_type="MANUAL")
    return await run_analysis(signal, signal_id=None, trigger_type="manual")
