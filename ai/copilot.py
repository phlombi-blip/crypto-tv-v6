# ai/copilot.py
# -*- coding: utf-8 -*-

import os
from typing import Optional

import pandas as pd
import streamlit as st
from groq import Groq


def _get_api_key() -> Optional[str]:
    """Liest den Groq API-Key aus Streamlit-Secrets oder Umgebungsvariablen."""
    key = None

    # 1) Streamlit Secrets
    try:
        key = st.secrets.get("GROQ_API_KEY", None)
    except Exception:
        key = None

    # 2) Fallback: Umgebungsvariable
    if not key:
        key = os.getenv("GROQ_API_KEY")

    return key


_api_key = _get_api_key()
_client: Optional[Groq]

if not _api_key:
    # Kein harter Fehler – App läuft weiter, KI ist nur deaktiviert
    st.warning(
        "⚠️ Kein Groq API-Key gefunden. "
        "Bitte in Streamlit unter 'Secrets' einen Eintrag "
        "`GROQ_API_KEY = \"gsk_…\"` anlegen oder die Umgebungsvariable "
        "`GROQ_API_KEY` setzen."
    )
    _client = None
else:
    _client = Groq(api_key=_api_key)


def _build_chart_summary(df: pd.DataFrame, max_rows: int = 300) -> str:
    """
    Kompakte textuelle Zusammenfassung der letzten Candles für den KI-Context.
    """
    if df is None or df.empty:
        return "Keine Candles vorhanden."

    df_tail = df.tail(max_rows).copy()

    cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ema20",
        "ema50",
        "ma200",
        "bb_mid",
        "bb_up",
        "bb_lo",
        "rsi14",
        "signal",
    ]
    use_cols = [c for c in cols if c in df_tail.columns]
    if not use_cols:
        return "Candles ohne Indikatoren – nur Preise verfügbar."

    df_tail = df_tail[use_cols]
    return df_tail.to_string(max_rows=max_rows)


def ask_copilot(
    question: str,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    last_signal: Optional[str] = None,
) -> str:
    """
    Fragt den KI-CoPilot (Groq / Llama 3) mit Chart-Kontext.
    Wird von ui.py aufgerufen.
    """
    if not question or not str(question).strip():
        return "Bitte zuerst eine Frage eingeben."

    if _client is None:
        return (
            "❌ KI Fehler: Kein Groq API-Key konfiguriert.\n\n"
            "Bitte `GROQ_API_KEY` in den Streamlit Secrets oder als "
            "Umgebungsvariable setzen."
        )

    chart_summary = _build_chart_summary(df)
    last_signal_txt = (
        f"Letztes Handelssignal laut System: {last_signal}"
        if last_signal
        else "Kein explizites Handelssignal vorhanden."
    )

    system_prompt = (
        "Du bist ein erfahrener TradingView-Chart-Analyst für Kryptowährungen. "
        "Du arbeitest mit Candlesticks, Volumen, RSI, EMA20/EMA50, MA200 "
        "und Bollinger-Bändern. "
        "Du gibst KEINE Anlageberatung, sondern erklärst Setups, Risiken und "
        "mögliche Szenarien verständlich."
    )

    user_prompt = f"""
Instrument: {symbol}
Timeframe: {timeframe}

{last_signal_txt}

Chartdaten (letzte Candles + Indikatoren):
{chart_summary}

User-Frage:
{question}

Bitte:
- Beschreibe das aktuelle Setup kurz aber präzise.
- Gehe auf Trend, Momentum, Volumen und wichtige Zonen/Levels ein.
- Nenne mögliche bullische UND bärische Szenarien.
- Erwähne immer, dass es keine Finanzberatung ist.
"""

    try:
        resp = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=400,
        )
        answer = resp.choices[0].message.content or ""
        return answer.strip()
    except Exception as e:
        return f"❌ KI Fehler (Groq): {e}"
