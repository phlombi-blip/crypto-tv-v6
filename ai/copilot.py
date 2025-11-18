# ai/copilot.py

"""
KI-CoPilot auf Basis von Groq (statt OpenAI).
Die Schnittstelle (ask_copilot) bleibt unverändert, damit ui.py
ohne Änderungen weiter funktioniert.
"""

import pandas as pd
import streamlit as st

from .llm import groq_chat


def ask_copilot(question, df, symbol, timeframe, last_signal=None):
    """
    KI-CoPilot analysiert den Chart und beantwortet Fragen.

    Parameters
    ----------
    question : str
        Nutzerfrage.
    df : pd.DataFrame
        DataFrame mit mindestens den Spalten close, rsi14, ema20, ema50, ma200.
    symbol : str
        Symbol-Label (z.B. 'BTC/USD').
    timeframe : str
        Timeframe-Label (z.B. '1h').
    last_signal : str | None
        Optional letztes Handelssignal des Systems.
    """
    if df is None or df.empty:
        chart_summary = "Keine Daten verfügbar."
    else:
        def _val(col):
            try:
                return float(df[col].iloc[-1])
            except Exception:
                return float("nan")

        last_close = _val("close")
        rsi14 = _val("rsi14")
        ema20 = _val("ema20")
        ema50 = _val("ema50")
        ma200 = _val("ma200")

        chart_summary = (
            f"Last Close: {last_close:.2f}\n"
            f"RSI14: {rsi14:.2f}\n"
            f"EMA20: {ema20:.2f}\n"
            f"EMA50: {ema50:.2f}\n"
            f"MA200: {ma200:.2f}\n"
        )

    if not last_signal:
        last_signal_txt = "Kein explizites Handelssignal übergeben."
    else:
        last_signal_txt = f"Aktuelles Handelssignal des Systems: {last_signal}"

    prompt = f"""
Du bist ein professioneller Trading-Assistent. Analysiere den Chart basierend auf:

Symbol: {symbol}
Timeframe: {timeframe}

Chart-Zusammenfassung:
{chart_summary}

{last_signal_txt}

User-Frage:
{question}

Gib klare, präzise Hinweise und erkläre den Trading-Kontext (Risiken, Szenarien, kein Finanzrat).
"""

    try:
        answer = groq_chat(
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein TradingView-Chart-Experte.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            max_completion_tokens=400,
        )
        return answer
    except Exception as e:
        st.error(f"Fehler beim Aufruf des KI-Modells (Groq): {e}")
        return f"❌ KI Fehler: {e}"
