"""
Live Kraken portfolio — read-only API via ccxt.
Adapted from ~/kraken/kraken_fetch_data.py auth pattern.
"""

import logging
from typing import Dict

import ccxt

from config.settings import KRAKEN_API_KEY, KRAKEN_API_SECRET

logger = logging.getLogger(__name__)

# Symbols to skip (dust, internal Kraken tokens, etc.)
_SKIP_SYMBOLS = {"KFEE", "NFT"}

# Map Kraken internal names to standard symbols
_SYMBOL_MAP = {
    "XXBT": "BTC",
    "XETH": "ETH",
    "XLTC": "LTC",
    "XXLM": "XLM",
    "XXRP": "XRP",
    "ZEUR": "EUR",
    "ZUSD": "USD",
    "ZCAD": "CAD",
}


def _normalize(symbol: str) -> str:
    return _SYMBOL_MAP.get(symbol, symbol)


def _make_exchange() -> ccxt.kraken:
    return ccxt.kraken(
        {
            "apiKey": KRAKEN_API_KEY,
            "secret": KRAKEN_API_SECRET,
            "enableRateLimit": True,
        }
    )


def fetch_kraken_balances() -> Dict[str, float]:
    """
    Return {normalized_symbol: quantity} for all non-zero, non-fiat balances.
    Raises on API error.
    """
    exchange = _make_exchange()
    balance = exchange.fetch_balance()
    total = balance.get("total", {})

    result: Dict[str, float] = {}
    for raw_sym, qty in total.items():
        if qty is None or qty <= 0:
            continue
        sym = _normalize(raw_sym)
        if sym in _SKIP_SYMBOLS:
            continue
        # Skip fiat
        if sym in {"USD", "EUR", "GBP", "CAD", "JPY", "CHF"}:
            continue
        result[sym] = float(qty)

    logger.info(f"Kraken balances fetched: {result}")
    return result


def fetch_crypto_prices(symbols: list[str]) -> Dict[str, float]:
    """
    Fetch current USD prices for a list of crypto symbols via Kraken tickers.
    Returns {symbol: usd_price}. Missing symbols are omitted.
    """
    exchange = _make_exchange()
    prices: Dict[str, float] = {}

    for sym in symbols:
        pair = f"{sym}/USDT" if sym not in ("USDT",) else None
        if pair is None:
            continue
        # Try USDT pair first, then USD
        for quote in ("USDT", "USD"):
            try:
                ticker = exchange.fetch_ticker(f"{sym}/{quote}")
                prices[sym] = float(ticker["last"])
                break
            except Exception:
                continue

    return prices
