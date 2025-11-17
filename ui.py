import requests
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime
from html import escape  # für sichere Tooltips

# KI-CoPilot Module
from ai.analyzers import detect_trend, detect_rsi_divergence, detect_volume_spike
from ai.commentary import market_commentary
from ai.copilot import ask_copilot

from charts import create_price_rsi_figure, create_signal_history_figure

# Optional: Auto-Refresh (falls Paket installiert ist)
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# ---------------------------------------------------------
# BASIS-KONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Crypto Live + AI CoPilot",
    layout="wide",
)

# Bitfinex Public API (ohne API-Key)
BITFINEX_BASE_URL = "https://api-pub.bitfinex.com/v2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CryptoTV-V5/1.0; +https://streamlit.io)"
}

# Symbole auf Bitfinex
SYMBOLS = {
    "BTC": "tBTCUSD",
    "ETH": "tETHUSD",
    "XRP": "tXRPUSD",
    "SOL": "tSOLUSD",
    "DOGE": "tDOGE:USD",
}

# Anzeige-Labels → interne Timeframes (Bitfinex: 1m..1D)
TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",  # Bitfinex schreibt 1D
}

DEFAULT_TIMEFRAME = "1d"
VALID_SIGNALS = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]

# Wie viele Jahre Historie sollen ungefähr geladen werden?
YEARS_HISTORY = 3.0


def candles_for_history(interval_internal: str, years: float = YEARS_HISTORY) -> int:
    """Rechnet ungefähr aus, wie viele Kerzen für X Jahre gebraucht werden."""
    candles_per_day_map = {
        "1m": 60 * 24,   # 1440
        "5m": 12 * 24,   # 288
        "15m": 4 * 24,   # 96
        "1h": 24,        # 24
        "4h": 6,         # 6
        "1D": 1,         # 1
    }
    candles_per_day = candles_per_day_map.get(interval_internal, 24)
    return int(candles_per_day * 365 * years)


# ---------------------------------------------------------
# THEME CSS
# ---------------------------------------------------------
DARK_CSS = """
<style>
body, .main {
    background-color: #020617;
}
.block-container {
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
}
.tv-card {
    background: #020617;
    border-radius: 0.75rem;
    border: 1px solid #1f2933;
    padding: 0.75rem 1rem;
}
.tv-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: #9ca3af;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.signal-badge {
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-weight: 600;
    display: inline-block;
}
</style>
"""

LIGHT_CSS = """
<style>
body, .main {
    background-color: #F3F4F6;
}
.block-container {
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
}
.tv-card {
    background: #FFFFFF;
    border-radius: 0.75rem;
    border: 1px solid #E5E7EB;
    padding: 0.75rem 1rem;
}
.tv-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: #6B7280;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.signal-badge {
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-weight: 600;
    display: inline-block;
}
</style>
"""


# ---------------------------------------------------------
# API FUNKTIONEN – BITFINEX
# ---------------------------------------------------------
def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
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
def cached_fetch_klines(symbol: str, interval: str, limit: int = 200):
    """Gecachter Candle-Abruf – reduziert Last & Rate-Limits."""
    return fetch_klines(symbol, interval, limit)


def fetch_ticker_24h(symbol: str):
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


