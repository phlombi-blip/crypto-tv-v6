import requests
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime
from html import escape

# KI-CoPilot Module
from ai.commentary import market_commentary
from ai.copilot import ask_copilot
from ai.analyzers import detect_trend, detect_rsi_divergence, detect_volatility

# Charts
from charts import create_price_rsi_figure, create_signal_history_figure

# Optional: Auto-Refresh
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


# ---------------------------------------------------------
# BASIS-KONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Crypto Live Ticker – TradingView Style V5 + AI",
    layout="wide",
)

BITFINEX_BASE_URL = "https://api-pub.bitfinex.com/v2"
HEADERS = {"User-Agent": "Mozilla/5.0"}

SYMBOLS = {
    "BTC": "tBTCUSD",
    "ETH": "tETHUSD",
    "XRP": "tXRPUSD",
    "SOL": "tSOLUSD",
    "DOGE": "tDOGE:USD",
}

TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}

DEFAULT_TIMEFRAME = "1d"
VALID_SIGNALS = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]
YEARS_HISTORY = 3.0


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------
def candles_for_history(interval_internal, years=YEARS_HISTORY):
    candles_per_day = {
        "1m": 1440,
        "5m": 288,
        "15m": 96,
        "1h": 24,
        "4h": 6,
        "1D": 1,
    }.get(interval_internal, 24)

    return int(candles_per_day * 365 * years)


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------
DARK_CSS = """
<style>
body, .main { background-color: #020617; }
.tv-card {
    background: #020617;
    border-radius: .75rem;
    border: 1px solid #1f2933;
    padding: .75rem 1rem;
}
.tv-title {
    font-weight: 600;
    font-size: .9rem;
    color: #9ca3af;
    text-transform: uppercase;
    margin-bottom: .3rem;
}
.ai-box {
    padding: .75rem;
    border-radius: .5rem;
    background: #0f172a;
    border: 1px solid #1e293b;
}
</style>
"""

LIGHT_CSS = """
<style>
body, .main { background-color: #F3F4F6; }
.tv-card {
    background: white;
    border-radius: .75rem;
    border: 1px solid #E5E7EB;
    padding: .75rem 1rem;
}
.tv-title {
    font-weight: 600;
    font-size: .9rem;
    color: #6B7280;
    text-transform: uppercase;
    margin-bottom: .3rem;
}
.ai-box {
    padding: .75rem;
    border-radius: .5rem;
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
}
</style>
"""


# ---------------------------------------------------------
# API BITFINEX
# ---------------------------------------------------------
def fetch_klines(symbol, interval, limit):
    key = f"trade:{interval}:{symbol}"
    url = f"{BITFINEX_BASE_URL}/candles/{key}/hist"
    r = requests.get(url, params={"limit": limit, "sort": -1}, headers=HEADERS)
    data = r.json()

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
def cached_fetch_klines(symbol, interval, limit):
    return fetch_klines(symbol, interval, limit)


def fetch_ticker_24h(symbol):
    url = f"{BITFINEX_BASE_URL}/ticker/{symbol}"
    r = requests.get(url, headers=HEADERS)
    d = r.json()
    return float(d[6]), float(d[5]) * 100.0


# ---------------------------------------------------------
# Indicators
# ---------------------------------------------------------
def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs = up.ewm(alpha=1/period).mean() / down.ewm(alpha=1/period).mean()
    return 100 - 100 / (1 + rs)


def compute_indicators(df):
    close = df["close"]
    df["ema20"] = close.ewm(span=20).mean()
    df["ema50"] = close.ewm(span=50).mean()
    df["ma200"] = close.rolling(200).mean()

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std(ddof=0)
    df["bb_mid"] = sma20
    df["bb_up"] = sma20 + 2 * std20
    df["bb_lo"] = sma20 - 2 * std20

    df["rsi14"] = compute_rsi(close)

    return df


