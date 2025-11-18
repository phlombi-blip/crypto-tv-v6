# ai/copilot.py
# -*- coding: utf-8 -*-

import os
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
from groq import Groq


# ------------------------------------------------------------------
# API-Client
# ------------------------------------------------------------------
def _get_api_key() -> Optional[str]:
    """Liest den Groq API-Key aus Streamlit-Secrets oder Umgebungsvariablen."""
    key = None

    try:
        key = st.secrets.get("GROQ_API_KEY", None)
    except Exception:
        key = None

    if not key:
        key = os.getenv("GROQ_API_KEY")

    return key


_api_key = _get_api_key()
_client: Optional[Groq]

if not _api_key:
    st.warning(
        "⚠️ Kein Groq API-Key gefunden. "
        "Bitte in Streamlit unter 'Secrets' einen Eintrag "
        "`GROQ_API_KEY = \"gsk_…\"` anlegen oder die Umgebungsvariable "
        "`GROQ_API_KEY` setzen."
    )
    _client = None
else:
    _client = Groq(api_key=_api_key)


# ------------------------------------------------------------------
# Kompakte Chart-Zusammenfassung – OHNE riesige Tabellen
# ------------------------------------------------------------------
def _build_chart_summary(df: pd.DataFrame, lookback: int = 150) -> str:
    """
    Erzeugt eine extrem kompakte, numerische Zusammenfassung des Charts,
    damit die Groq-Requests garantiert klein bleiben.
    Keine Tabellen, keine Zeilenlisten – nur Aggregate.
    """
    if df is None or df.empty:
        return "Keine Marktdaten vorhanden."

    # Nur die letzten N Kerzen für die Statistik
    df_tail = df.tail(lookback).copy()

    close = df_tail["close"]
    rsi = df_tail["rsi14"] if "rsi14" in df_tail.columns else None
    vol = df_tail["volume"] if "volume" in df_tail.columns else None
    sig = df_tail["signal"] if "signal" in df_tail.columns else None

    last_close = float(close.iloc[-1])
    first_close = float(close.iloc[0])
    change_pct = (last_close - first_close) / first_close * 100 if first_close != 0 else 0.0

    if rsi is not None and not rsi.isna().all():
        rsi_now = float(rsi.iloc[-1])
        rsi_min = float(rsi.min())
        rsi_max = float(rsi.max())
        rsi_avg = float(rsi.mean())
    else:
        rsi_now = rsi_min = rsi_max = rsi_avg = None

    if vol is not None and not vol.isna().all():
        vol_avg = float(vol.mean())
        vol_max = float(vol.max())
    else:
        vol_avg = vol_max = None

    sig_counts = {}
    if sig is not None:
        sig_counts = sig.value_counts().to_dict()

    # grob: Trendbeschreibung
    if change_pct > 5:
        trend = "klar aufwärts (Bullentrend)"
    elif change_pct < -5:
        trend = "klar abwärts (Bärentrend)"
    elif abs(change_pct) <= 1:
        trend = "seitwärts / Range"
    else:
        trend = "leichter Trend, aber nicht extrem"

    lines = [
        f"Betrachteter Zeitraum: letzte {len(df_tail)} Kerzen.",
        f"Aktueller Schlusskurs: {last_close:.2f} USD.",
        f"Veränderung über diesen Zeitraum: {change_pct:.2f} % → {trend}",
    ]

    if rsi_now is not None:
        lines.append(
            f"RSI(14): aktuell {rsi_now:.1f}, Minimum {rsi_min:.1f}, Maximum {rsi_max:.1f}, "
            f"Durchschnitt {rsi_avg:.1f}."
        )
    else:
        lines.append("RSI(14) ist nicht verfügbar.")

    if vol_avg is not None:
        lines.append(
            f"Volumen: Durchschnitt {vol_avg:.2f}, Spitze (max) {vol_max:.2f}."
        )

    if sig_counts:
        parts = [f"{k}: {v}" for k, v in sig_counts.items()]
        lines.append("Verteilung der Handelssignale im Zeitraum: " + ", ".join(parts))

    return "\n".join(lines)


# ------------------------------------------------------------------
# Hauptfunktion für ui.py
# ------------------------------------------------------------------
def ask_copilot(
    question: str,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    last_signal: Optional[str] = None,
) -> str:
    """
    Fragt den KI-CoPilot (Groq / Llama 3) mit sehr kleinem Chart-Kontext.
    """
    if not question or not str(question).strip():
        return "Bitte zuerst eine Frage eingeben."

    if _client is None:
        return (
            "❌ KI Fehler: Kein Groq API-Key konfiguriert.\n\n"
            "Bitte `GROQ_API_KEY` in den Streamlit Secrets oder als "
            "Umgebungsvariable setzen."
        )

    chart_summary = _build_chart_summary(df, lookback=150)
    last_signal_txt = (
        f"Letztes Handelssignal laut System: {last_signal}"
        if last_signal
        else "Kein explizites Handelssignal vorhanden."
    )

    system_prompt = (
        "Du bist ein erfahrener technischer Analyst für Kryptowährungen. "
        "Du interpretierst Candlestick-Charts mit RSI, Volumen und Handelssignalen. "
        "Du gibst KEINE Anlageberatung und triffst keine konkreten Trading-Entscheidungen, "
        "sondern erklärst Setups, mögliche Szenarien und Risiken."
    )

    user_prompt = f"""
Instrument: {symbol}
Timeframe: {timeframe}

{last_signal_txt}

Kompakte Marktzusammenfassung:
{chart_summary}

Frage des Nutzers:
{question}

Bitte:
- Beschreibe das aktuelle Setup kurz und verständlich.
- Gehe auf Trend, Momentum, Volumen und grobe Risiko-Szenarien ein.
- Nenne sowohl mögliche bullische als auch bärische Varianten.
- Weise explizit darauf hin, dass es keine Finanzberatung ist.
"""

    try:
        resp = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=320,   # auch hier klein halten
        )
        answer = resp.choices[0].message.content or ""
        return answer.strip()
    except Exception as e:
        return f"❌ KI Fehler (Groq): {e}"
