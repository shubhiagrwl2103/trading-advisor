"""
Pydantic models for incoming TradingView webhook payloads.
All TA fields are Optional — different LuxAlgo indicators send different fields.
"""

from typing import Optional
from pydantic import BaseModel, Field


class TradingViewSignal(BaseModel):
    # Core identification
    ticker: str
    exchange: Optional[str] = None
    timeframe: Optional[str] = None          # "1D", "1W", "1M", "4h", etc.
    close: Optional[float] = None
    signal_type: Optional[str] = None        # "BUY", "SELL", "STRONG_BUY", etc.
    indicator: Optional[str] = None          # "LuxAlgo_AIStrategy", "LuxAlgo_Signals", etc.

    # Momentum
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None      # stored as macd_signal_line in DB
    macd_histogram: Optional[float] = None

    # Trend
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None

    # Volatility
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_position: Optional[float] = None      # 0.0 = at lower band, 1.0 = at upper band

    # LuxAlgo proprietary
    luxalgo_signal: Optional[str] = None
    luxalgo_confidence: Optional[float] = None

    # Volume
    volume: Optional[float] = None

    # Timestamp from TradingView (ISO 8601)
    timestamp: Optional[str] = None

    model_config = {"extra": "allow"}       # Accept unknown fields without error


def signal_is_meaningful(signal: TradingViewSignal) -> bool:
    """
    Require at least one TA indicator to be present.
    Prevents analysis on bare ticker-only webhooks.
    """
    ta_fields = [
        signal.rsi_14, signal.ema_50, signal.ema_200,
        signal.macd_histogram, signal.bb_position,
        signal.luxalgo_confidence, signal.close,
    ]
    return any(v is not None for v in ta_fields)


def is_strong_signal(signal: TradingViewSignal) -> bool:
    """
    Returns True if the signal is marked STRONG — these bypass cooldown.
    """
    if signal.signal_type and "STRONG" in signal.signal_type.upper():
        return True
    if signal.luxalgo_confidence and signal.luxalgo_confidence >= 0.90:
        return True
    return False
