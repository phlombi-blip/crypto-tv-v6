# ui.py
# -*- coding: utf-8 -*-
# Test-UI für Trading-Dashboard mit Streamlit

from __future__ import annotations

import datetime as dt
from typing import Dict, Any, Optional, List

import pandas as pd
import streamlit as st

# --- Externe Module aus deinem Projekt -------------------
# Passe diese Imports ggf. an deine tatsächlichen Dateinamen/Funktionsnamen an

# TODO: hier deine echte Daten-Funktion einhängen
# z.B. from api import get_price_data
#      def get_price_data(symbol, timeframe, limit=500): ...
# ---------------------------------------------------------
try:
    from backtest import backtest_on_signals
except ImportError:
    backtest_on_signals = None  # type: ignore

try:
    from ai.copilot import run_copilot
except ImportError:
    run_copilot = None  # type: ignore

# Wenn du ein separates Auto-Analyse-Modul hast:
# try:
#     from auto_analysis import build_auto_analysis_text
# except ImportError:
#     build_auto_analysis_text = None  # type: ignore


# ---------------------------------------------------------
# Grundkonfiguration der App
# ---------------------------------------------------------
st.set_page_config(
    page_title="CryptoTV – Trading Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# Helper: Dummy-Daten/Stub-Funktionen für Stellen,
#         die du auf dein Projekt mappen musst
# ---------------------------------------------------------

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]  # TODO: anpassen oder dynamisch machen
TIMEFRAMES = {
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def get_price_data(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """
    TODO: Diese Funktion mit deiner echten Datenquelle ersetzen.
    Erwartet Rückgabe eines DataFrames mit mindestens:
        index: DatetimeIndex
        columns: ['open', 'high', 'low', 'close', 'volume']

    Aktuell: Platzhalter, wirft einen Fehler.
    """
    raise NotImplementedError(
        "get_price_data() ist noch nicht mit deiner Datenquelle verbunden. "
        "Bitte in ui.py an deine API / Datenfunktion anpassen."
    )


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    TODO: Hier deine echte Signal-Logik einbinden.
    Erwartung:
        df_in: Candle-Daten
        df_out: DataFrame mit mind. Spalte 'signal' (Werte: BUY, SELL, NONE/HOLD)

    Aktuell: Dummy-Implementation ohne echte Logik.
    """
    df = df.copy()
    if "signal" not in df.columns:
        df["signal"] = "NONE"
    return df


def get_indicator_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    TODO: Hier mit deinen Indikatoren füllen (RSI, EMAs, Bollinger etc.).

    Erwartete Keys (Beispiele!):
        "rsi": float
        "bb_position": str
        "ema20": float
        "ema50": float
        "price": float
    """
    indicators: Dict[str, Any] = {}

    close = df["close"]
    indicators["price"] = float(close.iloc[-1])

    # Dummy-RSI (bitte durch echten RSI ersetzen)
    indicators["rsi"] = 50.0

    # Dummy-BB-Position
    indicators["bb_position"] = "Mitte der Bollinger-Bänder"

    # Dummy-EMAs
    indicators["ema20"] = float(close.ewm(span=20).mean().iloc[-1])
    indicators["ema50"] = float(close.ewm(span=50).mean().iloc[-1])

    return indicators


def get_last_signal_info(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extrahiert das letzte BUY/SELL-Signal aus df['signal'].
    Erwartet, dass compute_signals() diese Spalte gefüllt hat.
    """
    if "signal" not in df.columns:
        return {}

    sig_series = df["signal"].astype(str).str.upper()
    idx = sig_series[(sig_series == "BUY") | (sig_series == "SELL")].last_valid_index()

    if idx is None:
        return {}

    sig = sig_series.loc[idx]
    age_bars = len(df) - df.index.get_loc(idx) - 1

    return {
        "signal": sig,
        "age_bars": int(age_bars),
        "context": f"Letztes klar definiertes {sig}-Signal vor {age_bars} Kerzen.",
    }


def run_auto_analysis(df: pd.DataFrame, symbol: str, tf_label: str) -> str:
    """
    Auto-Analyse (regelbasiert) – falls du schon eine eigene Logik hast,
    kannst du diese hier einfach aufrufen.
    """
    # TODO: Hier deine bestehende Auto-Analyse-Funktion einbinden
    # z.B.:
    # from auto_analysis import build_auto_analysis_text
    # return build_auto_analysis_text(df, symbol, tf_label)

    close = df["close"]
    last_price = float(close.iloc[-1])
    first_price = float(close.iloc[0])
    change_pct = (last_price / first_price - 1.0) * 100.0

    if change_pct > 5:
        trend_desc = "über den betrachteten Zeitraum klar aufwärtsgerichtet."
    elif change_pct < -5:
        trend_desc = "über den betrachteten Zeitraum klar abwärtsgerichtet."
    else:
        trend_desc = "eher seitwärts / ohne klaren Trend."

    txt = []
    txt.append(f"{symbol} ({tf_label}) – Automatische Chart-Analyse")
    txt.append("")
    txt.append(f"- Kursveränderung im aktuellen Fenster: {change_pct:.1f} %")
    txt.append(f"- Trend-Eindruck: {trend_desc}")
    txt.append("- Volatilität: grob normal (Dummy – bitte später verfeinern)")
    txt.append("")
    txt.append(
        "Kurzfazit: Dies ist eine automatische technische Einschätzung und keine "
        "Finanzberatung."
    )

    return "\n".join(txt)


# ---------------------------------------------------------
# Backtest-Wrapper für BUY/SELL-Signale
# ---------------------------------------------------------


def run_backtest_buy_sell(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Wrapper um backtest_on_signals() aus backtest.py.

    Erwartet:
        df['close']
        df['signal'] mit Werten BUY/SELL/NONE/HOLD

    Gibt ein Dict zurück mit:
        {
            "trades": [...],
            "equity_curve": pd.Series,
            "stats": {...}
        }
    """
    if backtest_on_signals is None:
        st.warning(
            "⚠️ backtest_on_signals konnte nicht importiert werden. "
            "Bitte prüfe backtest.py und den Import in ui.py."
        )
        return None

    if "signal" not in df.columns:
        st.warning("⚠️ Keine 'signal'-Spalte gefunden. Backtest nicht möglich.")
        return None

    try:
        result = backtest_on_signals(df=df, price_col="close", signal_col="signal")
    except Exception as e:
        st.error(f"Fehler im Backtest: {e}")
        return None

    return result


# ---------------------------------------------------------
# KI-CoPilot Wrapper
# ---------------------------------------------------------


def run_copilot_for_view(
    symbol: str,
    tf_label: str,
    df: pd.DataFrame,
    backtest_result: Optional[Dict[str, Any]],
) -> str:
    """
    Wandelt die Daten in ein Format, das run_copilot erwartet.
    """
    if run_copilot is None:
        return (
            "⚠️ KI-CoPilot ist nicht verfügbar (Import fehlgeschlagen). "
            "Bitte prüfe ai/copilot.py und den Import in ui.py."
        )

    indicators = get_indicator_summary(df)
    last_sig_info = get_last_signal_info(df)
    bt_stats = backtest_result["stats"] if backtest_result is not None else None

    try:
        text = run_copilot(
            symbol=symbol,
            timeframe_label=tf_label,
            price_df=df,
            indicators=indicators,
            last_signals=last_sig_info,
            backtest_stats=bt_stats,
        )
    except Exception as e:
        text = f"⚠️ Fehler bei Groq / KI-CoPilot: {e}"

    return text


# ---------------------------------------------------------
# UI-Layout
# ---------------------------------------------------------


def main() -> None:
    st.title("📺 CryptoTV – Trading Dashboard")

    # -------- Sidebar: Auswahl & Einstellungen ----------
    with st.sidebar:
        st.header("⚙️ Einstellungen")

        symbol = st.selectbox("Symbol", DEFAULT_SYMBOLS, index=0)
        tf_key_list = list(TIMEFRAMES.keys())
        tf_label = st.selectbox("Timeframe", tf_key_list, index=tf_key_list.index("1d"))
        timeframe = TIMEFRAMES[tf_label]

        st.markdown("---")
        st.subheader("Backtest")
        initial_capital = st.number_input(
            "Startkapital",
            min_value=100.0,
            max_value=1_000_000.0,
            value=1000.0,
            step=100.0,
        )

        st.markdown("---")
        st.subheader("Benachrichtigungen (optional)")
        enable_email = st.checkbox("E-Mail-Alerts aktivieren", value=False)
        email_address = ""
        if enable_email:
            email_address = st.text_input("E-Mail-Adresse", value="")

    # -------- Daten laden ----------
    try:
        df_raw = get_price_data(symbol=symbol, timeframe=timeframe, limit=500)
    except NotImplementedError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
        st.stop()

    if df_raw.empty:
        st.warning("Keine Daten geladen.")
        st.stop()

    # Sicherstellen, dass index Datetime ist
    if not isinstance(df_raw.index, pd.DatetimeIndex):
        try:
            df_raw = df_raw.copy()
            df_raw.index = pd.to_datetime(df_raw.index)
        except Exception:
            st.error("Konnte Index nicht in DatetimeIndex umwandeln.")
            st.stop()

    # Signale berechnen
    df = compute_signals(df_raw)

    # -------- Tabs ----------
    tab_chart, tab_backtest, tab_settings = st.tabs(
        ["📊 Chart & KI", "📈 Backtest", "🔧 Einstellungen"]
    )

    # -----------------------------------------------------
    # TAB 1: Chart & KI
    # -----------------------------------------------------
    with tab_chart:
        col_chart, col_right = st.columns([2, 1])

        with col_chart:
            st.subheader(f"{symbol} – {tf_label} Chart")

            # TODO: Hier deinen echten Chart zeichnen
            # z.B. mit Plotly / mplfinance / altair
            st.line_chart(df["close"])

        with col_right:
            auto_key = f"auto_analysis_{symbol}_{tf_label}"
            copilot_key = f"copilot_{symbol}_{tf_label}"

            # --- Auto-Analyse (regelbasiert) ---
            st.subheader("🔍 Automatische Analyse")

            if st.button(
                "🔄 Analyse aktualisieren",
                key=f"btn_reanalyse_{symbol}_{tf_label}",
            ):
                auto_text = run_auto_analysis(df, symbol, tf_label)
                st.session_state[auto_key] = auto_text

            auto_text = st.session_state.get(
                auto_key, "Noch keine Analyse verfügbar."
            )
            st.write(auto_text)

            st.markdown("---")

            # --- KI-CoPilot ---
            st.subheader("🤖 KI-CoPilot – Was sagt das Chart?")

            if st.button(
                "💡 KI-Analyse starten",
                key=f"btn_copilot_{symbol}_{tf_label}",
            ):
                # Für die KI gerne auf letzten Teil des Charts begrenzen
                df_for_ki = df.copy()
                if len(df_for_ki) > 200:
                    df_for_ki = df_for_ki.iloc[-200:]

                bt_result_for_ki = run_backtest_buy_sell(df_for_ki)
                copilot_text = run_copilot_for_view(
                    symbol=symbol,
                    tf_label=tf_label,
                    df=df_for_ki,
                    backtest_result=bt_result_for_ki,
                )
                st.session_state[copilot_key] = copilot_text

            copilot_text = st.session_state.get(
                copilot_key, "Noch keine KI-Analyse verfügbar."
            )
            st.write(copilot_text)

            st.markdown("---")

            # --- Backtest-Kurzfassung im rechten Panel ---
            st.subheader("📈 Backtest (BUY/SELL – Kurzfassung)")
            bt_result = run_backtest_buy_sell(df)
            if bt_result is not None:
                stats = bt_result["stats"]
                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "Total Return",
                    f"{stats['total_return_pct']:.1f} %",
                )
                c2.metric(
                    "Win-Rate",
                    f"{stats['win_rate_pct']:.1f} %",
                )
                c3.metric(
                    "Max Drawdown",
                    f"{stats['max_drawdown_pct']:.1f} %",
                )
            else:
                st.caption("Keine Backtest-Daten verfügbar.")

    # -----------------------------------------------------
    # TAB 2: Backtest-Details
    # -----------------------------------------------------
    with tab_backtest:
        st.subheader(f"📈 Backtest-Details – {symbol} ({tf_label})")

        bt_result = run_backtest_buy_sell(df)
        if bt_result is None:
            st.info("Noch kein Backtest verfügbar.")
        else:
            stats = bt_result["stats"]
            trades = bt_result["trades"]
            equity_curve = bt_result["equity_curve"]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Initial Capital", f"{stats['initial_capital']:.2f}")
            c2.metric("Final Equity", f"{stats['final_equity']:.2f}")
            c3.metric("Total Return", f"{stats['total_return_pct']:.1f} %")
            c4.metric("Win-Rate", f"{stats['win_rate_pct']:.1f} %")

            st.markdown("---")
            st.markdown("### Equity-Curve")
            st.line_chart(equity_curve)

            st.markdown("### Trades")

            if len(trades) == 0:
                st.caption("Keine Trades im Backtest.")
            else:
                trades_data: List[Dict[str, Any]] = []
                for t in trades:
                    trades_data.append(
                        {
                            "Entry Time": t.entry_time,
                            "Exit Time": t.exit_time,
                            "Entry Price": t.entry_price,
                            "Exit Price": t.exit_price,
                            "Return %": t.return_pct,
                            "Bars Held": t.bars_held,
                        }
                    )
                trades_df = pd.DataFrame(trades_data)
                st.dataframe(trades_df, use_container_width=True)

    # -----------------------------------------------------
    # TAB 3: Einstellungen / Infos
    # -----------------------------------------------------
    with tab_settings:
        st.subheader("🔧 Projekt-Einstellungen & Hinweise")

        st.markdown(
            """
        - Dieses UI ist als strukturierter Rahmen gedacht.
        - Wichtige TODO-Stellen sind im Code markiert:
          - `get_price_data()` → deine echte Datenquelle
          - `compute_signals()` → deine echte Signal-Logik (BUY/SELL)
          - `get_indicator_summary()` → echte Indikatoren (RSI, EMA, Bollinger, ...)
          - `run_auto_analysis()` → dein regelbasierter Analyse-Text
        - KI-CoPilot nutzt `ai/copilot.py` und bekommt:
          - komprimierte Chart-Daten
          - Indikator-Summary
          - letzte BUY/SELL-Signale
          - Backtest-Stats (falls vorhanden)
        """
        )

        if enable_email:
            st.markdown("---")
            st.subheader("E-Mail-Alerts (Platzhalter)")
            st.caption(
                "Hier kannst du später deine Email-Notifier-Logik einbinden, "
                "z.B. über email_notifier.py, wenn ein neues Signal entsteht."
            )
            st.write(f"Aktueller Alert-Empfänger: `{email_address or 'nicht gesetzt'}`")


# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    main()