# ---------------------------------------------------------
# Signals
# ---------------------------------------------------------
def _signal_core(last, prev):
    close = last["close"]
    prev_close = prev["close"]
    rsi = last["rsi14"]
    rsi_prev = prev["rsi14"]
    ema50 = last["ema50"]
    ma200 = last["ma200"]
    bb_up = last["bb_up"]
    bb_lo = last["bb_lo"]

    if pd.isna(ma200):
        return "HOLD", "Noch keine MA200"

    if close < ma200:
        return "HOLD", "Unter MA200"

    if close > bb_up and rsi > 72 and rsi < rsi_prev:
        return "SELL", "Überkauft + Umkehr"

    if close < bb_lo and rsi < 35 and rsi > rsi_prev:
        return "BUY", "Starker Dip + RSI dreht hoch"

    return "HOLD", "Neutral"


def compute_signals(df):
    sigs = []
    reasons = []
    last_sig = "NO DATA"

    for i in range(len(df)):
        if i == 0:
            sigs.append("NO DATA")
            reasons.append("Start")
            continue

        sig_raw, reason = _signal_core(df.iloc[i], df.iloc[i-1])

        if sig_raw == last_sig:
            sigs.append("HOLD")
            reasons.append(f"{sig_raw} bleibt bestehen")
        else:
            sigs.append(sig_raw)
            reasons.append(reason)
            if sig_raw in ["BUY", "SELL"]:
                last_sig = sig_raw

    df["signal"] = sigs
    df["signal_reason"] = reasons
    return df


def latest_signal(df):
    valid = df[df["signal"].isin(VALID_SIGNALS)]
    return valid["signal"].iloc[-1] if not valid.empty else "NO DATA"


# ---------------------------------------------------------
# State
# ---------------------------------------------------------
def init_state():
    st.session_state.setdefault("selected_symbol", "BTC")
    st.session_state.setdefault("selected_timeframe", DEFAULT_TIMEFRAME)
    st.session_state.setdefault("ai_chat_history", [])



