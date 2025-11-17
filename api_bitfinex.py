# api_bitfinex.py

"""
Bitfinex API–Layer für das TradingView-Projekt.
Enthält:
- Candle Abruf (OHLCV)
- Ticker Abruf
- Caching
- Helper für History-Länge
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

from config import BITFINEX_BASE_URL, HEADERS, YEARS_HISTORY


# ---------------------------------------------------------
# Helper: Anzahl Kerzen für X Jahre History
# ---------------------------------------------------------
def candles_for_history(interval_internal: str, years: float = YEARS_HISTORY) -> int:
    """
    Rechnet aus, wie viele Kerzen wir maximal laden sollten.
    Verhindert Überlastung der API.
    """
    candles_per_day_map = {
        "1m": 60 * 24,   # 1440
        "5m": 12 * 24,   # 288
        "15m": 4 * 24,   # 96
        "1h": 24,
        "4h": 6,
        "1D": 1,
    }

    candles_per_day = candles_per_day_map.get(interval_internal, 24)
    return int(candles_per_day * 365 * years)


# ---------------------------------------------------------
# Hauptfunktion: OHLCV Abruf
# ---------------------------------------------------------
def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    Holt Candle-Daten von Bitfinex.
    Liefert DataFrame mit:
    open_time, open, high, low, close, volume
    """
    key = f"trade:{interval}:{symbol}"
    url = f"{BITFINEX_BASE_URL}/candles/{key}/hist"

    params = {"limit": limit, "sort": -1}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    except Exception as e:
        raise RuntimeError(f"Netzwerkfehler: {e}")

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        raw = resp.json()
    except ValueError:
        raise RuntimeError(f"Ungültige JSON-Antwort: {resp.text[:200]}")

    if not isinstance(raw, list) or len(raw) == 0:
        return pd.DataFrame()

    rows = []
    for c in raw:
        if len(c) < 6:
            continue
        rows.append(
            {
                "open_time": pd.to_datetime(c[0], unit="ms"),
                "open": float(c[1]),
                "close": float(c[2]),
                "high": float(c[3]),
                "low": float(c[4]),
                "volume": float(c[5]),
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("open_time")
    df.sort_index(inplace=True)
    return df


# ---------------------------------------------------------
# Streamlit Cache Wrapper
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def cached_fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    Gecachter Candle-Abruf.
    Reduziert API-Last und erhöht Zuverlässigkeit.
    """
    return fetch_klines(symbol, interval, limit)


# ---------------------------------------------------------
# Abruf des 24h-Tickers
# ---------------------------------------------------------
def fetch_ticker_24h(symbol: str):
    """Gibt (last_price, percent_change) zurück."""
    url = f"{BITFINEX_BASE_URL}/ticker/{symbol}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
    except Exception as e:
        raise RuntimeError(f"Netzwerkfehler: {e}")

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError("Ungültige JSON-Antwort!")

    if not isinstance(data, (list, tuple)) or len(data) < 7:
        raise RuntimeError(f"Ticker-Format unerwartet: {data}")

    last_price = float(data[6])
    change_pct = float(data[5]) * 100.0

    return last_price, change_pct
