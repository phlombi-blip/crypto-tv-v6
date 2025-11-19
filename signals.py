# signals.py
import numpy as np
import pandas as pd
from config import SIGNAL_COLORS


def signal_color(signal: str) -> str:
    return SIGNAL_COLORS.get(signal, "#9E9E9E")


def _signal_core_with_reason(last, prev):
    """
    Moderates Risiko, Long-only:
    Regime (MA200/EMA20/EMA50, ADX, RVOL, ATR%), Setups (Dip/Breakout/Reclaim),
    De-Risk (Überhitzung/Trendbruch).
    """
    close = last["close"]
    prev_close = prev["close"]

    ema20 = last["ema20"]
    ema50 = last["ema50"]
    ma200 = last["ma200"]

    rsi_now = last["rsi14"]
    rsi_prev = prev["rsi14"]

    bb_up = last["bb_up"]
    bb_lo = last["bb_lo"]
    bb_mid = last["bb_mid"]

    adx = last.get("adx14", np.nan)
    atr_pct = (last.get("atr14", np.nan) / close * 100) if close else np.nan
    rvol = last.get("rvol20", np.nan)

    # Regime-Filter
    if pd.isna(ma200):
        return "HOLD", "MA200 nicht verfügbar – kein Regime."
    if close < ma200:
        return "HOLD", "Unter MA200 – kein Long-Regime."
    if pd.notna(adx) and adx < 20:
        return "HOLD", "Trend zu schwach (ADX < 20)."
    if pd.notna(rvol) and rvol < 0.9:
        return "HOLD", "Volumen zu dünn (RVOL < 0.9)."
    if pd.notna(atr_pct) and atr_pct > 9:
        return "HOLD", "Volatilität zu hoch (>9% ATR/Close)."

    trend_ok = ema20 > ema50 > ma200

    # Trend-Dip
    dip_zone = (close <= ema20 * 1.025) and (close >= ema50 * 0.95)
    dip_rsi = (38 <= rsi_now <= 56) and (rsi_now > rsi_prev)
    if trend_ok and dip_zone and dip_rsi:
        return (
            "BUY",
            "Trend-Dip: Über MA200, EMA20>EMA50; Pullback zur Value-Zone (EMA20/EMA50) mit RSI-Rebound.",
        )

    # Breakout
    recent_high = max(prev["high"], last["high"])
    breakout_price = (close > recent_high) and (close > ema20)
    breakout_rsi = (50 <= rsi_now <= 65) and (rsi_now >= rsi_prev)
    breakout_vol = (pd.isna(rvol) or rvol >= 1.05)
    if trend_ok and breakout_price and breakout_rsi and breakout_vol:
        return (
            "BUY",
            "Trend-Breakout: Über MA200/EMA20/EMA50 mit neuem Hoch, RSI 50–65 steigend und Volumen-Expansion.",
        )

    # Reclaim
    reclaim = (prev_close < ema50) and (close > ema50) and (rsi_now > rsi_prev) and (rsi_now >= 46)
    if trend_ok and reclaim:
        return (
            "BUY",
            "Reclaim EMA50 nach Flush: Trend intakt, RSI dreht hoch – kleiner Re-Entry.",
        )

    # Überhitzung
    overheat = (close > bb_up) and (rsi_now > 72) and (rsi_now < rsi_prev)
    strong_overheat = (close > ema20 * 1.1) and (rsi_now > 80) and (rsi_now < rsi_prev)
    if strong_overheat:
        return (
            "STRONG SELL",
            "Extreme Überhitzung: Kurs > 1.1x EMA20, RSI > 80 und dreht – Abverkaufsrisiko.",
        )
    if overheat:
        return (
            "SELL",
            "Überhitzung: Kurs über oberem BB, RSI > 72 und fällt – De-Risk.",
        )

    # Trendbruch-Warnung
    trend_break = (close < ema50) and (rsi_now < 50) and (rsi_now < rsi_prev)
    if trend_break:
        return (
            "SELL",
            "Trendbruch: Close < EMA50 und RSI < 50 fallend – Longs reduzieren.",
        )

    return "HOLD", "Kein Setup: Regime passt, aber kein Dip/Breakout/Reclaim bestätigt."


def signal_with_reason(last, prev):
    return _signal_core_with_reason(last, prev)


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 2:
        df["signal"] = "NO DATA"
        df["signal_reason"] = "Nicht genug Daten für ein Signal."
        return df

    signals = []
    reasons = []
    last_sig = "NO DATA"

    for i in range(len(df)):
        if i == 0:
            signals.append("NO DATA")
            reasons.append("Erste Candle – keine Historie für Signalberechnung.")
            continue

        sig_raw, reason_raw = signal_with_reason(df.iloc[i], df.iloc[i - 1])

        if sig_raw == last_sig:
            sig_display = "HOLD"
            reason_display = f"Signal '{sig_raw}' besteht weiter – kein neues Signal generiert."
        else:
            sig_display = sig_raw
            reason_display = reason_raw
            if sig_raw in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
                last_sig = sig_raw

        signals.append(sig_display)
        reasons.append(reason_display)

    df["signal"] = signals
    df["signal_reason"] = reasons
    return df


def latest_signal(df: pd.DataFrame) -> str:
    if "signal" not in df.columns or df.empty:
        return "NO DATA"
    valid = df[df["signal"].isin(["STRONG BUY", "BUY", "SELL", "STRONG SELL", "HOLD"])]
    return valid["signal"].iloc[-1] if not valid.empty else "NO DATA"
