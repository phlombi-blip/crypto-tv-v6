# indicators.py

"""
Technische Indikatoren:
- RSI (14)
- EMA20 / EMA50
- MA200 (Trendfilter)
- Bollinger Bands (20, 2σ)
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------
# RSI (14) – TradingView-ähnliche Version mit EWM
# ---------------------------------------------------------
def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Berechnet RSI mit EWM-Smoothing.
    Gleich wie TradingView: Delta → Up/Down getrennt → EWM → RS → RSI.
    """
    delta = series.diff()

    # positive & negative Bewegungen
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)

    # EWM wie TradingView
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()

    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))

    return rsi


# ---------------------------------------------------------
# EMA / SMA / Bollinger / RSI Wrapper
# ---------------------------------------------------------
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ergänzt einen OHLCV DataFrame um:
    - ema20
    - ema50
    - ma200
    - bb_mid
    - bb_up
    - bb_lo
    - rsi14
    """
    if df.empty:
        return df

    df = df.copy()

    try:
        close = df["close"]

        # EMA20 & EMA50
        df["ema20"] = close.ewm(span=20, adjust=False).mean()
        df["ema50"] = close.ewm(span=50, adjust=False).mean()

        # MA200 – großer Trendfilter
        df["ma200"] = close.rolling(200).mean()

        # Bollinger 20
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std(ddof=0)

        df["bb_mid"] = sma20
        df["bb_up"] = sma20 + 2 * std20
        df["bb_lo"] = sma20 - 2 * std20

        # RSI14
        df["rsi14"] = compute_rsi(close)

        return df

    except Exception:
        # Defensive fallback: df ohne Änderungen zurückgeben
        return df
