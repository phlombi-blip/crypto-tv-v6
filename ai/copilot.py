# ai/copilot.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st
from groq import Groq


@st.cache_resource
def get_groq_client() -> Optional[Groq]:
    """
    Holt einmalig Groq-Client aus Streamlit-Secrets oder Umgebungsvariablen.
    """
    api_key = None

    # 1) Streamlit Secrets
    try:
        api_key = st.secrets["groq"]["api_key"]
    except Exception:
        pass

    # 2) Fallback: Env
    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return None

    return Groq(api_key=api_key)


SYSTEM_PROMPT = """
Du bist ein erfahrener technischer Krypto-Trader.

Aufgabe:
- Analysiere das gegebene Chart- und Indikator-Summary.
- Erkläre verständlich, was das Chart aktuell „erzählt“.
- Nutze bekannte Chartmuster (z.B. Double Top/Bottom, Head & Shoulders, Cup & Handle, Dreiecke, Channels),
  wenn sie zur Beschreibung passen – aber spekuliere nicht wild.
- Beurteile grob das Chance/Risiko-Verhältnis für Swing-Trades (kein Scalp).
- Beschreibe mögliche Szenarien für die nächsten Tage/Wochen (bullische/bärische/seitwärtige Varianten).
- Formuliere KEINE konkreten Trading-Empfehlungen, sondern Szenarien & Levels, auf die man achten könnte.

WICHTIG:
- Sei ehrlich, wenn das Bild gemischt oder unklar ist.
- Nenne Unsicherheiten oder widersprüchliche Signale explizit.
- Kein Finanz- oder Anlageberatung – immer nur technische Einschätzung des Charts.
"""


def build_chart_summary(
    price_df: pd.DataFrame,
    indicators: Dict[str, Any],
    last_signals: Dict[str, Any],
    backtest_stats: Optional[Dict[str, Any]] = None,
    max_bars: int = 200,
) -> str:
    """
    Baut einen kompakten Text-Summary des Charts.
    price_df: erwartet Spalten wie 'close', optional 'high', 'low'
    indicators: z.B. {"rsi": 62, "bb_position": "oberes Band", ...}
    last_signals: z.B. {"signal": "BUY", "age_bars": 3}
    backtest_stats: optional Stats aus dem Backtest.
    """
    if len(price_df) > max_bars:
        df = price_df.iloc[-max_bars:].copy()
    else:
        df = price_df.copy()

    close = df["close"]
    last_price = float(close.iloc[-1])
    first_price = float(close.iloc[0])
    change_pct = (last_price / first_price - 1.0) * 100.0

    # Grober Trend
    if change_pct > 10:
        trend_desc = "klarer Aufwärtstrend über die betrachteten Kerzen"
    elif change_pct < -10:
        trend_desc = "klarer Abwärtstrend über die betrachteten Kerzen"
    elif abs(change_pct) < 3:
        trend_desc = "weitgehend seitwärts (Range-Markt)"
    else:
        trend_desc = "moderater Trend, nicht extrem stark ausgeprägt"

    # Volatilität grob
    if "high" in df.columns and "low" in df.columns:
        intraday_ranges = (df["high"] - df["low"]) / df["close"]
        vol = float(intraday_ranges.mean() * 100.0)
    else:
        # Fallback: Close-to-Close
        returns = close.pct_change().dropna()
        vol = float(returns.std() * (len(returns) ** 0.5) * 100.0)

    if vol > 8:
        vol_desc = "sehr hohe Volatilität"
    elif vol > 4:
        vol_desc = "erhöhte Volatilität"
    else:
        vol_desc = "relativ ruhige Volatilität"

    indicator_lines = []
    if "rsi" in indicators:
        indicator_lines.append(f"- RSI: {indicators['rsi']:.1f}")
    if "bb_position" in indicators:
        indicator_lines.append(f"- Position vs. Bollinger-Bändern: {indicators['bb_position']}")
    if "ema20" in indicators and "ema50" in indicators and "price" in indicators:
        ema_trend = (
            "bullischer Crossover (EMA20 > EMA50)"
            if indicators["ema20"] > indicators["ema50"]
            else "bearischer Crossover (EMA20 < EMA50)"
        )
        above_ema = "oberhalb der EMAs" if indicators["price"] > indicators["ema20"] else "unterhalb der EMAs"
        indicator_lines.append(f"- EMAs: {ema_trend}, Kurs aktuell {above_ema}")

    signal_lines = []
    if last_signals:
        sig = last_signals.get("signal")
        age = last_signals.get("age_bars")
        if sig:
            signal_lines.append(f"- Letztes Signal: {sig}, vor {age} Kerzen")
        if "context" in last_signals:
            signal_lines.append(f"- Signal-Kontext: {last_signals['context']}")

    backtest_lines = []
    if backtest_stats:
        backtest_lines.append(
            f"- Backtest Total Return: {backtest_stats.get('total_return_pct', 0):.1f} %"
        )
        backtest_lines.append(
            f"- Win-Rate: {backtest_stats.get('win_rate_pct', 0):.1f} %, "
            f"Trades: {backtest_stats.get('num_trades', 0)}"
        )
        backtest_lines.append(
            f"- Max Drawdown: {backtest_stats.get('max_drawdown_pct', 0):.1f} %"
        )

    text = []
    text.append(f"Aktueller Kurs: {last_price:.2f} (Veränderung über Zeitraum: {change_pct:.1f} %).")
    text.append(f"Trend-Einschätzung: {trend_desc}.")
    text.append(f"Volatilität: {vol_desc} (ca. {vol:.1f} % typische Spanne).")

    if indicator_lines:
        text.append("\nIndikator-Summary:")
        text.extend(indicator_lines)

    if signal_lines:
        text.append("\nSignale:")
        text.extend(signal_lines)

    if backtest_lines:
        text.append("\nBacktest-Kurzfassung (auf Basis BUY/SELL-Signale):")
        text.extend(backtest_lines)

    text.append(
        "\nBitte leite daraus mögliche Chartmuster und Szenarien für Swing-Trades ab."
    )

    return "\n".join(text)


def run_copilot(
    symbol: str,
    timeframe_label: str,
    price_df: pd.DataFrame,
    indicators: Dict[str, Any],
    last_signals: Dict[str, Any],
    backtest_stats: Optional[Dict[str, Any]] = None,
    model: str = "llama-3.3-70b-versatile",
) -> str:
    """
    Baut Prompt + ruft Groq auf.
    """
    client = get_groq_client()
    if client is None:
        return "⚠️ Kein Groq API-Key gefunden. Bitte GROQ_API_KEY in Secrets oder Umgebungsvariablen setzen."

    chart_summary = build_chart_summary(
        price_df=price_df,
        indicators=indicators,
        last_signals=last_signals,
        backtest_stats=backtest_stats,
    )

    user_prompt = f"""
Symbol: {symbol}
Timeframe: {timeframe_label}

CHART SUMMARY (aggregiert):
{chart_summary}
"""

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )

    return resp.choices[0].message.content.strip()
