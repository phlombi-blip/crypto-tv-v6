# ui.py

import streamlit as st
from datetime import datetime

# interne Module
from crypto_tv_v6.config import signal_colors, DEFAULT_TIMEFRAME, YEARS_HISTORY
from crypto_tv_v6.api import (
    fetch_ticker_24h,
    cached_fetch_klines,
    SYMBOLS,
    TIMEFRAMES,
    candles_for_history
)
from crypto_tv_v6.indicators import compute_indicators
from crypto_tv_v6.signals import compute_signals, latest_signal, signal_color
from crypto_tv_v6.charts import create_price_rsi_figure, create_signal_history_figure
from crypto_tv_v6.backtest import compute_backtest_trades, summarize_backtest

# externe Modules
from html import escape
import pandas as pd
import numpy as np


# ---------------------------------------------------------
# Page config
# ---------------------------------------------------------
st.set_page_config(
    page_title="Crypto Live Ticker – TradingView Style",
    layout="wide",
)


# ---------------------------------------------------------
# Session State
# ---------------------------------------------------------
def init_state():
    st.session_state.setdefault("selected_symbol", "BTC")
    st.session_state.setdefault("selected_timeframe", "1d")
    st.session_state.setdefault("theme", "Dark")
    st.session_state.setdefault("backtest_horizon", 5)
    st.session_state.setdefault("date_from", None)
    st.session_state.setdefault("date_to", None)


init_state()


# ---------------------------------------------------------
# CSS Themes
# ---------------------------------------------------------
DARK_CSS = """
<style>
body, .main { background-color:#020617; }
.tv-card {
    background:#020617; border-radius:0.75rem; 
    border:1px solid #1f2933; padding:0.8rem 1rem;
}
.tv-title { font-weight:600; font-size:0.9rem; color:#9ca3af;
    text-transform:uppercase; margin-bottom:0.3rem; }
.signal-badge {
    padding:0.25rem 0.7rem; border-radius:999px; 
    font-weight:600; display:inline-block;
}
</style>
"""

LIGHT_CSS = """
<style>
body, .main { background-color:#F3F4F6; }
.tv-card {
    background:#ffffff; border-radius:0.75rem; 
    border:1px solid #E5E7EB; padding:0.8rem 1rem;
}
.tv-title {
    font-weight:600; font-size:0.9rem; color:#6B7280;
    text-transform:uppercase; margin-bottom:0.3rem;
}
.signal-badge {
    padding:0.25rem 0.7rem; border-radius:999px;
    font-weight:600; display:inline-block;
}
</style>
"""


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
st.sidebar.title("⚙️ Einstellungen")

theme = st.sidebar.radio(
    "Theme",
    ["Dark", "Light"],
    index=0 if st.session_state.theme == "Dark" else 1,
)
st.session_state.theme = theme

