#V2
import requests
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime
from html import escape  # für sichere Tooltips d
import plotly.graph_objects as go

try:
    import yfinance as yf
except ImportError:
    yf = None

# KI-CoPilot Module
from ai.copilot import ask_copilot
from ai.patterns import detect_patterns
from signals import compute_signals as compute_signals_ext, latest_signal as latest_signal_ext, signal_color as signal_color_ext

from charts import create_price_rsi_figure, create_signal_history_figure
from email_notifier import send_signal_email
from backtest import compute_backtest_trades as compute_backtest_trades_ext, summarize_backtest as summarize_backtest_ext

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
PATTERN_LOOKBACK = 400

# Wie viele Jahre Historie sollen ungefähr geladen werden?
YEARS_HISTORY = 3.0

# Erweiterte Markt-Definitionen (Crypto + Stocks)
MARKETS = {
    "Crypto": {
        "label": "Bitfinex Spot",
        "source": "bitfinex",
        "symbols": {
            "BTC": "tBTCUSD",
            "ETH": "tETHUSD",
            "XRP": "tXRPUSD",
            "SOL": "tSOLUSD",
            "DOGE": "tDOGE:USD",
        },
        "timeframes": {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1D",
        },
        "default_timeframe": "1d",
    },
    "Stocks": {
        "label": "Yahoo Finance",
        "source": "yfinance",
        "symbols": {
            "NASDAQ": "^IXIC",
            "SMI": "^SSMI",
        },
        "timeframes": {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "4h": "4h",
            "1d": "1d",
            "1h": "1h",
        },
        "default_timeframe": "1d",
    },
}

DEFAULT_MARKET = "Crypto"


def candles_for_history(interval_internal: str, years: float = YEARS_HISTORY) -> int:
    """Rechnet ungefähr aus, wie viele Kerzen für X Jahre gebraucht werden."""
    candles_per_day_map = {
        "1m": 60 * 24,   # 1440
        "5m": 12 * 24,   # 288
        "15m": 4 * 24,   # 96
        "1h": 24,        # 24
        "4h": 6,         # 6
        "1D": 1,         # 1
        "1d": 1,         # 1 (Stocks via Yahoo)
    }
    candles_per_day = candles_per_day_map.get(interval_internal, 24)
    # Bitfinex akzeptiert pro Request max ~10k Kerzen – clampen, um 500er zu vermeiden.
    return min(int(candles_per_day * 365 * years), 9900)


# ---------------------------------------------------------
# THEME CSS
# ---------------------------------------------------------
DARK_CSS = """
<style>
body, .main { background-color: #0f172a; }
.block-container { padding-top: 2.8rem; padding-bottom: 0.6rem; }
.tv-card {
    background: #0f172a;
    border-radius: 0.9rem;
    border: 1px solid #1e293b;
    padding: 0.85rem 1rem;
    box-shadow: none !important;
}
.tv-title {
    font-weight: 700;
    font-size: 0.9rem;
    letter-spacing: 0.02em;
    color: #9ca3af;
    text-transform: uppercase;
    margin-bottom: 0.35rem;
}
.signal-badge {
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-weight: 700;
    display: inline-block;
    font-size: 0.82rem;
}
.stButton>button {
    border-radius: 0.55rem;
    padding: 0.45rem 0.9rem;
    font-weight: 700;
    white-space: nowrap;
}
</style>
"""

