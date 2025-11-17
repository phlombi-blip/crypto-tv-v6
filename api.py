# api.py
"""
API-Schicht für Bitfinex – lädt Daten und exportiert die
globalen Settings aus config.py weiter an ui.py.
"""

import requests
import pandas as pd

from config import (
    BITFINEX_BASE_URL,
    HEADERS,
    SYMBOLS,          # <-- wichtig!
    TIMEFRAMES,       # <-- wichtig!
)

# Diese beiden Variablen werden von ui.py importiert:
# SYMBOLS, TIMEFRAMES


def candles_for_history(interval_internal: str, years: float = 3.0) -> int:
    """Rechnet ungefähr aus, wie viele Kerzen für X Jahre gebraucht werden."""
    candles_per_day_map = {
        "1m": 60 * 24,
        "5m": 12 * 24,
        "15m": 4 * 24,
        "1h": 24,
        "4h": 6,
        "1D": 1,
    }
    candles_per_day = candles_per_day_map.get(interval_internal, 24)
    return int(candles_per_day * 365 * years)


def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    key = f"trade:{interval}:{symbol}"
    url = f"{BITFINEX_BASE_URL}/candles/{key}/hist"

    params = {"limit": limit, "sort": -1}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    raw = resp.json()
    if not isinstance(raw, list) or len(raw) == 0:
        return pd.DataFrame()

    rows = []
    for c in raw:
        if len(c) < 6:
            continue
        rows.append({
            "open_time": pd.to_datetime(c[0], unit="ms"),
            "open": float(c[1]),
            "close": float(c[2]),
            "high": float(c[3]),
            "low": float(c[4]),
            "volume": float(c[5]),
        })

    df = pd.DataFrame(rows).set_index("open_time")
    df.sort_index(inplace=True)
    return df


import streamlit as st

@st.cache_data(ttl=60)
def cached_fetch_klines(symbol: str, interval: str, limit: int = 200):
    return fetch_klines(symbol, interval, limit)


def fetch_ticker_24h(symbol: str):
    url = f"{BITFINEX_BASE_URL}/ticker/{symbol}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    d = resp.json()
    last_price = float(d[6])
    change_pct = float(d[5]) * 100.0
    return last_price, change_pct
