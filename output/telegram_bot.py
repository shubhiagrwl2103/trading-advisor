"""
Telegram bot for the AI Investment Advisor.

Two responsibilities:
1. Push recommendations immediately when signals fire (called by claude_client.py)
2. Respond to /analyze, /portfolio, /signals commands

Usage:
  python -m output.telegram_bot          # starts the command listener
  from output.telegram_bot import send_recommendation   # for push calls
"""

import asyncio
import json
import logging
from typing import Optional

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from portfolio.aggregator import PortfolioSnapshot

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=TELEGRAM_BOT_TOKEN)
    return _bot


# ---------------------------------------------------------------------------
# Push notification (called by analysis pipeline)
# ---------------------------------------------------------------------------

async def send_recommendation(rec: dict, portfolio: PortfolioSnapshot) -> None:
    """Format and push a recommendation to the configured Telegram chat."""
    try:
        text = _format_recommendation(rec, portfolio)
        bot = _get_bot()
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"Telegram: recommendation sent for {rec.get('trigger_signal', {}).get('ticker')}")
    except Exception as e:
        logger.error(f"Telegram send_recommendation failed: {e}")


async def send_morning_digest(digest_text: str) -> None:
    """Push the morning digest."""
    bot = _get_bot()
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=digest_text,
        parse_mode=ParseMode.HTML,
    )


async def send_text(text: str) -> None:
    """Send arbitrary text to the configured chat."""
    bot = _get_bot()
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode=ParseMode.HTML)


def _format_recommendation(rec: dict, portfolio: PortfolioSnapshot) -> str:
    sig = rec.get("trigger_signal", {})
    r = rec.get("recommendation", {})
    port = rec.get("portfolio_at_analysis", {})

    ticker = sig.get("ticker", "?")
    signal_type = sig.get("signal_type", "?")
    timeframe = sig.get("timeframe", "?")
    indicator = sig.get("indicator", "?")
    close = sig.get("close", "?")
    confidence_raw = sig.get("luxalgo_confidence")
    confidence = f"{confidence_raw * 100:.0f}%" if confidence_raw else "N/A"

    action = r.get("current_action", "?")
    conviction = r.get("conviction", "?")
    risk = r.get("risk_rating", "?")
    size_pct = r.get("suggested_position_size_pct", "?")
    holding = r.get("estimated_holding_period", "?")
    entry = r.get("entry_zone", "?")
    target = r.get("target_zone", "?")
    stop = r.get("stop_loss_zone", "?")
    reasoning = r.get("reasoning", "")
    supporting = r.get("supporting_signals", [])
    portfolio_note = r.get("portfolio_note", "")
    urgency = rec.get("urgency", "standard")

    total_val = port.get("total_value_usd", portfolio.total_value_usd)
    weight = port.get("ticker_weight_pct", 0.0)

    urgency_prefix = {
        "immediate": "⚡️",
        "standard": "📊",
        "low": "💤",
    }.get(urgency, "📊")

    action_emoji = {
        "BUY": "🟢", "ADD": "🟢", "HOLD": "🟡",
        "WAIT": "🟡", "REDUCE": "🔴", "AVOID": "🔴",
    }.get(action, "⚪")

    lines = [
        f"{urgency_prefix} <b>[AI Advisor] {ticker} — {signal_type} Signal ({timeframe})</b>",
        "",
        f"{indicator} | Confidence: {confidence}",
        f"Price: ${close:,.2f}" if isinstance(close, (int, float)) else f"Price: {close}",
        "",
        f"{action_emoji} <b>Action: {action}</b> | Conviction: <b>{conviction}</b> | Risk: {risk}",
        f"Portfolio: <b>${total_val:,.0f}</b> | {ticker} weight: {weight:.1f}%",
        f"Suggested weight: {size_pct}%",
        "",
        f"Entry: {entry}",
        f"Target: {target}",
        f"Stop: {stop}",
        f"Holding: {holding}",
    ]

    if supporting:
        lines.append("")
        for s in supporting[:3]:
            lines.append(f"• {s}")

    if reasoning:
        lines.append("")
        lines.append(f"<i>{reasoning}</i>")

    if portfolio_note:
        lines.append("")
        lines.append(f"📁 {portfolio_note}")

    lines.append("")
    lines.append("<i>Suggestion only — not financial advice.</i>")

    return "\n".join(lines)


def _format_morning_digest(recommendations: list, portfolio: PortfolioSnapshot) -> str:
    from datetime import datetime
    today = datetime.now().strftime("%B %-d, %Y")

    lines = [
        f"☀️ <b>[AI Advisor] Morning — {today}</b>",
        "",
        f"Portfolio: <b>${portfolio.total_value_usd:,.0f}</b> (live Kraken + last Robinhood snapshot)",
        f"Signals last 24h: {len(recommendations)}",
        "",
    ]

    if not recommendations:
        lines.append("No signals in the last 24 hours.")
    else:
        for rec in recommendations[-5:]:  # show up to 5
            try:
                r = json.loads(rec["recommendation_json"]) if isinstance(rec["recommendation_json"], str) else rec["recommendation_json"]
                sig = r.get("trigger_signal", {})
                recommendation = r.get("recommendation", {})
                ticker = sig.get("ticker", rec.get("ticker", "?"))
                tf = sig.get("timeframe", "?")
                action = recommendation.get("current_action", "?")
                conviction = recommendation.get("conviction", "?")
                lines.append(f"• <b>{ticker} {tf}:</b> {action} — {conviction} conviction")
            except Exception:
                continue

    lines.extend([
        "",
        "/signals — view all   /portfolio — check holdings",
        "/analyze TICKER — manual analysis",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /analyze TICKER")
        return

    ticker = context.args[0].upper()
    await update.message.reply_text(f"Analyzing {ticker}... (this may take ~10 seconds)")

    try:
        from ai.claude_client import run_manual_analysis
        rec = await run_manual_analysis(ticker)
        if rec:
            await update.message.reply_text(
                f"Analysis complete. Check your latest recommendation above.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text("Analysis failed. Check logs.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        from portfolio.aggregator import get_live_portfolio
        port = get_live_portfolio()
        lines = [
            f"<b>Portfolio — ${port.total_value_usd:,.0f}</b>",
            f"Kraken (live): ${port.kraken_value_usd:,.0f}",
            f"Robinhood ({port.robinhood_snapshot_age_days or '?'} days old): ${port.robinhood_value_usd:,.0f}",
            "",
        ]
        for h in sorted(port.holdings, key=lambda x: x.value_usd, reverse=True)[:10]:
            lines.append(f"{h.symbol}: ${h.value_usd:,.0f} ({h.weight_pct:.1f}%)")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        from storage.queries import sync_get_recent_signals
        signals = sync_get_recent_signals(limit=10)
        if not signals:
            await update.message.reply_text("No signals received yet.")
            return
        lines = ["<b>Recent signals:</b>", ""]
        for s in signals:
            lines.append(
                f"[{s['received_at'][:16]}] {s['ticker']} {s.get('timeframe','?')} — "
                f"{s.get('signal_type','?')} via {s.get('indicator','?')}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


def run_bot() -> None:
    """Start the Telegram bot polling loop (blocking)."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("signals", cmd_signals))

    logger.info("Telegram bot starting...")
    app.run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
