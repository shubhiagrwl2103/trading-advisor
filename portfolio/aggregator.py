"""
Live portfolio aggregator.

get_live_portfolio() always returns the current state:
  - Kraken crypto balances: fetched live from the API
  - Robinhood stocks: loaded from the latest CSV snapshot in SQLite
  - Total value: computed dynamically from current prices
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from portfolio.kraken_portfolio import fetch_kraken_balances, fetch_crypto_prices
from storage.queries import sync_get_latest_robinhood_snapshot

logger = logging.getLogger(__name__)


@dataclass
class Holding:
    symbol: str
    name: str
    asset_type: str          # "crypto" | "stock" | "etf"
    quantity: float
    price_usd: float
    value_usd: float
    weight_pct: float        # % of total portfolio


@dataclass
class PortfolioSnapshot:
    timestamp: str
    total_value_usd: float
    holdings: List[Holding] = field(default_factory=list)
    kraken_value_usd: float = 0.0
    robinhood_value_usd: float = 0.0
    robinhood_snapshot_age_days: Optional[float] = None
    robinhood_stale: bool = False


def get_live_portfolio(incoming_signal: Optional[Dict] = None) -> PortfolioSnapshot:
    """
    Build a fully live PortfolioSnapshot.

    If `incoming_signal` is provided, its close price is used for that ticker
    so prices are maximally current.

    Returns a PortfolioSnapshot with all holdings valued at live prices.
    """
    now = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # 1. Kraken live balances
    # ------------------------------------------------------------------
    kraken_balances: Dict[str, float] = {}
    try:
        kraken_balances = fetch_kraken_balances()
    except Exception as e:
        logger.error(f"Kraken balance fetch failed: {e}")

    # ------------------------------------------------------------------
    # 2. Robinhood snapshot from SQLite
    # ------------------------------------------------------------------
    robinhood_holdings: List[Dict] = []
    robinhood_snapshot_age_days: Optional[float] = None
    robinhood_stale = False

    rh_row = sync_get_latest_robinhood_snapshot()
    if rh_row:
        try:
            snapshot_data = json.loads(rh_row["snapshot_json"])
            robinhood_holdings = snapshot_data.get("holdings", [])

            upload_ts = datetime.fromisoformat(
                snapshot_data.get("upload_timestamp", rh_row["timestamp"])
            )
            age = (datetime.now(timezone.utc) - upload_ts).total_seconds() / 86400
            robinhood_snapshot_age_days = round(age, 1)
            robinhood_stale = age > 7
        except Exception as e:
            logger.error(f"Failed to parse Robinhood snapshot: {e}")

    # ------------------------------------------------------------------
    # 3. Fetch live prices for crypto
    # ------------------------------------------------------------------
    crypto_prices: Dict[str, float] = {}
    if kraken_balances:
        try:
            crypto_prices = fetch_crypto_prices(list(kraken_balances.keys()))
        except Exception as e:
            logger.error(f"Price fetch failed: {e}")

    # Override with incoming signal price if available
    if incoming_signal and incoming_signal.get("ticker") and incoming_signal.get("close"):
        ticker = incoming_signal["ticker"].upper()
        price = float(incoming_signal["close"])
        crypto_prices[ticker] = price

    # ------------------------------------------------------------------
    # 4. Build holdings list
    # ------------------------------------------------------------------
    holdings: List[Holding] = []
    kraken_value = 0.0

    for sym, qty in kraken_balances.items():
        price = crypto_prices.get(sym, 0.0)
        value = qty * price
        kraken_value += value
        holdings.append(
            Holding(
                symbol=sym,
                name=sym,
                asset_type="crypto",
                quantity=qty,
                price_usd=price,
                value_usd=value,
                weight_pct=0.0,  # computed below
            )
        )

    robinhood_value = 0.0
    for h in robinhood_holdings:
        sym = h.get("symbol", "")
        qty = float(h.get("quantity", 0))
        equity = float(h.get("equity_usd", 0))
        # equity from CSV is a live snapshot value; derive price
        price = equity / qty if qty > 0 else 0.0

        # If incoming signal matches this ticker, use its close price
        if incoming_signal and incoming_signal.get("ticker", "").upper() == sym.upper():
            price = float(incoming_signal.get("close", price))
            equity = qty * price

        robinhood_value += equity
        holdings.append(
            Holding(
                symbol=sym,
                name=h.get("name", sym),
                asset_type=_guess_asset_type(sym),
                quantity=qty,
                price_usd=price,
                value_usd=equity,
                weight_pct=0.0,
            )
        )

    total = kraken_value + robinhood_value

    # Compute weights
    for h in holdings:
        h.weight_pct = round((h.value_usd / total * 100) if total > 0 else 0.0, 2)

    snapshot = PortfolioSnapshot(
        timestamp=now,
        total_value_usd=round(total, 2),
        holdings=holdings,
        kraken_value_usd=round(kraken_value, 2),
        robinhood_value_usd=round(robinhood_value, 2),
        robinhood_snapshot_age_days=robinhood_snapshot_age_days,
        robinhood_stale=robinhood_stale,
    )

    logger.info(
        f"Portfolio snapshot: total=${total:,.2f} "
        f"(Kraken ${kraken_value:,.2f} + Robinhood ${robinhood_value:,.2f})"
    )
    return snapshot


def _guess_asset_type(sym: str) -> str:
    """Lightweight local guess without importing settings to avoid circular deps."""
    ETFs = {"IBIT", "FBTC", "GBTC", "BITO", "SPY", "QQQ", "GLD"}
    if sym.upper() in ETFs:
        return "etf"
    return "stock"


def holding_for_ticker(snapshot: PortfolioSnapshot, ticker: str) -> Optional[Holding]:
    """Return the Holding for a given ticker, or None if not held."""
    upper = ticker.upper()
    for h in snapshot.holdings:
        if h.symbol.upper() == upper:
            return h
    return None
