from __future__ import annotations
import pandas as pd
from .analyzers import detect_trend, detect_rsi_divergence, detect_volume_spike

def market_commentary(df: pd.DataFrame, symbol_label: str, timeframe_label: str) -> str:
    """
    Builds a concise, human-readable commentary string based on analyzers.
    Pure function – no Streamlit calls. Safe to run each refresh.
    """
    if df is None or df.empty:
        return f"{symbol_label}/{timeframe_label}: Keine Daten vorhanden."

    t = detect_trend(df)
    div = detect_rsi_divergence(df)
    vol = detect_volume_spike(df)

    parts = [f"📈 {symbol_label}/{timeframe_label} – KI-Kurzkommentar:"]
    # trend
    parts.append(f"• Trend: **{t['state']}** (Stärke {t['strength']:.2f}).")
    # divergence
    if div["type"] != "none":
        arrow = "🟢 Bullische Divergenz" if div["type"] == "bullish" else "🔴 Bärische Divergenz"
        parts.append(f"• RSI: {arrow} (Konfidenz {div['confidence']:.2f}).")
    else:
        parts.append("• RSI: Keine klare Divergenz.")
    # volume
    if vol["spike"]:
        parts.append(f"• Volumen: Spike erkannt (x{vol['ratio']:.1f} über Durchschnitt).")
    else:
        parts.append("• Volumen: Unauffällig.")

    parts.append("• Hinweis: Das ist kein Finanzrat – bitte eigenes Risk-Management nutzen.")
    return "  \n".join(parts)