# ---------------------------------------------------------
# MAIN UI
# ---------------------------------------------------------
def main():
    init_state()

    if st_autorefresh:
        st_autorefresh(interval=60000, key="auto")

    # Sidebar
    st.sidebar.title("⚙️ Einstellungen")
    theme = st.sidebar.radio("Theme", ["Dark", "Light"])
    st.markdown(DARK_CSS if theme == "Dark" else LIGHT_CSS, unsafe_allow_html=True)

    # Header
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    st.markdown(
        f"""
        <div class="tv-card">
            <div style="font-size:1.2rem; font-weight:600;">Crypto Live + AI CoPilot</div>
            <div style="opacity:0.7;">Update: {now}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([2, 5], gap="large")

    # ---------------------------------------------------------
    # LEFT PANEL — WATCHLIST
    # ---------------------------------------------------------
    with col_left:
        st.markdown('<div class="tv-card"><div class="tv-title">Watchlist</div>', unsafe_allow_html=True)

        choice = st.radio(
            "Symbol",
            list(SYMBOLS.keys()),
            index=list(SYMBOLS.keys()).index(st.session_state.selected_symbol),
            label_visibility="collapsed",
        )
        st.session_state.selected_symbol = choice

        rows = []
        tf = st.session_state.selected_timeframe
        limit_watch = candles_for_history(TIMEFRAMES[tf])

        for lbl, sym in SYMBOLS.items():
            try:
                price, chg = fetch_ticker_24h(sym)
                df_tmp = cached_fetch_klines(sym, TIMEFRAMES[tf], limit_watch)
                df_tmp = compute_indicators(df_tmp)
                df_tmp = compute_signals(df_tmp)
                sig = latest_signal(df_tmp)
            except:
                price, chg, sig = np.nan, np.nan, "NO DATA"

            rows.append({"Symbol": lbl, "Price": price, "Change %": chg, "Signal": sig})

        df_watch = pd.DataFrame(rows).set_index("Symbol")
        st.dataframe(df_watch, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # RIGHT PANEL — CHART + AI COPILOT
    # ---------------------------------------------------------
    with col_right:
        st.markdown('<div class="tv-card"><div class="tv-title">Chart</div>', unsafe_allow_html=True)

        # Timeframe buttons
        cols_tf = st.columns(len(TIMEFRAMES))
        for i, tf_key in enumerate(TIMEFRAMES):
            if cols_tf[i].button(tf_key):
                st.session_state.selected_timeframe = tf_key
                st.rerun()

        # Load chart data
        try:
            symbol = SYMBOLS[st.session_state.selected_symbol]
            tf = st.session_state.selected_timeframe
            interval_internal = TIMEFRAMES[tf]
            limit = candles_for_history(interval_internal)

            df_all = cached_fetch_klines(symbol, interval_internal, limit)
            df_all = compute_indicators(df_all)
            df_all = compute_signals(df_all)

            df = df_all
            feed_ok = True
        except Exception as e:
            df = pd.DataFrame()
            feed_ok = False
            st.error(str(e))

        # Chart
        if not df.empty:
            fig = create_price_rsi_figure(df, st.session_state.selected_symbol, tf, theme)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Keine Daten.")

        st.markdown("</div>", unsafe_allow_html=True)
    # ---------------------------------------------------------
    # KI-ANALYSE PANEL
    # ---------------------------------------------------------
    st.markdown("")

    st.markdown('<div class="tv-card">', unsafe_allow_html=True)
    st.markdown('<div class="tv-title">🤖 KI-Analyse</div>', unsafe_allow_html=True)

    if not df.empty:
        # --- 1) Automatische Indikatoranalyse ---
        trend = detect_trend(df)
        rsi_div = detect_rsi_divergence(df)
        vol = detect_volatility(df)

        # --- 2) GPT-Marktkommentar ---
        ai_comment = market_commentary(
            df=df,
            symbol=st.session_state.selected_symbol,
            timeframe=st.session_state.selected_timeframe,
            trend=trend,
            rsi_divergence=rsi_div,
            volatility=vol,
        )

        st.markdown(
            f"""
            <div class="ai-box">
                <b>📊 Automatische Marktanalyse</b><br><br>
                {ai_comment}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Manuelles Aktualisieren
        if st.button("🔍 KI-Analyse aktualisieren"):
            st.rerun()

    else:
        st.info("Keine Daten für KI-Analyse.")
    st.markdown("</div>", unsafe_allow_html=True)



    # ---------------------------------------------------------
    # KI-COPILOT CHAT
    # ---------------------------------------------------------
    st.markdown("")
    st.markdown('<div class="tv-card">', unsafe_allow_html=True)
    st.markdown('<div class="tv-title">🧠 KI-CoPilot Chat</div>', unsafe_allow_html=True)

    st.markdown("""
        Stelle Fragen wie:<br>
        • „Ist das ein möglicher Breakout?“<br>
        • „Bewerte den Trend.“<br>
        • „Ist jetzt ein guter Zeitpunkt zum Einstieg?“<br>
        • „Was sagt das Volumen?“<br>
    """, unsafe_allow_html=True)

    # Chatverlauf anzeigen
    for msg in st.session_state.ai_chat_history:
        who, text = msg["role"], msg["content"]
        bubble_color = "#1e293b" if theme == "Dark" else "#e2e8f0"
        align = "left" if who == "assistant" else "right"

        st.markdown(
            f"""
            <div style='text-align:{align}; margin:6px 0;'>
                <div style='display:inline-block; padding:8px 12px; 
                            background:{bubble_color}; border-radius:8px; 
                            max-width:80%;'
                >
                    {text}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Eingabefeld
    user_msg = st.text_input("Deine Frage an den CoPilot:")
    if st.button("Senden"):
        if user_msg.strip():
            st.session_state.ai_chat_history.append(
                {"role": "user", "content": user_msg}
            )

            # Antwort vom CoPilot
            answer = ask_copilot(user_msg, df)
            st.session_state.ai_chat_history.append(
                {"role": "assistant", "content": answer}
            )

            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)



# ---------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------
if __name__ == "__main__":
    main()
