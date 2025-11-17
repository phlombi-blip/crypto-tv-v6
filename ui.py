# ui.py
import streamlit as st
from datetime import datetime
from html import escape
import pandas as pd
import numpy as np

# interne Module (Flat Structure!)
from config import (
    SYMBOLS,
    TIMEFRAMES,
    DEFAULT_TIMEFRAME,
    YEARS_HISTORY,
    SIGNAL_COLORS,
)
from api import (
    fetch_ticker_24h,
    cached_fetch_klines,
    candles_for_history,
)
from indicators import compute_indicators
from signals import compute_signals, latest_signal, signal_color
from charts import create_price_rsi_figure, create_signal_history_figure
from backtest import compute_backtest_trades, summarize_backtest

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="CryptoTV – TradingView Style",
    layout="wide",
)

# ---------------------------------------------------------
# SIDEBAR – Einstellungen
# ---------------------------------------------------------
st.sidebar.title("⚙️ Einstellungen")

theme = st.sidebar.radio(
    "Theme",
    ["Dark", "Light"],
    index=0,
)

st.sidebar.markdown("---")

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

st.markdown(
    f"""
    <h2 style="margin-bottom:0;">CryptoTV – TradingView Style</h2>
    <div style="opacity:0.7;">Letztes Update: {now}</div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")

# Layout: Links Watchlist, rechts Charts
col_left, col_right = st.columns([2, 5], gap="medium")

# ---------------------------------------------------------
# WATCHLIST (LINKS)
# ---------------------------------------------------------
with col_left:
    st.subheader("Watchlist")

    sel_symbol = st.radio("Symbol", list(SYMBOLS.keys()))
    symbol = SYMBOLS[sel_symbol]

    sel_tf = st.radio("Timeframe", list(TIMEFRAMES.keys()), index=list(TIMEFRAMES.keys()).index(DEFAULT_TIMEFRAME))
    interval_internal = TIMEFRAMES[sel_tf]

    st.markdown("---")

    # kleine Tickerliste
    rows = []
    limit_watch = candles_for_history(interval_internal, years=YEARS_HISTORY)

    for label, sym in SYMBOLS.items():
        try:
            price, chg_pct = fetch_ticker_24h(sym)
            df_tmp = cached_fetch_klines(sym, interval_internal, limit=limit_watch)
            df_tmp = compute_indicators(df_tmp)
            df_tmp = compute_signals(df_tmp)
            sig = latest_signal(df_tmp)
        except Exception:
            price, chg_pct, sig = np.nan, np.nan, "NO DATA"

        rows.append({
            "Symbol": label,
            "Price": price,
            "Change %": chg_pct,
            "Signal": sig,
        })

    df_watch = pd.DataFrame(rows).set_index("Symbol")

    st.dataframe(
        df_watch.style.format({"Price": "{:,.2f}", "Change %": "{:+.2f}"}),
        use_container_width=True,
    )

# ---------------------------------------------------------
# MAIN CHART AREA (RECHTS)
# ---------------------------------------------------------
with col_right:
    st.subheader(f"Chart – {sel_symbol}")

    # alle Kerzen laden
    limit_main = candles_for_history(interval_internal, years=YEARS_HISTORY)
    df_all = cached_fetch_klines(symbol, interval_internal, limit_main)

    if df_all.empty:
        st.error("Keine Daten von der API.")
    else:
        # Date-Picker
        min_date = df_all.index.min().date()
        max_date = df_all.index.max().date()

        c1, c2 = st.columns(2)
        with c1:
            date_from = st.date_input("Von", min_date, min_value=min_date, max_value=max_date)
        with c2:
            date_to = st.date_input("Bis", max_date, min_value=min_date, max_value=max_date)

        # falls vertauscht → korrigieren
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        mask = (df_all.index.date >= date_from) & (df_all.index.date <= date_to)

        df = df_all.loc[mask].copy()

        # Indikatoren + Signale
        df = compute_indicators(df)
        df = compute_signals(df)

        if df.empty:
            st.warning("Keine Daten im gewählten Zeitraum.")
        else:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last

            last_price = last["close"]
            change_abs = last_price - prev["close"]
            change_pct = (change_abs / prev["close"] * 100) if prev["close"] != 0 else 0
            sig = last["signal"]
            reason = last["signal_reason"]

            # TOP KENNZAHLEN
            k1, k2, k3 = st.columns(3)
            with k1:
                st.caption("Preis")
                st.markdown(f"**{last_price:,.2f} USD**")
            with k2:
                st.caption("Änderung letzte Kerze")
                s = "+" if change_abs >= 0 else "-"
                st.markdown(f"**{s}{abs(change_abs):.2f} ({s}{abs(change_pct):.2f}%)**")
            with k3:
                st.caption("Signal")
                st.markdown(
                    f"""<span style="padding:4px 12px;border-radius:12px;background:{signal_color(sig)};">
                    {sig}</span>""",
                    unsafe_allow_html=True,
                )

            st.caption(f"Grund: {escape(reason)}")

            st.markdown("---")

            # Hauptchart
            fig = create_price_rsi_figure(df, sel_symbol, sel_tf, theme)
            st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# SIGNAL HISTORY + BACKTEST
# ---------------------------------------------------------
st.markdown("---")
st.subheader("Signal History & Backtest")
col_sh, col_bt = st.columns([3, 2])

with col_sh:
    if df.empty:
        st.info("Keine Signale verfügbar.")
    else:
        allow = st.multiselect(
            "Signale anzeigen:",
            ["STRONG BUY", "BUY", "SELL", "STRONG SELL"],
            default=["STRONG BUY", "BUY", "SELL", "STRONG SELL"],
        )
        fig2 = create_signal_history_figure(df, allow, theme)
        st.plotly_chart(fig2, use_container_width=True)

with col_bt:
    if df.empty:
        st.info("Keine Backtest-Daten.")
    else:
        horizon = st.slider("Haltezeit (Kerzen)", 1, 20, 5)
        trades = compute_backtest_trades(df, horizon)
        stats = summarize_backtest(trades)

        if not trades.empty:
            st.write(f"**Trades:** {stats['total_trades']}")
            st.write(f"**Ø Return:** {stats['overall_avg_return']:.2f}%")
            st.write(f"**Trefferquote:** {stats['overall_hit_rate']:.1f}%")

            st.markdown("---")
            st.caption("Trades")
            st.dataframe(trades, use_container_width=True, height=260)
        else:
            st.info("Keine Trades in diesem Zeitraum.")

st.markdown("---")
if st.button("🔄 Refresh"):
    st.rerun()