LIGHT_CSS = """
<style>
body, .main { background-color: #F5F6FB; }
.block-container { padding-top: 2.8rem; padding-bottom: 0.6rem; }
.tv-card {
    background: #FFFFFF;
    border-radius: 0.9rem;
    border: 1px solid #E5E7EB;
    padding: 0.85rem 1rem;
    box-shadow: none !important;
}
.tv-title {
    font-weight: 700;
    font-size: 0.9rem;
    letter-spacing: 0.02em;
    color: #6B7280;
    text-transform: uppercase;
    margin-bottom: 0.35rem;
}
.signal-badge {
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-weight: 700;
    display: inline-block;
    font-size: 0.82rem;
}
.stButton>button {
    border-radius: 0.55rem;
    padding: 0.45rem 0.9rem;
    font-weight: 700;
    white-space: nowrap;
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


def fetch_yf_ohlc(symbol: str, interval: str, years: float = YEARS_HISTORY) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance nicht installiert – bitte `pip install yfinance` ausführen.")

    intraday = interval.lower() in {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
    if intraday:
        # YF-Restriktionen: 1m nur ~7 Tage, andere Intraday max. ~60 Tage
        period = "7d" if interval.lower() == "1m" else "60d"
    else:
        days = max(int(years * 365), 1)
        period = "max" if days >= 3650 else f"{days}d"

    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        group_by="column",
        threads=False,
    )
    if df.empty:
        return pd.DataFrame()

    # yfinance liefert bei Einzel-Ticker teils MultiIndex (Level 0 = Field, Level 1 = Ticker)
    if isinstance(df.columns, pd.MultiIndex):
        if symbol in df.columns.get_level_values(1):
            df = df.xs(symbol, axis=1, level=1)
        else:
            df.columns = df.columns.get_level_values(0)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # doppelte Spaltennamen entfernen (falls YF mehrere Varianten liefert)
    df = df.loc[:, ~df.columns.duplicated()]

    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})

    # sicherstellen, dass nur die benötigten Spalten vorhanden sind
    required_cols = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing and {"open", "close"}.issubset(df.columns):
        # falls Volume fehlt etc., ergänzen wir.
        for col in missing:
            df[col] = np.nan
    try:
        df = df[required_cols]
    except KeyError:
        # harte Fallbacks: nehme nur die verfügbaren OHLC-Spalten
        avail = [c for c in required_cols if c in df.columns]
        if not avail:
            return pd.DataFrame()
        df = df[avail]

    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.sort_index(inplace=True)
    df = df.dropna(subset=["open", "high", "low", "close"], how="any")
    return df


@st.cache_data(ttl=300)
def cached_fetch_yf(symbol: str, interval: str, years: float = YEARS_HISTORY, cache_tag: str = "v2"):
    return fetch_yf_ohlc(symbol, interval, years=years)


def fetch_market_ohlc(symbol: str, interval: str, market: str, limit: int = None) -> pd.DataFrame:
    """
    Abstraktion für Krypto (Bitfinex) und Aktien/Indizes (Yahoo Finance).
    Limit wird nur für Bitfinex genutzt.
    """
    if market == "Stocks":
        return cached_fetch_yf(symbol, interval, years=YEARS_HISTORY)
    effective_limit = limit or candles_for_history(interval, years=YEARS_HISTORY)
    return cached_fetch_klines(symbol, interval, limit=effective_limit)


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
    EMA20/EMA50, MA200, Bollinger 20, RSI14, ATR14, ADX14, RVOL20.
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

    # True Range / ATR14
    high = df["high"]
    low = df["low"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()

    # ADX14 (Wilder)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move
    tr14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / tr14)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / tr14)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)) * 100
    # Guard against unexpected multi-column objects to avoid assignment errors
    if isinstance(dx, pd.DataFrame):
        dx = dx.squeeze()
    df["adx14"] = pd.Series(dx, index=df.index).ewm(alpha=1 / 14, adjust=False).mean()

    # Relative Volume (RVOL20): aktuelles Volumen / 20er Durchschnitt
    if "volume" in df.columns:
        df["rvol20"] = df["volume"] / df["volume"].rolling(20).mean()
    else:
        df["rvol20"] = np.nan

    return df


# ---------------------------------------------------------
# SIGNAL-LOGIK (mit Begründung) – erweiterte Profi-Variante
# ---------------------------------------------------------
def _hh_hl_state(df: pd.DataFrame) -> pd.Series:
    """Grobe HH/HL-Erkennung: +1 = HH/HL intakt, -1 = LH/LL, 0 = neutral."""
    if df.empty:
        return pd.Series([], dtype=int)
    highs = df["high"]
    lows = df["low"]
    hh_hl = [0]
    for i in range(1, len(df)):
        hh = highs.iloc[i] > highs.iloc[i - 1]
        hl = lows.iloc[i] > lows.iloc[i - 1]
        if hh and hl:
            hh_hl.append(1)
        elif (not hh) and (not hl):
            hh_hl.append(-1)
        else:
            hh_hl.append(0)
    return pd.Series(hh_hl, index=df.index)


def _signal_core_with_reason(last, prev):
    """
    Mehrschichtig:
    - Regime: MA200/EMA50, ADX, RVOL
    - Setups: Trend-Dip, Trend-Breakout, Reclaim
    - Exits: Trendbruch / Überhitzung
    Liefert (signal, reason).
    """

    close = last["close"]
    prev_close = prev["close"]

    ema20 = last["ema20"]
    ema50 = last["ema50"]
    ma200 = last["ma200"]

    rsi_now = last["rsi14"]
    rsi_prev = prev["rsi14"]

    bb_up = last["bb_up"]
    bb_lo = last["bb_lo"]
    bb_mid = last["bb_mid"]

    adx = last.get("adx14", np.nan)
    atr_pct = (last.get("atr14", np.nan) / close * 100) if close else np.nan
    rvol = last.get("rvol20", np.nan)

    # Regime-Filter (Long-Bias only)
    if pd.isna(ma200):
        return "HOLD", "MA200 nicht verfügbar – kein Regime."
    if close < ma200:
        return "HOLD", "Unter MA200 – kein Long-Regime."
    if pd.notna(adx) and adx < 20:
        return "HOLD", "Trend zu schwach (ADX < 20)."
    if pd.notna(rvol) and rvol < 0.9:
        return "HOLD", "Volumen zu dünn (RVOL < 0.9)."
    if pd.notna(atr_pct) and atr_pct > 9:
        return "HOLD", "Volatilität zu hoch (>9% ATR/Close)."

    trend_ok = ema20 > ema50 > ma200

    # Setup 1: Trend-Dip (Value-Zone + Rebound)
    dip_zone = (close <= ema20 * 1.025) and (close >= ema50 * 0.95)
    dip_rsi = (38 <= rsi_now <= 56) and (rsi_now > rsi_prev)
    if trend_ok and dip_zone and dip_rsi:
        return (
            "BUY",
            "Trend-Dip: Über MA200, EMA20>EMA50; Pullback zur Value-Zone (EMA20/EMA50) mit RSI-Rebound."
        )

    # Setup 2: Breakout (Fortsetzung)
    recent_high = max(prev["high"], last["high"])
    breakout_price = (close > recent_high) and (close > ema20)
    breakout_rsi = (50 <= rsi_now <= 65) and (rsi_now >= rsi_prev)
    breakout_vol = (pd.isna(rvol) or rvol >= 1.05)
    if trend_ok and breakout_price and breakout_rsi and breakout_vol:
        return (
            "BUY",
            "Trend-Breakout: Über MA200/EMA20/EMA50 mit neuem Hoch, RSI 50–65 steigend und Volumen-Expansion."
        )

    # Setup 3: Reclaim nach Flush
    reclaim = (prev_close < ema50) and (close > ema50) and (rsi_now > rsi_prev) and (rsi_now >= 46)
    if trend_ok and reclaim:
        return (
            "BUY",
            "Reclaim EMA50 nach Flush: Trend bleibt intakt, RSI dreht hoch – kleiner Re-Entry möglich."
        )

    # Exits / De-Risk: Überhitzung
    overheat = (close > bb_up) and (rsi_now > 72) and (rsi_now < rsi_prev)
    strong_overheat = (close > ema20 * 1.1) and (rsi_now > 80) and (rsi_now < rsi_prev)
    if strong_overheat:
        return (
            "STRONG SELL",
            "Extreme Überhitzung: Kurs > 1.1x EMA20, RSI > 80 und dreht – Risiko auf Abverkauf."
        )
    if overheat:
        return (
            "SELL",
            "Überhitzung: Kurs über oberem BB, RSI > 72 und fällt – Gewinnmitnahme/De-Risk."
        )

    # Trendbruch-Exit (falls man Long wäre) – hier nur als Warnsignal
    trend_break = (close < ema50) and (rsi_now < 50) and (rsi_now < rsi_prev)
    if trend_break:
        return (
            "SELL",
            "Trendbruch: Close < EMA50 und RSI < 50 fallend – Longs vorsichtig reduzieren."
        )

    # Standard: weiter halten / nichts tun
    return "HOLD", "Kein Setup: Trend-Filter passt, aber weder Dip noch Breakout bestätigt."


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
        df["signal"] = "NO DATA"
        df["signal_reason"] = "Nicht genug Daten für ein Signal."
        return df

    signals = []
    reasons = []
    last_sig = "NO DATA"

    for i in range(len(df)):
        if i == 0:
            signals.append("NO DATA")
            reasons.append("Erste Candle – keine Historie für Signalberechnung.")
            continue

        sig_raw, reason_raw = signal_with_reason(df.iloc[i], df.iloc[i - 1])

        # nur neues Signal, wenn Richtung wechselt
        if sig_raw == last_sig:
            sig_display = "HOLD"
            reason_display = f"Signal '{sig_raw}' besteht weiter – kein neues Signal generiert."
        else:
            sig_display = sig_raw
            reason_display = reason_raw

        signals.append(sig_display)
        reasons.append(reason_display)

        if sig_raw in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
            last_sig = sig_raw

    df["signal"] = signals
    df["signal_reason"] = reasons
    return df


# ---------------------------------------------------------
# BACKTEST
# ---------------------------------------------------------
def latest_signal(df: pd.DataFrame) -> str:
    if "signal" not in df.columns or df.empty:
        return "NO DATA"
    valid = df[df["signal"].isin(VALID_SIGNALS)]
    return valid["signal"].iloc[-1] if not valid.empty else "NO DATA"


def compute_backtest_trades(df: pd.DataFrame, max_hold_bars: int = 40, tp_mult: float = 1.2, atr_mult: float = 2.0) -> pd.DataFrame:
    """Wrapper: nutzt die Backtest-Engine aus backtest.py."""
    return compute_backtest_trades_ext(df, max_hold_bars=max_hold_bars, tp_mult=tp_mult, atr_mult=atr_mult)


def summarize_backtest(df_bt: pd.DataFrame):
    """Wrapper: nutzt summarize_backtest aus backtest.py."""
    return summarize_backtest_ext(df_bt)


def signal_color(signal: str) -> str:
    # Alias für Alt-Code; Hauptfarbe kommt aus signals.signal_color_ext
    return signal_color_ext(signal)


# ---------------------------------------------------------
# SESSION STATE INITIALISIERUNG
# ---------------------------------------------------------
def init_state():
    st.session_state.setdefault("market", DEFAULT_MARKET)
    if "selected_symbol" not in st.session_state:
        st.session_state.selected_symbol = list(MARKETS[DEFAULT_MARKET]["symbols"].keys())[0]
    if "selected_timeframe" not in st.session_state:
        st.session_state.selected_timeframe = MARKETS[DEFAULT_MARKET]["default_timeframe"]
    st.session_state.setdefault("theme", "Dark")
    st.session_state.setdefault("backtest_trades", pd.DataFrame())
    st.session_state.setdefault("copilot_question", "")
    # Zeitraum-Defaults (nur Platzhalter, Widget steuert diese Keys)
    st.session_state.setdefault("date_from", None)
    st.session_state.setdefault("date_to", None)


# ---------------------------------------------------------
# HAUPT UI / STREAMLIT APP
# ---------------------------------------------------------
def main():
    init_state()

    # Auto-Refresh (TradingView Feel)
    if st_autorefresh is not None:
        st_autorefresh(interval=60 * 1000, key="refresh")

    # -----------------------------------------------------
    # SIDEBAR / NAVIGATION – Reihenfolge: Markt, Zeitraum, Backtest, Theme
    # -----------------------------------------------------
    st.sidebar.title("⚙️ Navigation & Einstellungen")

    # 1) Markt
    st.sidebar.markdown("### Markt")
    market_names = list(MARKETS.keys())
    market = st.sidebar.radio(
        "Markt",
        market_names,
        index=market_names.index(st.session_state.market) if st.session_state.market in market_names else 0,
    )
    if market != st.session_state.market:
        st.session_state.market = market
        st.session_state.selected_symbol = list(MARKETS[market]["symbols"].keys())[0]
        st.session_state.selected_timeframe = MARKETS[market]["default_timeframe"]

    symbols_map = MARKETS[market]["symbols"]
    timeframes_map = MARKETS[market]["timeframes"]

    symbol_options = list(symbols_map.keys())
    if st.session_state.selected_symbol not in symbol_options:
        st.session_state.selected_symbol = symbol_options[0]

    symbol_label = st.sidebar.selectbox(
        "Aktives Symbol",
        symbol_options,
        index=symbol_options.index(st.session_state.selected_symbol),
    )
    st.session_state.selected_symbol = symbol_label

    tf_options = list(timeframes_map.keys())
    if st.session_state.selected_timeframe not in tf_options:
        st.session_state.selected_timeframe = MARKETS[market]["default_timeframe"]

    tf_label = st.sidebar.radio(
        "Timeframe",
        tf_options,
        index=tf_options.index(st.session_state.selected_timeframe),
    )
    st.session_state.selected_timeframe = tf_label

    # 2) Zeitraum – Widget steuert date_from/date_to in Session State
    st.sidebar.markdown("### Zeitraum")
    today = datetime.utcnow().date()
    default_from = st.session_state.get("date_from") or today
    default_to = st.session_state.get("date_to") or today

    st.sidebar.date_input(
        "📅 Von (Datum)",
        value=default_from,
        key="date_from",
    )
    st.sidebar.date_input(
        "📅 Bis (Datum)",
        value=default_to,
        key="date_to",
    )

    # 3) Backtest
    # Backtest-Section im Sidebar entfällt (Panel erklärt es)

    # 4) Theme
    st.sidebar.markdown("### Theme")
    theme = st.sidebar.radio(
        "Darstellung",
        ["Dark", "Light"],
        index=0 if st.session_state.theme == "Dark" else 1,
    )
    st.session_state.theme = theme

    # Theme anwenden
    st.markdown(DARK_CSS if theme == "Dark" else LIGHT_CSS, unsafe_allow_html=True)

    # Header Bar (TV-Style)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    st.markdown(
        f"""
        <div class="tv-card" style="margin-bottom: 0.4rem; padding: 0.65rem 0.9rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap: 1rem;">
                <div style="display:flex; align-items:center; gap: 0.6rem;">
                    <div style="font-size:1.1rem; font-weight:700;">{symbol_label}/{tf_label.upper()}</div>
                    <span style="background:#2563eb; color:white; padding:0.2rem 0.6rem; border-radius: 999px; font-size:0.8rem; font-weight:600;">
                        Live
                    </span>
                </div>
                <div style="text-align:right; font-size:0.85rem; opacity:0.85;">
                    Datenquelle: {MARKETS[market]["label"]}<br/>
                    Update: {now}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Gemeinsame Basis-Variablen
    symbol = symbols_map[symbol_label]
    interval_internal = timeframes_map[tf_label]

    # Layout: Hauptbereich (Watchlist + Charts + Backtest) und rechts Copilot
    col_main, col_right = st.columns([4.2, 1.8], gap="medium")

    # ---------------------------------------------------------
    # HAUPTBEREICH (WATCHLIST + CHARTS)
    # ---------------------------------------------------------
    with col_main:
        # WATCHLIST kompakt über dem Chart
        with st.container():
            st.markdown('<div class="tv-card">', unsafe_allow_html=True)
            st.markdown('<div class="tv-title">Watchlist</div>', unsafe_allow_html=True)

            rows = []
            selected_tf_internal = interval_internal
            limit_watch = candles_for_history(selected_tf_internal, years=YEARS_HISTORY)

            for label, sym in symbols_map.items():
                price = np.nan
                chg_pct = np.nan
                sig = "NO DATA"

                try:
                    df_tmp = fetch_market_ohlc(sym, selected_tf_internal, market, limit=limit_watch)
                    if df_tmp.empty:
                        raise ValueError("Keine Daten")

                    price = df_tmp["close"].iloc[-1]
                    if len(df_tmp) >= 2:
                        prev_close = df_tmp["close"].iloc[-2]
                        chg_pct = ((price - prev_close) / prev_close) * 100 if prev_close else np.nan

                    df_tmp = compute_indicators(df_tmp)
                    df_tmp = compute_signals_ext(df_tmp)
                    sig = latest_signal_ext(df_tmp)
                except Exception:
                    pass

                rows.append(
                    {
                        "Symbol": label,
                        "Price": price,
                        "Change %": chg_pct,
                        "Signal": sig,
                    }
                )

            df_watch = pd.DataFrame(rows)
            if not df_watch.empty:
                df_watch["Price"] = pd.to_numeric(df_watch["Price"], errors="coerce")
                df_watch["Change %"] = pd.to_numeric(df_watch["Change %"], errors="coerce")
                df_watch["Change %"] = df_watch["Change %"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "–")
                df_watch["Price"] = df_watch["Price"].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "–")
                st.dataframe(df_watch, use_container_width=True, height=170, hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # CHART-BEREICH
        st.markdown("")
        with st.container():
            st.markdown('<div class="tv-card">', unsafe_allow_html=True)

            st.markdown('<div class="tv-title">Chart</div>', unsafe_allow_html=True)

            # Daten abrufen + Zeitraum auf Basis der Sidebar-Werte
            try:
                limit_main = candles_for_history(interval_internal, years=YEARS_HISTORY)

                # komplette Historie laden
                df_all = fetch_market_ohlc(symbol, interval_internal, market, limit=limit_main)

                date_from = None
                date_to = None
                mask = None

                if not df_all.empty:
                    min_date = df_all.index.min().date()
                    max_date = df_all.index.max().date()

                    # Sidebar-Werte holen (können auch außerhalb des Bereichs liegen)
                    date_from = st.session_state.get("date_from") or min_date
                    date_to = st.session_state.get("date_to") or max_date

                    # Falls out-of-range, einfach lokal clampen – Session State NICHT überschreiben
                    if date_from < min_date:
                        date_from = min_date
                    if date_from > max_date:
                        date_from = max_date

                    if date_to < min_date:
                        date_to = min_date
                    if date_to > max_date:
                        date_to = max_date

                    if date_from > date_to:
                        date_from, date_to = date_to, date_from

                    mask = (df_all.index.date >= date_from) & (df_all.index.date <= date_to)

                # Indikatoren & Signale auf kompletter Historie
                if not df_all.empty:
                    df_all_ind = compute_indicators(df_all.copy())
                    df_all_ind = compute_signals_ext(df_all_ind)

                    if mask is not None:
                        df = df_all_ind.loc[mask]
                    else:
                        df = df_all_ind.copy()
                else:
                    df = pd.DataFrame()

                # Kennzahlen / Stati
                if df.empty or len(df) < 2:
                    sig = "NO DATA"
                    last_price = 0
                    change_abs = 0
                    change_pct = 0
                    last_time = None
                    signal_reason = ""
                    feed_ok = False
                    error_msg = "Keine Daten im gewählten Zeitraum."
                else:
                    sig = latest_signal_ext(df)
                    last = df.iloc[-1]
                    prev = df.iloc[-2]

                    last_price = last["close"]
                    change_abs = last_price - prev["close"]
                    change_pct = (change_abs / prev["close"]) * 100 if prev["close"] != 0 else 0
                    last_time = df.index[-1]
                    signal_reason = last.get("signal_reason", "")
                    feed_ok = True
                    error_msg = ""

                    # E-Mail Push bei Signalwechsel (Gmail)
                    prev_key = f"last_signal_{market}_{symbol_label}_{tf_label}"
                    prev_sig = st.session_state.get(prev_key)

                    if prev_sig != sig and sig in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
                        ok_email, msg_email = send_signal_email(
                            previous_signal=prev_sig,
                            new_signal=sig,
                            symbol=symbol_label,
                            timeframe=tf_label,
                            price=last_price,
                            reason=signal_reason,
                            when=last_time,
                        )
                        if ok_email:
                            st.toast(f"📧 Signalwechsel: {prev_sig or 'NONE'} → {sig} – E-Mail gesendet.")
                        else:
                            # Nur Info im UI, keine Exception
                            st.info(
                                f"Signalwechsel erkannt ({prev_sig or 'NONE'} → {sig}), "
                                f"aber E-Mail konnte nicht gesendet werden: {msg_email}"
                            )

                    st.session_state[prev_key] = sig

            except Exception as e:
                df = pd.DataFrame()
                sig = "NO DATA"
                last_price = 0
                change_abs = 0
                change_pct = 0
                last_time = None
                signal_reason = ""
                feed_ok = False
                error_msg = str(e)

            # Top-Kennzahlen
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.caption("Preis")
                st.markdown(f"**{last_price:,.2f} USD**" if feed_ok else "–")

            with k2:
                st.caption("Change letzte Candle")
                if feed_ok:
                    s = "+" if change_abs >= 0 else "-"
                    st.markdown(f"**{s}{abs(change_abs):.2f} ({s}{abs(change_pct):.2f}%)**")
                else:
                    st.markdown("–")

            with k3:
                st.caption("Signal")
                reason_html = escape(signal_reason, quote=True)
                st.markdown(
                    f'<span class="signal-badge" style="background-color:{signal_color_ext(sig)};" '
                    f'title="{reason_html}">{sig}</span>',
                    unsafe_allow_html=True,
                )

            with k4:
                st.caption("Status")
                if feed_ok:
                    st.markdown("🟢 **Live**")
                    if last_time is not None:
                        st.caption(f"Letzte Candle: {last_time}")
                    if date_from and date_to:
                        st.caption(f"Zeitraum: {date_from} bis {date_to}")
                else:
                    st.markdown("🔴 **Fehler**")
                    st.caption(error_msg[:80])

            st.markdown("---")

            # Price-Chart mit optionalem Pattern-Overlay (Top-1)
            if not df.empty:
                show_overlay = st.toggle("Pattern-Overlay anzeigen (Top 1)", value=False, key=f"overlay_{market}_{symbol_label}_{tf_label}")
                y_zoom_factor = st.slider(
                    "Y-Zoom (vertikal strecken)",
                    min_value=0.4,
                    max_value=2.0,
                    value=1.0,
                    step=0.1,
                    key=f"y_zoom_{market}_{symbol_label}_{tf_label}",
                    help="Werte <1 strecken die Kerzen (engerer Range), >1 entspannen die Range.",
                )
                df_pat = df.tail(PATTERN_LOOKBACK) if len(df) > PATTERN_LOOKBACK else df
                pat_overlay = detect_patterns(df_pat) if show_overlay else []

                if show_overlay:
                    # Nur Kerzen + Overlay, ohne EMA/BB
                    fig = go.Figure()
                    fig.add_candlestick(
                        x=df_pat.index,
                        open=df_pat["open"],
                        high=df_pat["high"],
                        low=df_pat["low"],
                        close=df_pat["close"],
                        name="Price",
                        increasing_line_color="#16a34a",
                        decreasing_line_color="#ef4444",
                        increasing_fillcolor="#16a34a",
                        decreasing_fillcolor="#ef4444",
                        opacity=0.9,
                    )
                    if pat_overlay:
                        options = {f"{p.name} ({p.score}/100, {p.direction})": p for p in pat_overlay}
                        csel, _ = st.columns([2, 5])
                        sel_label = csel.selectbox(
                            "Pattern auswählen (Top-Scores)",
                            list(options.keys()),
                            index=0,
                            key=f"pattern_select_{market}_{symbol_label}_{tf_label}",
                        )
                        top = options[sel_label]
                        line_color = "#000000"
                        offset = len(df) - len(df_pat)
                        for (i0, y0, i1, y1) in top.overlay_lines:
                            i0o = int(i0) + offset
                            i1o = int(i1) + offset
                            x0 = df.index[i0o] if i0o < len(df.index) else df.index[-1]
                            x1 = df.index[i1o] if i1o < len(df.index) else df.index[-1]
                            # Profi-Style: Trendlinie entlang der Steigung verlängern (kein horizontaler Flat-Extend)
                            extend = max(3, int((i1o - i0o) * 0.5))
                            ext_idx = min(len(df.index) - 1, i1o + extend)
                            delta_idx = max(i1o - i0o, 1e-9)
                            slope = (y1 - y0) / delta_idx
                            y_ext = y1 + slope * (ext_idx - i1o)
                            x_ext = df.index[ext_idx]
                            fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, xref="x", yref="y", line=dict(color=line_color, width=2))
                            fig.add_shape(type="line", x0=x1, y0=y1, x1=x_ext, y1=y_ext, xref="x", yref="y", line=dict(color=line_color, width=1, dash="dot"))
                        fig.add_annotation(
                            x=df_pat.index[min(len(df_pat) - 1, int(top.overlay_lines[0][0]))] if top.overlay_lines else df_pat.index[-1],
                            y=top.overlay_lines[0][1] if top.overlay_lines else df_pat["close"].iloc[-1],
                            text=f"{top.name} ({top.score}/100)",
                            showarrow=False,
                            font=dict(color=line_color, size=12),
                            bgcolor="rgba(255,255,255,0.1)",
                        )
                    # Support/Resistance aus lokalen Swing-Punkten (wie es ein Trader erwarten wuerde)
                    if not df_pat.empty:
                        highs_ser = df_pat["high"].reset_index(drop=True)
                        lows_ser = df_pat["low"].reset_index(drop=True)
                        w = 3
                        swing_highs = []
                        swing_lows = []
                        for i in range(w, len(highs_ser) - w):
                            # Hoch
                            left_h = highs_ser.iloc[i - w : i]
                            right_h = highs_ser.iloc[i + 1 : i + 1 + w]
                            v_h = highs_ser.iloc[i]
                            if v_h == max(highs_ser.iloc[i - w : i + w + 1]) and v_h > left_h.max() and v_h > right_h.max():
                                swing_highs.append(i)
                            # Tief
                            left_l = lows_ser.iloc[i - w : i]
                            right_l = lows_ser.iloc[i + 1 : i + 1 + w]
                            v_l = lows_ser.iloc[i]
                            if v_l == min(lows_ser.iloc[i - w : i + w + 1]) and v_l < left_l.min() and v_l < right_l.min():
                                swing_lows.append(i)

                        current_close = df_pat["close"].iloc[-1]

                        # Resistance: naechstes Hoch oberhalb; falls keins, letztes relevantes Hoch
                        res_candidates = [(i, float(highs_ser.iloc[i])) for i in swing_highs if highs_ser.iloc[i] > current_close]
                        if not res_candidates and swing_highs:
                            # fallback: juengstes Swing-High (auch wenn <= close)
                            res_candidates = [(swing_highs[-1], float(highs_ser.iloc[swing_highs[-1]]))]
                        if res_candidates:
                            idx_res, y_res = sorted(res_candidates, key=lambda t: (t[1], -t[0]))[0]
                            fig.add_shape(
                                type="line",
                                x0=0,
                                y0=y_res,
                                x1=1,
                                y1=y_res,
                                xref="paper",  # volle Breite
                                yref="y",
                                line=dict(color="#f6465d", width=2.5, dash="dot"),
                            )
                            fig.add_annotation(
                                xref="paper",
                                x=0.01,
                                y=y_res,
                                text="Resistance",
                                showarrow=False,
                                font=dict(color="#7c2d12", size=11),
                                bgcolor="rgba(255,255,255,0.9)",
                            )

                        # Support: naechstes Tief unterhalb; falls keins, letztes relevantes Tief
                        sup_candidates = [(i, float(lows_ser.iloc[i])) for i in swing_lows if lows_ser.iloc[i] < current_close]
                        if not sup_candidates and swing_lows:
                            sup_candidates = [(swing_lows[-1], float(lows_ser.iloc[swing_lows[-1]]))]
                        if sup_candidates:
                            idx_sup, y_sup = sorted(sup_candidates, key=lambda t: (-t[1], -t[0]))[0]
                            fig.add_shape(
                                type="line",
                                x0=0,
                                y0=y_sup,
                                x1=1,
                                y1=y_sup,
                                xref="paper",  # volle Breite
                                yref="y",
                                line=dict(color="#22c55e", width=2.5, dash="dot"),
                            )
                            fig.add_annotation(
                                xref="paper",
                                x=0.01,
                                y=y_sup,
                                text="Support",
                                showarrow=False,
                                font=dict(color="#14532d", size=11),
                                bgcolor="rgba(255,255,255,0.9)",
                            )
                    # Heller Hintergrund erzwingen (speziell für Mobile, damit schwarze Trendlinien gut sichtbar sind)
                    fig.update_layout(
                        margin=dict(l=10, r=10, t=30, b=10),
                        xaxis_title="",
                        yaxis_title="Price",
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        template="plotly_white",
                        font=dict(color="#111827"),
                        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#111827")),
                        yaxis=dict(showgrid=True, gridcolor="#e5e7eb", zeroline=False, tickfont=dict(color="#111827")),
                        dragmode="zoom",  # Pinch/Zoom als Default, wie TradingView
                    )
                    # Y-Range mit manuellem Zoom-Faktor
                    if not df_pat.empty:
                        y_min = df_pat["low"].min()
                        y_max = df_pat["high"].max()
                        span = max(y_max - y_min, 1e-9)
                        mid = (y_min + y_max) / 2
                        half = (span / 2) * y_zoom_factor
                        fig.update_yaxes(autorange=False, range=[mid - half, mid + half])
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        theme=None,  # eigenes helles Theme erzwingen (auch mobil)
                        config={"scrollZoom": True},  # Y-Achse via Maus/Scroll/Pinch zoombar wie TradingView
                    )
                else:
                    fig_price_rsi = create_price_rsi_figure(df, symbol_label, tf_label, theme)
                    fig_price_rsi.update_layout(dragmode="zoom")
                    # Y-Range der Price-Achse (Row 1) mit Zoom-Faktor
                    if not df.empty:
                        y_min = df["low"].min()
                        y_max = df["high"].max()
                        span = max(y_max - y_min, 1e-9)
                        mid = (y_min + y_max) / 2
                        half = (span / 2) * y_zoom_factor
                        fig_price_rsi.update_yaxes(autorange=False, range=[mid - half, mid + half], row=1, col=1, secondary_y=False)
                    st.plotly_chart(
                        fig_price_rsi,
                        use_container_width=True,
                        config={"scrollZoom": True},  # Hover an der Y-Achse + Scroll = vertikales Strecken/Kürzen
                    )
            else:
                st.warning("Keine Daten im gewählten Zeitraum – Zeitraum anpassen oder API/Internet prüfen.")

            st.markdown("</div>", unsafe_allow_html=True)

        # Signal-History + Backtest
        st.markdown("")
        col_hist, col_bt = st.columns([3, 2])

        # Signal-History Panel
        with col_hist:
            with st.container():
                st.markdown('<div class="tv-card">', unsafe_allow_html=True)
                st.markdown('<div class="tv-title">Signal History</div>', unsafe_allow_html=True)

                if df.empty:
                    st.info("Keine Signale verfügbar.")
                else:
                    allow = st.multiselect(
                        "Signale anzeigen",
                        ["STRONG BUY", "BUY", "SELL", "STRONG SELL"],
                        default=["STRONG BUY", "BUY", "SELL", "STRONG SELL"],
                    )
                    st.plotly_chart(
                        create_signal_history_figure(df, allow, theme),
                        use_container_width=True,
                    )

                st.markdown("</div>", unsafe_allow_html=True)

        # Backtest Panel
        with col_bt:
            with st.container():
                st.markdown('<div class="tv-card">', unsafe_allow_html=True)
                st.markdown('<div class="tv-title">Backtest</div>', unsafe_allow_html=True)

                if df.empty:
                    st.info("Keine Daten.")
                else:
                    st.caption("Long-only: Buy/Strong Buy halten bis Sell/Strong Sell oder letzte Kerze.")

                    # Time-Stop je nach Timeframe (Bars)
                    tf_stop = {
                        "1m": 720,   # 12h
                        "5m": 288,   # 1 Tag
                        "15m": 192,  # ~2 Tage
                        "1h": 96,    # ~4 Tage
                        "4h": 60,    # ~10 Tage
                        "1d": 60,    # ~60 Tage
                    }.get(tf_label, 60)

                    bt = compute_backtest_trades(df, max_hold_bars=tf_stop, tp_mult=1.2, atr_mult=2.0)
                    st.session_state.backtest_trades = bt

                    stats = summarize_backtest(bt)

                    if not stats:
                        st.info("Keine verwertbaren Trades.")
                    else:
                        kpi_cols = st.columns(4)
                        kpi_cols[0].metric("Trades", stats["total_trades"])
                        kpi_cols[1].metric("Ø Return %", f"{stats['overall_avg_return']:.2f}")
                        kpi_cols[2].metric("Hit Rate %", f"{stats['overall_hit_rate']:.1f}")
                        if stats.get("overall_avg_r") is not None:
                            kpi_cols[3].metric("Ø R", f"{stats['overall_avg_r']:.2f}")

                        if stats.get("per_type"):
                            st.markdown("---")
                            st.caption(f"{symbol_label} — {tf_label}")
                            st.table(pd.DataFrame(stats["per_type"]))

                st.markdown("</div>", unsafe_allow_html=True)

        # TRADES LIST – MIT CSV EXPORT
        st.markdown("")
        with st.container():
            st.markdown('<div class="tv-card">', unsafe_allow_html=True)
            st.markdown('<div class="tv-title">Trades List (Backtest)</div>', unsafe_allow_html=True)
            st.caption("Return % = (Exit - Entry) / Entry * 100 · Hold Bars = Kerzen zwischen Entry/Exit · R basiert auf Stop=2×ATR oder 2% Fallback, TP1 bei 1.2R (50% Ausstieg)")

            bt = st.session_state.backtest_trades

            if bt.empty:
                st.info("Noch keine Trades.")
            else:
                df_show = bt.copy()
                df_show["entry_time"] = df_show["entry_time"].dt.strftime("%Y-%m-%d %H:%M")
                df_show["exit_time"] = df_show["exit_time"].dt.strftime("%Y-%m-%d %H:%M")
                df_show["ret_pct"] = df_show["ret_pct"].map(lambda x: f"{x:.2f}")
                if "r_multiple" in df_show.columns:
                    df_show["r_multiple"] = df_show["r_multiple"].map(lambda x: f"{x:.2f}")
                if "hold_bars" in df_show.columns:
                    df_show["hold_bars"] = df_show["hold_bars"].astype(int)
                if "hold_time" in df_show.columns:
                    df_show["hold_time"] = df_show["hold_time"].astype(str)
                df_show["correct"] = df_show["correct"].map(lambda x: "✅" if x else "❌")

                df_show = df_show.rename(columns={"ret_pct": "Return %", "hold_bars": "Hold Bars", "hold_time": "Hold Time", "r_multiple": "R"})

                cols = [
                    "entry_time",
                    "exit_time",
                    "signal",
                    "exit_signal",
                    "reason",
                    "entry_price",
                    "exit_price",
                    "Return %",
                    "Hold Bars",
                    "Hold Time",
                    "R",
                    "correct",
                ]
                df_show = df_show[[c for c in cols if c in df_show.columns]]

                st.dataframe(df_show, use_container_width=True, height=220)

                csv = bt.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 CSV Export",
                    csv,
                    file_name=f"trades_{symbol_label}_{tf_label}.csv",
                    mime="text/csv",
                )

            st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # RECHTS: KI-COPILOT (Auto-Analyse = CoPilot)
    # ---------------------------------------------------------
    with col_right:
        with st.container():
            st.markdown('<div class="tv-card">', unsafe_allow_html=True)
            st.markdown('<div class="tv-title">🤖 KI-CoPilot</div>', unsafe_allow_html=True)

            if df.empty:
                st.info("Keine Marktdaten geladen – bitte zuerst einen gültigen Zeitraum wählen.")
                st.markdown("</div>", unsafe_allow_html=True)
                return

            # Key für Auto-Analyse im Session-State (pro Symbol + Timeframe)
            auto_key = f"copilot_auto_{market}_{symbol_label}_{tf_label}"

            def run_auto_analysis():
                """Startet eine automatische CoPilot-Analyse und speichert das Ergebnis im Session State."""
                with st.spinner("CoPilot analysiert den Chart..."):
                    st.session_state[auto_key] = ask_copilot(
                        question=(
                            "Bitte analysiere den aktuellen Chart anhand von RSI(14), EMA20, EMA50, MA200, "
                            "Bollinger-Bändern und der Candlestick-Struktur (Trend, Pullbacks, Übertreibungen). "
                            "Beschreibe zuerst nüchtern die technische Lage. "
                            "Formuliere danach eine mögliche technische Handelsidee basierend auf der "
                            "Marktpsychologie (z.B. FOMO, Panik, Kapitulation, Rebound), mit grober Einstiegszone, "
                            "Stop-Zone und Zielzone – ohne Beträge, Hebel oder Positionsgrößen. "
                            "Weise am Ende klar darauf hin, dass dies keine Anlageberatung ist, sondern nur ein "
                            "hypothetisches Szenario."
                        ),
                        df=df,
                        symbol=symbol_label,
                        timeframe=tf_label,
                        last_signal=sig,
                    )

            # Beim ersten Aufruf für dieses Symbol/TF automatisch Analyse holen
            if auto_key not in st.session_state:
                run_auto_analysis()

            auto_text = st.session_state.get(auto_key, "Noch keine Analyse verfügbar.")

            # Tabs: Auto-Analyse (CoPilot), KI-Chat, lokale Chartmuster
            patterns_local = detect_patterns(df) if not df.empty else []
            tab_auto, tab_chat, tab_patterns = st.tabs(["📊 Auto-Analyse (CoPilot)", "💬 KI-Chat", "📐 Chart Pattern"])

            # --- TAB 1: Auto-Analyse / Insights (nur CoPilot) ---
            with tab_auto:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**Automatische KI-Analyse ({symbol_label} – {tf_label})**")
                with c2:
                    if st.button(
                        "🔄 Neu laden",
                        key=f"btn_reanalyse_{market}_{symbol_label}_{tf_label}",
                    ):
                        run_auto_analysis()

                auto_text = st.session_state.get(auto_key, "Noch keine Analyse verfügbar.")
                st.markdown(auto_text)

            # --- TAB 2: Interaktiver KI-Chat ---
            with tab_chat:
                st.markdown("**Frag den CoPilot** – z.B.:")
                st.caption("„Wie würdest du den aktuellen BTC-Chart interpretieren?“")
                st.caption("„Welche Risiken siehst du im aktuellen Setup?“")

                question = st.text_area(
                    "Deine Frage an den KI-CoPilot",
                    value=st.session_state.get("copilot_question", ""),
                    height=80,
                )
                st.session_state.copilot_question = question

                if st.button("Antwort holen", key=f"btn_copilot_chat_{market}_{symbol_label}_{tf_label}"):
                    if not question.strip():
                        st.warning("Bitte zuerst eine Frage eingeben.")
                    else:
                        with st.spinner("CoPilot denkt nach..."):
                            answer = ask_copilot(
                                question=question,
                                df=df,
                                symbol=symbol_label,
                                timeframe=tf_label,
                                last_signal=sig,
                            )
                        st.markdown("**Antwort:**")
                        st.write(answer)

            # --- TAB 3: Lokale Chartmuster (ohne KI) ---
            with tab_patterns:
                st.markdown("**Erkannte Chartmuster (heuristisch, lokal)**")
                st.caption("Score 0-100 = Passgenauigkeit der Form; Ausblick = typische Fortsetzung (keine Garantie).")
                if not patterns_local:
                    st.info("Keine klaren Muster erkannt.")
                else:
                    for p in patterns_local:
                        st.markdown(
                            f"**{p.name}** — Score {p.score}/100 ({p.direction})  \n"
                            f"{p.rationale}  \n"
                            f"**Ausblick:** {p.projection}"
                        )

            st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# LAUNCH
# ---------------------------------------------------------
if __name__ == "__main__":
    main()
