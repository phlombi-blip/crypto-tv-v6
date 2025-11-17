import pandas as pd
import streamlit as st

from config import DEFAULT_TIMEFRAME
from ui.layout import apply_theme_css, render_header
from ui.panels import (
    render_watchlist,
    render_chart_panel,
    render_signal_and_backtest,
    render_trades_list,
    render_refresh_footer,
)

# Optional: Auto-Refresh (falls Paket installiert ist)
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


def init_state():
    """
    Initialisiert Streamlit Session-State.
    """
    st.session_state.setdefault("selected_symbol", "BTC")
    st.session_state.setdefault("selected_timeframe", DEFAULT_TIMEFRAME)
    st.session_state.setdefault("theme", "Dark")
    st.session_state.setdefault("backtest_horizon", 5)
    st.session_state.setdefault("backtest_trades", pd.DataFrame())


def main():
    st.set_page_config(
        page_title="Crypto Live Ticker – TradingView Style V5",
        layout="wide",
    )
    init_state()

    # Auto-Refresh (TradingView Feel)
    if st_autorefresh is not None:
        st_autorefresh(interval=60 * 1000, key="refresh")

    # Sidebar: Theme
    st.sidebar.title("⚙️ Einstellungen")
    theme = st.sidebar.radio(
        "Theme",
        ["Dark", "Light"],
        index=0 if st.session_state.theme == "Dark" else 1,
    )
    st.session_state.theme = theme

    apply_theme_css(theme)
    render_header()

    # Layout: Watchlist links, Charts rechts
    col_left, col_right = st.columns([2, 5], gap="medium")

    with col_left:
        render_watchlist()

    with col_right:
        df = render_chart_panel(theme)
        render_signal_and_backtest(df, theme)

        symbol_label = st.session_state.selected_symbol
        tf_label = st.session_state.selected_timeframe
        render_trades_list(symbol_label, tf_label)

        render_refresh_footer()


if __name__ == "__main__":
    main()
