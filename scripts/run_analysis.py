"""
Manual analysis trigger.

Usage:
    python -m scripts.run_analysis --ticker MSTR
    python -m scripts.run_analysis --ticker BTC --timeframe 1W --signal BUY --close 85000 --rsi 44.2
"""

import argparse
import asyncio
import json
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.json import JSON

console = Console()
logging.basicConfig(level=logging.INFO)


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI Advisor manual analysis trigger")
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g. MSTR, BTC)")
    parser.add_argument("--timeframe", default=None, help="Timeframe (e.g. 1D, 1W)")
    parser.add_argument("--signal", default="MANUAL", help="Signal type (BUY, SELL, etc.)")
    parser.add_argument("--close", type=float, default=None, help="Current close price")
    parser.add_argument("--rsi", type=float, default=None, help="RSI 14 value")
    parser.add_argument("--ema50", type=float, default=None, help="EMA 50 value")
    parser.add_argument("--ema200", type=float, default=None, help="EMA 200 value")
    parser.add_argument("--macd_hist", type=float, default=None, help="MACD histogram")
    parser.add_argument("--lux_conf", type=float, default=None, help="LuxAlgo confidence (0.0-1.0)")
    args = parser.parse_args()

    from storage.database import init_db_sync
    init_db_sync()

    from webhooks.models import TradingViewSignal
    from ai.claude_client import run_analysis

    signal = TradingViewSignal(
        ticker=args.ticker.upper(),
        timeframe=args.timeframe,
        signal_type=args.signal.upper(),
        close=args.close,
        rsi_14=args.rsi,
        ema_50=args.ema50,
        ema_200=args.ema200,
        macd_histogram=args.macd_hist,
        luxalgo_confidence=args.lux_conf,
        indicator="manual",
    )

    console.print(f"\n[bold blue]Analyzing {args.ticker.upper()}...[/bold blue]")

    rec = await run_analysis(signal, signal_id=None, trigger_type="manual")

    if rec:
        console.print("\n[bold green]Recommendation:[/bold green]")
        console.print(JSON(json.dumps(rec, indent=2)))
    else:
        console.print("[bold red]Analysis failed — check logs above.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
