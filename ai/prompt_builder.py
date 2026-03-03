"""
Builds the system prompt and user prompt for Claude.
All indicator values come from the incoming TradingView signal.
No local TA computation.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from config.settings import ROBINHOOD_STALE_DAYS
from portfolio.aggregator import PortfolioSnapshot, holding_for_ticker
from webhooks.models import TradingViewSignal

SYSTEM_PROMPT = """You are an expert AI investment advisor providing event-driven trade recommendations.

IMPORTANT RULES:
1. You NEVER execute trades — you provide suggestions only. The user decides manually.
2. You have NO timeframe bias. Holding period can be days, weeks, or months. Let the signal quality and timeframe determine it.
3. Always cite the EXACT indicator values from the signal payload. Do not approximate.
4. Always consider current portfolio weight before suggesting position changes.
5. Flag when the Robinhood snapshot is stale (>7 days old) — use "STALE DATA" note.
6. If key indicator data is missing from the signal, say so explicitly in your reasoning.
7. Consider convergence: multiple confirming signals strengthen conviction. Divergence lowers it.
8. Risk rating must reflect asset volatility (crypto is inherently higher risk than stocks).

OUTPUT FORMAT: Respond ONLY with valid JSON matching the schema exactly. No markdown, no prose, no explanation outside the JSON.

JSON SCHEMA:
{
  "analysis_date": "<ISO 8601>",
  "trigger_signal": {
    "ticker": "<string>",
    "indicator": "<string>",
    "signal_type": "<string>",
    "timeframe": "<string>",
    "close": <number or null>
  },
  "portfolio_at_analysis": {
    "total_value_usd": <number>,
    "ticker_weight_pct": <number>,
    "ticker_value_usd": <number>
  },
  "recommendation": {
    "symbol": "<string>",
    "asset_type": "<crypto|stock|etf>",
    "current_action": "<HOLD|BUY|ADD|REDUCE|AVOID|WAIT>",
    "conviction": "<HIGH|MEDIUM|LOW>",
    "risk_rating": "<HIGH|MEDIUM|LOW>",
    "suggested_position_size_pct": <number>,
    "change_direction": "<increase|decrease|maintain|avoid>",
    "estimated_holding_period": "<string — e.g. '3-5 days', '2-4 weeks', '1-3 months'>",
    "entry_zone": "<string>",
    "target_zone": "<string>",
    "stop_loss_zone": "<string>",
    "reasoning": "<3-4 sentences citing specific indicator values>",
    "supporting_signals": ["<string>", ...],
    "conflicting_signals": ["<string>", ...],
    "signal_history_note": "<string>",
    "portfolio_note": "<string>"
  },
  "urgency": "<immediate|standard|low>",
  "confidence_disclaimer": "Suggestion only. Always do your own research."
}"""


def build_user_prompt(
    signal: TradingViewSignal,
    portfolio: PortfolioSnapshot,
    signal_history: list,
    asset_type: str,
) -> str:
    """Build the user-turn prompt with all live context."""

    now = datetime.now(timezone.utc).isoformat()

    # --- Signal section ---
    signal_data = {k: v for k, v in signal.model_dump().items() if v is not None}

    # --- Portfolio section ---
    holding = holding_for_ticker(portfolio, signal.ticker)
    ticker_weight = holding.weight_pct if holding else 0.0
    ticker_value = holding.value_usd if holding else 0.0
    ticker_qty = holding.quantity if holding else 0.0
    ticker_price = holding.price_usd if holding else signal.close

    # Robinhood staleness warning
    rh_note = ""
    if portfolio.robinhood_stale and portfolio.robinhood_snapshot_age_days:
        rh_note = (
            f"\n⚠️ ROBINHOOD SNAPSHOT IS {portfolio.robinhood_snapshot_age_days:.0f} DAYS OLD — "
            f"stock positions may be outdated. Crypto (Kraken) is live."
        )

    # All holdings summary
    holdings_summary = []
    for h in sorted(portfolio.holdings, key=lambda x: x.value_usd, reverse=True):
        holdings_summary.append(
            f"  {h.symbol}: {h.quantity:.4f} units @ ${h.price_usd:,.2f} = ${h.value_usd:,.2f} ({h.weight_pct:.1f}%)"
        )

    # --- Signal history ---
    history_lines = []
    for row in signal_history[:10]:
        history_lines.append(
            f"  [{row.get('received_at', '?')[:10]}] {row.get('signal_type', '?')} "
            f"via {row.get('indicator', '?')} @ ${row.get('close_price', '?')}"
        )

    prompt = f"""CURRENT DATE/TIME: {now}

=== INCOMING SIGNAL ===
{json.dumps(signal_data, indent=2)}

=== LIVE PORTFOLIO ===
Total portfolio value: ${portfolio.total_value_usd:,.2f}
  Kraken (live): ${portfolio.kraken_value_usd:,.2f}
  Robinhood (snapshot, {portfolio.robinhood_snapshot_age_days or 'unknown'} days old): ${portfolio.robinhood_value_usd:,.2f}
{rh_note}

Current holding in {signal.ticker}:
  Quantity: {ticker_qty:,.4f}
  Price: ${ticker_price:,.2f}
  Value: ${ticker_value:,.2f}
  Portfolio weight: {ticker_weight:.2f}%

Full holdings (sorted by value):
{chr(10).join(holdings_summary) if holdings_summary else "  (no holdings data)"}

Asset type: {asset_type}

=== RECENT SIGNAL HISTORY FOR {signal.ticker} (last 10) ===
{chr(10).join(history_lines) if history_lines else "  No previous signals for this ticker."}

=== YOUR TASK ===
Analyze this signal in the context of the live portfolio and produce a JSON recommendation.
- Cite exact indicator values from the signal
- Consider the current {ticker_weight:.1f}% portfolio weight
- Determine holding period from the signal timeframe and setup quality — no restriction
- If data is missing, state it clearly in reasoning
- Respond ONLY with valid JSON
"""
    return prompt
