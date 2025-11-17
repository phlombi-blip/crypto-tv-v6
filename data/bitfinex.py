import requests
import pandas as pd
import streamlit as st

from config import BITFINEX_BASE_URL, HEADERS


def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    Holt Kerzen von der Bitfinex-Public-API.
    """
    timeframe = interval  # z.B. "1m", "1h", "1D"
    key = f"trade:{timeframe}:{symbol}"
    url = f"{BITFINEX_BASE_URL}/candles/{key}/hist"

    params = {"limit": limit, "sort": -1}

    resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Candles HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        raw = resp.json()
    except ValueError:
        raise RuntimeError(f"Candles: Ungültige JSON-Antwort: {resp.text[:200]}")

    if not isinstance(raw, list) or len(raw) == 0:
        return pd.DataFrame()

    rows = []
    for c in raw:
        # [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
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


@st.cache_data(ttl=60)
def cached_fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    Gecachter Candle-Abruf – reduziert Last & Rate-Limits.
    """
    return fetch_klines(symbol, interval, limit)


def fetch_ticker_24h(symbol: str):
    """
    Holt Ticker-Infos (Last Price, 24h Change %) von Bitfinex.
    """
    url = f"{BITFINEX_BASE_URL}/ticker/{symbol}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Ticker HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        d = resp.json()
    except ValueError:
        raise RuntimeError(f"Ticker: Ungültige JSON-Antwort: {resp.text[:200]}")

    if not isinstance(d, (list, tuple)) or len(d) < 7:
        raise RuntimeError(f"Ticker: Unerwartetes Format: {d}")

    last_price = float(d[6])
    change_pct = float(d[5]) * 100.0
    return last_price, change_pct
