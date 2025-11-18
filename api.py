# api.py
import requests
import pandas as pd
import streamlit as st

from config import BITFINEX_BASE_URL, HEADERS, SYMBOLS, TIMEFRAMES

def candles_for_history(interval_internal: str, years: float = 3.0) -> int:
    candles_per_day_map = {
        "1m": 1440,
        "5m": 288,
        "15m": 96,
        "1h": 24,
        "4h": 6,
        "1D": 1,
    }
    candles_per_day = candles_per_day_map.get(interval_internal, 24)
    return int(candles_per_day * 365 * years)


def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    key = f"trade:{interval}:{symbol}"
    url = f"{BITFINEX_BASE_URL}/candles/{key}/hist"
    resp = requests.get(url, params={"limit": limit, "sort": -1}, headers=HEADERS)
    resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, list):
        return pd.DataFrame()

    rows = []
    for c in data:
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


@st.cache_data(ttl=60)
def cached_fetch_klines(symbol: str, interval: str, limit: int = 200):
    return fetch_klines(symbol, interval, limit)


def fetch_ticker_24h(symbol: str):
    url = f"{BITFINEX_BASE_URL}/ticker/{symbol}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    d = r.json()
    return float(d[6]), float(d[5]) * 100