# inject CSS
st.markdown(DARK_CSS if theme == "Dark" else LIGHT_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
st.markdown(
    f"""
    <div class="tv-card" style="margin-bottom:0.6rem;">
        <div style="display:flex; justify-content:space-between;">
            <div>
                <div class="tv-title">Crypto Live Ticker</div>
                <div style="font-size:1.1rem; font-weight:600;">
                    TradingView Style • Desktop
                </div>
            </div>
            <div style="text-align:right; font-size:0.85rem; opacity:0.8;">
                Datenquelle: Bitfinex Spot<br/>
                Letztes Update: {now}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Layout: Left Watchlist / Right Charts
# ---------------------------------------------------------
col_left, col_right = st.columns([2, 5], gap="medium")


# =========================================================
# LEFT PANEL — Watchlist
# =========================================================
with col_left:
    with st.container():
        st.markdown('<div class="tv-card">', unsafe_allow_html=True)
        st.markdown('<div class="tv-title">Watchlist</div>', unsafe_allow_html=True)

        sel = st.radio(
            "Symbol",
            list(SYMBOLS.keys()),
            index=list(SYMBOLS.keys()).index(st.session_state.selected_symbol),
            label_visibility="collapsed",
        )
        st.session_state.selected_symbol = sel

        tf_label = st.session_state.selected_timeframe
        tf_internal = TIMEFRAMES[tf_label]
        limit_watch = candles_for_history(tf_internal, years=3)

        rows = []
        for label, sym in SYMBOLS.items():
            try:
                price, chg_pct = fetch_ticker_24h(sym)
                df_tmp = cached_fetch_klines(sym, tf_internal, limit=limit_watch)
                df_tmp = compute_indicators(df_tmp)
                df_tmp = compute_signals(df_tmp)
                sig = latest_signal(df_tmp)
            except Exception:
                price = np.nan
                chg_pct = np.nan
                sig = "NO DATA"

            rows.append(
                {"Symbol": label, "Price": price, "Change %": chg_pct, "Signal": sig}
            )

        df_watch = pd.DataFrame(rows).set_index("Symbol")

        def highlight(row):
            if row.name == st.session_state.selected_symbol:
                bg = "#111827" if theme == "Dark" else "#D1D5DB"
                fg = "white" if theme == "Dark" else "black"
                return [f"background-color:{bg}; color:{fg}"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_watch.style.apply(highlight, axis=1).format(
                {"Price": "{:,.2f}", "Change %": "{:+.2f}"}
            ),
            use_container_width=True,
            height=270,
        )

        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# RIGHT PANEL — Chart + Signals + Backtest
# =========================================================
with col_right:
    with st.container():
        st.markdown('<div class="tv-card">', unsafe_allow_html=True)
        st.markdown('<div class="tv-title">Chart</div>', unsafe_allow_html=True)

        # Timeframe buttons
        cols_tf = st.columns(len(TIMEFRAMES))
        for i, tf in enumerate(TIMEFRAMES.keys()):
            with cols_tf[i]:
                if st.button(tf, key=f"tf_{tf}"):
                    st.session_state.selected_timeframe = tf
                    st.rerun()

        # -------------------------------------------------
        # Load full data
        # -------------------------------------------------
        symbol = SYMBOLS[st.session_state.selected_symbol]
        tf_label = st.session_state.selected_timeframe
        tf_internal = TIMEFRAMES[tf_label]

        limit_main = candles_for_history(tf_internal, years=3)
        df_all = cached_fetch_klines(symbol, tf_internal, limit=limit_main)

        # -------------------------------------------------
        # Date Picker Range
        # -------------------------------------------------
        if not df_all.empty:
            min_d = df_all.index.min().date()
            max_d = df_all.index.max().date()

            # load state or default
            def_from = st.session_state.date_from or min_d
            def_to = st.session_state.date_to or max_d

            c_from, c_to = st.columns(2)
            with c_from:
                date_from = st.date_input(
                    "Von",
                    value=def_from,
                    min_value=min_d,
                    max_value=max_d,
                    key="date_from",
                )
            with c_to:
                date_to = st.date_input(
                    "Bis",
                    value=def_to,
                    min_value=min_d,
                    max_value=max_d,
                    key="date_to",
                )

            if date_from > date_to:
                date_from, date_to = date_to, date_from

            mask = (df_all.index.date >= date_from) & (df_all.index.date <= date_to)
        else:
            mask = None

        # -------------------------------------------------
        # Indicators + Signals
        # -------------------------------------------------
        if not df_all.empty:
            df_all = compute_indicators(df_all)
            df_all = compute_signals(df_all)

            df = df_all.loc[mask] if mask is not None else df_all.copy()
        else:
            df = pd.DataFrame()

        # -------------------------------------------------
        # Top Info Bar
        # -------------------------------------------------
        k1, k2, k3, k4 = st.columns(4)

        if df.empty:
            last_price = 0
            change_abs = 0
            change_pct = 0
            sig = "NO DATA"
            signal_reason = ""
            feed_ok = False
        else:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            last_price = last["close"]
            change_abs = last_price - prev["close"]
            change_pct = (change_abs / prev["close"]) * 100 if prev["close"] else 0
            sig = latest_signal(df)
            signal_reason = last.get("signal_reason", "")
            feed_ok = True

        with k1:
            st.caption("Preis")
            st.markdown(f"**{last_price:,.2f} USD**" if feed_ok else "–")

        with k2:
            st.caption("Change letzte Candle")
            if feed_ok:
                s = "+" if change_abs >= 0 else "-"
                st.markdown(f"**{s}{abs(change_abs):.2f} ({s}{abs(change_pct):.2f}%)**")
            else:
                st.write("–")

        with k3:
            st.caption("Signal")
            reason_html = escape(signal_reason)
            color = {
                "STRONG BUY": "#00e676",
                "BUY": "#81c784",
                "SELL": "#e57373",
                "STRONG SELL": "#d32f2f",
                "HOLD": "#9ca3af",
            }.get(sig, "#9ca3af")

            st.markdown(
                f'<span class="signal-badge" style="background:{color};" '
                f'title="{reason_html}">{sig}</span>',
                unsafe_allow_html=True,
            )

        with k4:
            st.caption("Status")
            st.write("🟢 Live" if feed_ok else "🔴 Fehler")
            if feed_ok:
                st.caption(f"Range: {date_from} bis {date_to}")

        st.markdown("---")

        # -------------------------------------------------
        # Main Chart
        # -------------------------------------------------
        if df.empty:
            st.warning("Keine Daten im gewählten Zeitraum.")
        else:
            fig = create_price_rsi_figure(
                df,
                st.session_state.selected_symbol,
                tf_label,
                theme,
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)


    # =====================================================
    # Signal History + Backtest
    # =====================================================
    col_hist, col_bt = st.columns([3, 2])

    # Signal History
    with col_hist:
        with st.container():
            st.markdown('<div class="tv-card">', unsafe_allow_html=True)
            st.markdown('<div class="tv-title">Signal History</div>', unsafe_allow_html=True)

            if df.empty:
                st.info("Keine Signale verfügbar.")
            else:
                allowed = st.multiselect(
                    "Signale anzeigen:",
                    ["STRONG BUY", "BUY", "SELL", "STRONG SELL"],
                    ["STRONG BUY", "BUY", "SELL", "STRONG SELL"],
                )
                fig_hist = create_signal_history_figure(df, allowed, theme)
                st.plotly_chart(fig_hist, use_container_width=True)

            st.markdown("</div>", unsafe_allow_html=True)

    # Backtest
    with col_bt:
        with st.container():
            st.markdown('<div class="tv-card">', unsafe_allow_html=True)
            st.markdown('<div class="tv-title">Backtest</div>', unsafe_allow_html=True)

            if df.empty:
                st.info("Keine Daten.")
            else:
                horizon = st.slider(
                    "Halte-Dauer (Kerzen)",
                    1, 20,
                    value=st.session_state.backtest_horizon,
                )
                st.session_state.backtest_horizon = horizon

                bt = compute_backtest_trades(df, horizon)
                stats = summarize_backtest(bt)

                if not stats:
                    st.info("Keine Trades.")
                else:
                    st.write(f"**Trades:** {stats['total_trades']}")
                    st.write(f"**Ø Return:** {stats['overall_avg_return']:.2f}%")
                    st.write(f"**Trefferquote:** {stats['overall_hit_rate']:.1f}%")

                    if stats["per_type"]:
                        st.markdown("---")
                        st.caption("Per Signal:")
                        st.table(pd.DataFrame(stats["per_type"]))

            st.markdown("</div>", unsafe_allow_html=True)


    # =====================================================
    # Trades Table + CSV Export
    # =====================================================
    with st.container():
        st.markdown('<div class="tv-card">', unsafe_allow_html=True)
        st.markdown('<div class="tv-title">Backtest Trades</div>', unsafe_allow_html=True)

        bt = compute_backtest_trades(df, st.session_state.backtest_horizon)

        if bt.empty:
            st.info("Noch keine Trades.")
        else:
            df_show = bt.copy()
            df_show["entry_time"] = df_show["entry_time"].dt.strftime("%Y-%m-%d %H:%M")
            df_show["exit_time"] = df_show["exit_time"].dt.strftime("%Y-%m-%d %H:%M")
            df_show["ret_pct"] = df_show["ret_pct"].map(lambda x: f"{x:.2f}")
            df_show["correct"] = df_show["correct"].map(lambda x: "✅" if x else "❌")

            st.dataframe(df_show, use_container_width=True, height=250)

            csv = bt.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 CSV Export",
                csv,
                file_name=f"trades_{st.session_state.selected_symbol}_{tf_label}.csv",
                mime="text/csv",
            )

        st.markdown("</div>", unsafe_allow_html=True)
