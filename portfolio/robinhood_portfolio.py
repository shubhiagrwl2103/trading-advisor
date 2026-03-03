"""
Robinhood portfolio from CSV export.
Robinhood has no safe official API, so we parse the CSV you export manually.

Expected CSV columns (Robinhood export format):
  Name, Symbol, Quantity, Average Cost, Equity, Percent Change, ...
"""

import io
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Robinhood CSV column names (may vary slightly between exports)
_COL_SYMBOL = "Symbol"
_COL_QUANTITY = "Quantity"
_COL_EQUITY = "Equity"
_COL_AVG_COST = "Average Cost"
_COL_NAME = "Name"


def parse_robinhood_csv(csv_bytes: bytes) -> List[Dict]:
    """
    Parse a Robinhood portfolio CSV export.

    Returns a list of dicts:
    [
        {
            "symbol": "MSTR",
            "name": "MicroStrategy Inc",
            "quantity": 10.0,
            "avg_cost": 245.30,
            "equity_usd": 2450.00,
        },
        ...
    ]
    """
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as e:
        raise ValueError(f"Failed to parse Robinhood CSV: {e}") from e

    # Normalise column names (strip whitespace)
    df.columns = df.columns.str.strip()

    required = {_COL_SYMBOL, _COL_QUANTITY}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Robinhood CSV missing expected columns: {missing}. Got: {list(df.columns)}")

    holdings = []
    for _, row in df.iterrows():
        sym = str(row.get(_COL_SYMBOL, "")).strip()
        if not sym or sym.lower() == "nan":
            continue

        try:
            qty = float(str(row.get(_COL_QUANTITY, 0)).replace(",", ""))
        except (ValueError, TypeError):
            qty = 0.0

        try:
            equity = float(str(row.get(_COL_EQUITY, 0)).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            equity = 0.0

        try:
            avg_cost = float(str(row.get(_COL_AVG_COST, 0)).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            avg_cost = 0.0

        if qty <= 0:
            continue

        holdings.append(
            {
                "symbol": sym.upper(),
                "name": str(row.get(_COL_NAME, sym)).strip(),
                "quantity": qty,
                "avg_cost": avg_cost,
                "equity_usd": equity,
            }
        )

    logger.info(f"Parsed {len(holdings)} Robinhood holdings from CSV")
    return holdings


def robinhood_holdings_to_snapshot(holdings: List[Dict], upload_timestamp: Optional[str] = None) -> Dict:
    """
    Convert parsed holdings list to a snapshot dict suitable for storing in SQLite.
    """
    ts = upload_timestamp or datetime.now(timezone.utc).isoformat()
    total = sum(h["equity_usd"] for h in holdings)

    return {
        "upload_timestamp": ts,
        "total_equity_usd": total,
        "holdings": holdings,
    }
