# signals.py

"""
Signal-Engine:
- STRONG BUY / BUY / SELL / STRONG SELL / HOLD
- Blow-Off-Top Detection
- Adaptive Bollinger Volatilität
- RSI Trend Confirmation
- Nur Long im Bullenmarkt (MA200-Filter)
- Nur neues Signal bei Richtungswechsel

Exportiert:
- signal_with_reason(last, prev)
- compute_signals(df)
- latest_signal(df)
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------
# Kernlogik für EIN Candlepaar (aktueller + vorheriger)
# ---------------------------------------------------------
def _signal_core_with_reason(last: pd.Series, prev: pd.Series):
    """
    Single-candle-Decision Engine.
    Liefert (Signal, Reason).
    """

    # Rohdaten extrahieren
    close = last["close"]
    prev_close = prev["close"]

    ema50 = last["ema50"]
    ma200 = last["ma200"]

    rsi_now = last["rsi14"]
    rsi_prev = prev["rsi14"]

    bb_up = last["bb_up"]
    bb_lo = last["bb_lo"]
    bb_mid = last["bb_mid"]

    high = last["high"]
    low = last["low"]
    open_price = last["open"]

    candle_range = high - low
    upper_wick = high - max(close, open_price)

    # -----------------------------------------------------
    # Adaptive Volatilität: beeinflusst Stärke der Signale
    # -----------------------------------------------------
    vol = (bb_up - bb_lo) / bb_mid if bb_mid else 0
    is_low_vol = vol < 0.06
    is_high_vol = vol > 0.12

    # -----------------------------------------------------
    # 1) MA200 Trendfilter
    # -----------------------------------------------------
    if pd.isna(ma200):
        return "HOLD", "MA200 nicht verfügbar – zu wenig Historie für Trendfilter."

    # Nur Long-Trading, wenn über MA200
    if close < ma200:
        return "HOLD", "Preis unter MA200 – System handelt nur Long im Bullenmarkt."

    # -----------------------------------------------------
    # 2) Blow-Off-Top (STRONG SELL)
    # -----------------------------------------------------
    blowoff = (
        candle_range > 0
        and upper_wick > candle_range * 0.45
        and close < prev_close
        and close > bb_up
        and rsi_now > 73
    )

    if blowoff:
        return (
            "STRONG SELL",
            "Blow-Off-Top: großer oberer Docht, Close über BB-Upper, RSI > 73 und Umkehrkerze."
        )

    # -----------------------------------------------------
    # 3) Deep Dip → STRONG BUY
    # -----------------------------------------------------
    deep_dip = (
        close <= bb_lo
        and rsi_now < 35
        and rsi_now > rsi_prev
    )

    if deep_dip:
        if is_low_vol and close < bb_lo * 0.995:
            return (
                "STRONG BUY",
                "Tiefer Dip + sehr geringe Volatilität → starker Mean-Reversion Einstieg."
            )
        return (
            "STRONG BUY",
            "Tiefer Dip: Preis am unteren Bollinger-Band, RSI < 35 und dreht hoch."
        )

    # -----------------------------------------------------
    # 4) BUY (normaler Pullback)
    # -----------------------------------------------------
    buy_price_cond = (
        close <= bb_lo * (1.01 if is_high_vol else 1.00)
        or close <= ema50 * 0.96
    )

    buy_rsi_cond = (
        30 < rsi_now <= 48
        and rsi_now > rsi_prev
    )

    if buy_price_cond and buy_rsi_cond:
        return (
            "BUY",
            "Gesunder Pullback: Nähe BB-Lo oder <EMA50, RSI 30–48 und dreht hoch."
        )

    # -----------------------------------------------------
    # 5) STRONG SELL (extreme Überhitzung)
    # -----------------------------------------------------
    strong_sell_cond = (
        close > ema50 * 1.12
        and close > bb_up
        and rsi_now > 80
        and rsi_now < rsi_prev
    )

    if strong_sell_cond:
        return (
            "STRONG SELL",
            "Extreme Überhitzung: Preis >> EMA50 & BB-Upper, RSI > 80 und fällt."
        )

    # -----------------------------------------------------
    # 6) SELL (normale Übertreibung)
    # -----------------------------------------------------
    sell_cond = (
        close > bb_up
        and rsi_now > 72
        and rsi_now < rsi_prev
    )

    if sell_cond:
        return (
            "SELL",
            "Übertreibung: Preis über BB-Upper, RSI > 72 und dreht nach unten."
        )

    # -----------------------------------------------------
    # Kein Signal → HOLD
    # -----------------------------------------------------
    return "HOLD", "Neutral – weder Übertreibung noch Dip erkannt."


# ---------------------------------------------------------
# Public API – einzelne Kerze
# ---------------------------------------------------------
def signal_with_reason(last: pd.Series, prev: pd.Series):
    """Externe Schnittstelle für 1 Kerze: (signal, reason)."""
    return _signal_core_with_reason(last, prev)


# ---------------------------------------------------------
# Compute für ganzen DataFrame
# ---------------------------------------------------------
def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt zwei Spalten hinzu:
    - signal
    - signal_reason

    UND:
    - nur neues Signal, wenn sich Richtung ändert
    - sonst → HOLD
    """

    if df.empty or len(df) < 2:
        df = df.copy()
        df["signal"] = "NO DATA"
        df["signal_reason"] = "Nicht genug Daten."
        return df

    df = df.copy()

    signals = []
    reasons = []
    last_sig = "NO DATA"

    for i in range(len(df)):
        if i == 0:
            signals.append("NO DATA")
            reasons.append("Erste Kerze – keine Historie.")
            continue

        sig_raw, reason_raw = signal_with_reason(df.iloc[i], df.iloc[i - 1])

        # Logik: Nur neues Signal wenn echte Richtungsänderung
        if sig_raw == last_sig:
            signals.append("HOLD")
            reasons.append(f"Signal '{sig_raw}' hält an.")
        else:
            signals.append(sig_raw)
            reasons.append(reason_raw)
            if sig_raw in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
                last_sig = sig_raw

    df["signal"] = signals
    df["signal_reason"] = reasons
    return df


# ---------------------------------------------------------
# aktuelles (letztes) Signal
# ---------------------------------------------------------
def latest_signal(df: pd.DataFrame) -> str:
    """Gibt das letzte VALIDE Signal zurück."""
    if df.empty or "signal" not in df:
        return "NO DATA"
    subset = df[df["signal"].isin(["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"])]
    return subset["signal"].iloc[-1] if not subset.empty else "NO DATA"