# ---------------------------------------------------------
# INDIKATOREN
# ---------------------------------------------------------
def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)

    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()

    rs = roll_up / roll_down
    return 100 - (100 / (1 + rs))


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    EMA20/EMA50, MA200, Bollinger 20, RSI14.
    """
    if df.empty:
        return df

    close = df["close"]

    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    df["ma200"] = close.rolling(200).mean()

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std(ddof=0)
    df["bb_mid"] = sma20
    df["bb_up"] = sma20 + 2 * std20
    df["bb_lo"] = sma20 - 2 * std20

    df["rsi14"] = compute_rsi(close)

    return df


# ---------------------------------------------------------
# SIGNAL-LOGIK (mit Begründung)
# ---------------------------------------------------------
def _signal_core_with_reason(last, prev):
    """
    Kernlogik:
    - Adaptive Bollinger
    - RSI Trend Confirmation
    - Blow-Off-Top Detector
    Liefert (signal, reason).
    """

    close = last["close"]
    prev_close = prev["close"]

    ema50 = last["ema50"]
    ma200 = last["ma200"]

    rsi_now = last["rsi14"]
    rsi_prev = prev["rsi14"]

    bb_up = last["bb_up"]
    bb_lo = last["bb_lo"]
    bb_mid = last["bb_mid"]

    high = last["high"]
    low = last["low"]
    candle_range = high - low
    upper_wick = high - max(close, last["open"])

    # Adaptive Volatility → passt Bollinger-Sensitivität an
    vol = (bb_up - bb_lo) / bb_mid if bb_mid != 0 else 0
    is_low_vol = vol < 0.06
    is_high_vol = vol > 0.12

    # MA200 fehlt → nicht traden
    if pd.isna(ma200):
        return "HOLD", "MA200 noch nicht verfügbar – zu wenig Historie, daher kein Trade."

    # Nur Long-Trading in Bullen-Trends
    if close < ma200:
        return "HOLD", "Kurs liegt unter MA200 – System handelt nur Long im Bullenmarkt."

    # Blow-Off-Top Detector
    blowoff = (
        candle_range > 0
        and upper_wick > candle_range * 0.45
        and close < prev_close
        and close > bb_up
        and rsi_now > 73
    )

    if blowoff:
        return (
            "STRONG SELL",
            "Blow-Off-Top: langer oberer Docht, Kurs über oberem Bollinger-Band "
            "und RSI > 73 mit Umkehrkerze – hohes Top-Risiko."
        )

    # STRONG BUY – tiefer Dip
    deep_dip = (
        close <= bb_lo
        and rsi_now < 35
        and rsi_now > rsi_prev
    )

    if deep_dip:
        if is_low_vol and close < bb_lo * 0.995:
            return (
                "STRONG BUY",
                "Tiefer Dip: Kurs an/unter unterem Bollinger-Band in ruhiger Phase, "
                "RSI < 35 dreht nach oben – aggressiver Rebound-Einstieg."
            )
        return (
            "STRONG BUY",
            "Tiefer Dip: Kurs am unteren Bollinger-Band, RSI < 35 und steigt wieder – "
            "kräftiges Long-Signal."
        )

    # BUY – normale gesunde Pullbacks
    buy_price_cond = (
        close <= bb_lo * (1.01 if is_high_vol else 1.00)
        or close <= ema50 * 0.96
    )

    buy_rsi_cond = (
        30 < rsi_now <= 48
        and rsi_now > rsi_prev
    )

    if buy_price_cond and buy_rsi_cond:
        return (
            "BUY",
            "Gesunder Pullback: Kurs im Bereich unteres Bollinger-Band bzw. leicht unter EMA50, "
            "RSI zwischen 30 und 48 und dreht nach oben."
        )

    # STRONG SELL – extreme Überhitzung
    strong_sell_cond = (
        close > ema50 * 1.12
        and close > bb_up
        and rsi_now > 80
        and rsi_now < rsi_prev
    )

    if strong_sell_cond:
        return (
            "STRONG SELL",
            "Extreme Überhitzung: Kurs deutlich über EMA50 und oberem Bollinger-Band, "
            "RSI > 80 und fällt bereits – starkes Abverkaufsrisiko."
        )

    # SELL – normale Übertreibung
    sell_cond = (
        close > bb_up
        and rsi_now > 72
        and rsi_now < rsi_prev
    )

    if sell_cond:
        return (
            "SELL",
            "Übertreibung: Kurs über dem oberen Bollinger-Band, RSI > 72 und dreht nach unten – "
            "Gewinnmitnahme / Short-Signal."
        )

    # Nichts erkannt
    return "HOLD", "Keine klare Übertreibung oder Dip – System wartet (HOLD)."


def signal_with_reason(last, prev):
    """Neue Schnittstelle: (signal, reason)."""
    return _signal_core_with_reason(last, prev)


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Wendet signal_with_reason() an und gibt nur neue Signale aus,
    wenn sich die Richtung ändert → keine gespammten Wiederholungssignale.
    Zusätzlich Spalte 'signal_reason'.
    """
    if df.empty or len(df) < 2:
        df["signal"]
