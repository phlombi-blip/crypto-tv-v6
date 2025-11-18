# ai/copilot.py
"""
KI-CoPilot für die Trading-View-App.

Diese Version nutzt die kostenlose Groq-API.
Erwartet einen API-Key in

  - Streamlit Secrets: st.secrets["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"]
    oder
  - Umgebungsvariable: GROQ_API_KEY

Hinweis:
- Du brauchst einen Account unter https://console.groq.com
- Dort einen API-Key erstellen und in Streamlit Cloud unter "Secrets" hinterlegen.
"""

import os
from typing import Optional

import pandas as pd
import streamlit as st
from groq import Groq


def _get_api_key() -> Optional[str]:
    """Liest den Groq API-Key aus Secrets/Env."""
    # st.secrets.get(...) ist robust, wenn Key fehlt
    key = None
    try:
        key = st.secrets.get("GROQ_API_KEY", None)
    except Exception:
        key = None

    return key or os.getenv("GROQ_API_KEY")


_api_key = _get_api_key()
if not _api_key:
    # Bewusst klare Meldung – die App läuft trotzdem weiter,
    # aber der CoPilot wird einen Fehlertext zurückgeben.
    st.warning(
        "⚠️ Kein Groq API-Key gefunden. "
        "Bitte in Streamlit unter 'Secrets' einen Eintrag `GROQ_API_KEY = "gsk_..."` anlegen "
        "oder die Umgebungsvariable GROQ_API_KEY setzen."
    )
    _client: Optional[Groq] = None
else:
    _client = Groq(api_key=_api_key)


def _build_chart_summary(df: Optional[pd.DataFrame]) -> str:
    """Extrahiert ein paar Kennzahlen aus dem DataFrame für den Prompt."""
    if df is None or df.empty:
        return "Keine Daten verfügbar."

    last = df.iloc[-1]

    def get(col, fmt="{:.2f}"):
        if col not in df.columns:
            return "n/a"
        try:
            return fmt.format(float(last[col]))
        except Exception:
            return "n/a"

    parts = [
        f"Letzter Schlusskurs: {get('close')} USD",
        f"RSI14: {get('rsi14')}",
        f"EMA20: {get('ema20')}",
        f"EMA50: {get('ema50')}",
        f"MA200: {get('ma200')}",
        f"Bollinger-Oberband: {get('bb_up')}",
        f"Bollinger-Unterband: {get('bb_low')}",
    ]
    return "\n".join(parts)


def ask_copilot(question, df, symbol, timeframe, last_signal=None):
    """
    KI-CoPilot analysiert den Chart und beantwortet Fragen (über Groq / Llama 3).

    Parameters
    ----------
    question : str
        User-Frage aus dem UI.
    df : pd.DataFrame
        Chart-Daten mit Indikatoren.
    symbol : str
        Symbol-Bezeichnung (z.B. BTCUSD).
    timeframe : str
        Timeframe-Label (z.B. 1h, 4h, 1d).
    last_signal : str | None
        Letztes Handelssignal (BUY/SELL/...), falls vorhanden.
    """
    if not question or not str(question).strip():
        return "Bitte zuerst eine Frage eingeben."

    if _client is None:
        return (
            "❌ KI Fehler: Kein Groq API-Key konfiguriert. "
            "Bitte `GROQ_API_KEY` in Streamlit Secrets oder als Umgebungsvariable setzen."
        )

    chart_summary = _build_chart_summary(df)
    last_signal_txt = (
        f"Letztes Handelssignal: {last_signal}"
        if last_signal
        else "Kein explizites Handelssignal vorhanden."
    )

    system_prompt = (
        "Du bist ein erfahrener TradingView-Chart-Experte für Kryptowährungen. "
        "Du arbeitest mit Candlestick-Charts, RSI, EMAs, MA200, Bollinger-Bändern "
        "und Volumen. Du gibst keine Anlageberatung, sondern erklärst Setups, "
        "Risiken und mögliche Szenarien so, dass auch fortgeschrittene Einsteiger "
        "es verstehen."
    )

    user_prompt = f"""
Instrument: {symbol}
Timeframe: {timeframe}

Chart-Daten:
{chart_summary}

{last_signal_txt}

User-Frage:
{question}

Bitte:
- Beschreibe das aktuelle Setup knapp aber präzise.
- Gehe auf Trend, Momentum, Volumen und wichtige Levels ein.
- Nenne mögliche bullische UND bärische Szenarien.
- Erinnere stets daran, dass es keine Finanzberatung ist.
"""

    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ KI Fehler (Groq): {str(e)}"
