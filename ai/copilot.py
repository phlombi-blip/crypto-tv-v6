# ai/copilot.py

import os
import streamlit as st
from openai import OpenAI

# Versuche, den API-Key aus Secrets oder Umgebungsvariablen zu holen
api_key = st.secrets.get("OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")

if not api_key:
    # Hier bewusst eigene, klare Fehlermeldung
    raise RuntimeError(
        "Kein OpenAI API-Key gefunden. "
        "Bitte in Streamlit unter 'Secrets' einen Eintrag "
        'OPENAI_API_KEY = "sk-..." anlegen '
        "oder die Umgebungsvariable OPENAI_API_KEY setzen."
    )

client = OpenAI(api_key=api_key)


def ask_copilot(question, df, symbol, timeframe, last_signal=None):
    """
    KI-CoPilot analysiert den Chart und beantwortet Fragen.
    """
    if df is None or df.empty:
        chart_summary = "Keine Daten verfügbar."
    else:
        chart_summary = (
            f"Last Close: {df['close'].iloc[-1]:.2f}\n"
            f"RSI14: {df['rsi14'].iloc[-1]:.2f}\n"
            f"EMA20: {df['ema20'].iloc[-1]:.2f}\n"
            f"EMA50: {df['ema50'].iloc[-1]:.2f}\n"
            f"MA200: {df['ma200'].iloc[-1]:.2f}\n"
        )

    if last_signal is None:
        last_signal_txt = "Kein explizites Handelssignal übergeben."
    else:
        last_signal_txt = f"Aktuelles Handelssignal des Systems: {last_signal}"

    prompt = f"""
Du bist ein professioneller Trading-Assistent. Analysiere den Chart basierend auf:

Symbol: {symbol}
Timeframe: {timeframe}

Chart-Daten:
{chart_summary}

{last_signal_txt}

User-Frage:
{question}

Gib klare, präzise Hinweise und erkläre den Trading-Kontext (Risiken, Szenarien, kein Finanzrat).
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Du bist ein TradingView-Chart-Experte."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"❌ KI Fehler: {str(e)}"
