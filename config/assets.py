"""
Asset type mappings.
Used to tell Claude whether a symbol is crypto, stock, or ETF.
"""

from typing import Dict, Set

CRYPTO_SYMBOLS: Set[str] = {
    "BTC", "ETH", "SOL", "XRP", "ADA", "DOT", "LINK", "AVAX", "MATIC",
    "BTC/USD", "ETH/USD", "SOL/USD",
    "XBTUSD", "ETHUSD", "XXBTZUSD", "XETHZUSD",
}

ETF_SYMBOLS: Set[str] = {
    "IBIT", "FBTC", "GBTC", "BITO", "BITB",
    "SPY", "QQQ", "IWM", "GLD", "SLV",
}

STOCK_SYMBOLS: Set[str] = {
    "MSTR", "COIN", "HOOD", "TSLA", "NVDA", "AMD", "MSFT", "AAPL",
    "META", "GOOGL", "AMZN", "RIOT", "MARA", "CLSK",
}

# Fallback mapping for ambiguous tickers
_EXPLICIT: Dict[str, str] = {
    "BTC": "crypto",
    "ETH": "crypto",
    "MSTR": "stock",
    "COIN": "stock",
    "HOOD": "stock",
    "TSLA": "stock",
    "IBIT": "etf",
    "GBTC": "etf",
}


def get_asset_type(ticker: str) -> str:
    """
    Return 'crypto', 'etf', or 'stock' for the given ticker.
    Defaults to 'stock' if unknown.
    """
    upper = ticker.upper().replace("-", "/")

    if upper in _EXPLICIT:
        return _EXPLICIT[upper]

    if upper in CRYPTO_SYMBOLS:
        return "crypto"
    if upper in ETF_SYMBOLS:
        return "etf"
    if upper in STOCK_SYMBOLS:
        return "stock"

    # Heuristic: Kraken crypto pairs contain "/" or are all-caps short codes
    if "/" in upper or len(upper) <= 4 and upper.isalpha():
        return "crypto"

    return "stock"
