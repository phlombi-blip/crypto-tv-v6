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
    Erzeugt eine extrem kompakte, TA-orientierte Zusammenfassung des Charts
    basierend auf den letzten N Kerzen.
    Nutzt Close, RSI(14), EMA20/EMA50, MA200, Bollinger-Bänder und grobe
    Candlestick-Verteilung – aber nur aggregiert, ohne lange Tabellen.
    """
    if df is None or df.empty:
        return "Keine Marktdaten vorhanden."

    df_tail = df.tail(lookback).copy()

    close = df_tail["close"]
    last_close = float(close.iloc[-1])
    first_close = float(close.iloc[0])
    change_pct = (last_close - first_close) / first_close * 100 if first_close != 0 else 0.0

    # RSI
    rsi = df_tail["rsi14"] if "rsi14" in df_tail.columns else None
    if rsi is not None and not rsi.isna().all():
        rsi_now = float(rsi.iloc[-1])
        rsi_min = float(rsi.min())
        rsi_max = float(rsi.max())
        rsi_avg = float(rsi.mean())
        rsi_oversold = int((rsi < 30).sum())
        rsi_overbought = int((rsi > 70).sum())
    else:
        rsi_now = rsi_min = rsi_max = rsi_avg = None
        rsi_oversold = rsi_overbought = 0

    # EMA / MA
    ema20 = df_tail["ema20"] if "ema20" in df_tail.columns else None
    ema50 = df_tail["ema50"] if "ema50" in df_tail.columns else None
    ma200 = df_tail["ma200"] if "ma200" in df_tail.columns else None

    last_ema20 = float(ema20.iloc[-1]) if ema20 is not None and not ema20.isna().all() else None
    last_ema50 = float(ema50.iloc[-1]) if ema50 is not None and not ema50.isna().all() else None
    last_ma200 = float(ma200.iloc[-1]) if ma200 is not None and not ma200.isna().all() else None

    # Bollinger
    bb_up = df_tail["bb_up"] if "bb_up" in df_tail.columns else None
    bb_lo = df_tail["bb_lo"] if "bb_lo" in df_tail.columns else None
    bb_mid = df_tail["bb_mid"] if "bb_mid" in df_tail.columns else None

    if (
        bb_up is not None
        and bb_lo is not None
        and not bb_up.isna().all()
        and not bb_lo.isna().all()
    ):
        last_bb_up = float(bb_up.iloc[-1])
        last_bb_lo = float(bb_lo.iloc[-1])
        last_bb_mid = float(bb_mid.iloc[-1]) if bb_mid is not None else (last_bb_up + last_bb_lo) / 2
        band_width = (last_bb_up - last_bb_lo) / last_bb_mid if last_bb_mid != 0 else 0.0
    else:
        last_bb_up = last_bb_lo = last_bb_mid = band_width = None

    # Volumen
    vol = df_tail["volume"] if "volume" in df_tail.columns else None
    if vol is not None and not vol.isna().all():
        vol_avg = float(vol.mean())
        vol_max = float(vol.max())
    else:
        vol_avg = vol_max = None

    # Candle-Verteilung (bullish / bearish)
    opens = df_tail["open"]
    bulls = int((df_tail["close"] > opens).sum())
    bears = int((df_tail["close"] < opens).sum())
    neutrals = int((df_tail["close"] == opens).sum())

    # grobe Trendbeschreibung
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
        f"Candlestick-Verteilung: {bulls} bullische, {bears} bärische, {neutrals} neutrale Kerzen.",
    ]

    if rsi_now is not None:
        lines.append(
            f"RSI(14): aktuell {rsi_now:.1f}, Minimum {rsi_min:.1f}, Maximum {rsi_max:.1f}, "
            f"Durchschnitt {rsi_avg:.1f}, "
            f"{rsi_oversold}x unter 30 (überverkauft), {rsi_overbought}x über 70 (überkauft)."
        )
    else:
        lines.append("RSI(14) ist nicht verfügbar.")

    if last_ema20 is not None and last_ema50 is not None:
        rel_20 = "über" if last_close > last_ema20 else "unter"
        rel_50 = "über" if last_close > last_ema50 else "unter"
        cross = "EMA20 über EMA50" if last_ema20 > last_ema50 else "EMA20 unter EMA50"
        lines.append(
            f"EMA20/EMA50: Kurs liegt {rel_20} EMA20 und {rel_50} EMA50, "
            f"Aktueller Zustand der EMAs: {cross}."
        )

    if last_ma200 is not None:
        rel_200 = "über" if last_close > last_ma200 else "unter"
        lines.append(f"MA200: Kurs liegt {rel_200} der MA200 ({last_ma200:.2f}).")

    if last_bb_up is not None and last_bb_lo is not None:
        pos = "mittig im Band"
        if last_close >= last_bb_up:
            pos = "am oder über dem oberen Band"
        elif last_close <= last_bb_lo:
            pos = "am oder unter dem unteren Band"
        lines.append(
            f"Bollinger-Bänder(20): Kurs liegt {pos}. Bandbreite relativ: {band_width:.3f}."
        )

    if vol_avg is not None:
        lines.append(
            f"Volumen: Durchschnitt {vol_avg:.2f}, Spitze (max) {vol_max:.2f}."
        )

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
        "Du interpretierst explizit RSI(14), EMA20, EMA50, MA200, Bollinger-Bänder "
        "und Candlestick-Strukturen (Trend, Pullbacks, Übertreibungen). "
        "Du gibst KEINE Anlageberatung und triffst keine konkreten Trading-Entscheidungen, "
        "sondern erklärst Setups, mögliche Szenarien und Risiken und gibst Empfehlungen."
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
            max_completion_tokens=480,  # etwas mehr Raum für die Analyse
        )
        answer = resp.choices[0].message.content or ""
        return answer.strip()
    except Exception as e:
        return f"❌ KI Fehler (Groq): {e}"
