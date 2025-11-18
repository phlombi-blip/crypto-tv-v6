# signals.py
import pandas as pd
from config import SIGNAL_COLORS

def signal_color(signal: str) -> str:
    return SIGNAL_COLORS.get(signal, "#9E9E9E")


def _signal_core_with_reason(last, prev):
    close = last["close"]
    prev_close = prev["close"]

    ema50 = last["ema50"]
    ma200 = last["ma200"]
    rsi = last["rsi14"]
    bb_up = last["bb_up"]
    bb_lo = last["bb_lo"]

    # MA200 fehlt → nicht handeln
    if pd.isna(ma200):
        return "HOLD", "MA200 nicht verfügbar"

    # unterhalb MA200 → kein Long-Trading
    if close < ma200:
        return "HOLD", "Preis unterhalb MA200"

    # Blow-off top
    if (
        close > bb_up and
        rsi > 73 and
        close < prev_close
    ):
        return "STRONG SELL", "Blow-Off Top erkannt"

    # Deep dip
    if (
        close <= bb_lo and
        rsi < 35
    ):
        return "STRONG BUY", "Starker Dip am unteren Bollinger Band"

    # Buy
    if (
        close <= bb_lo * 1.01 and
        30 < rsi < 48
    ):
        return "BUY", "Gesunder Pullback"

    # Sell normal
    if (
        close > bb_up and
        rsi > 72 and
        rsi < prev["rsi14"]
    ):
        return "SELL", "Übertreibung am oberen Bollinger Band"

    return "HOLD", "Kein eindeutiges Signal"


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df["signal"] = "NO DATA"
        df["signal_reason"] = "Keine Daten"
        return df

    signals = []
    reasons = []
    last_out = "NO DATA"

    for i in range(len(df)):
        if i == 0:
            signals.append("NO DATA")
            reasons.append("Erste Kerze – keine Historie")
            continue

        sig_raw, reason_raw = _signal_core_with_reason(df.iloc[i], df.iloc[i - 1])

        if sig_raw == last_out:
            signals.append("HOLD")
            reasons.append("Signal unverändert")
        else:
            signals.append(sig_raw)
            reasons.append(reason_raw)
            if sig_raw in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
                last_out = sig_raw

    df["signal"] = signals
    df["signal_reason"] = reasons
    return df


def latest_signal(df: pd.DataFrame) -> str:
    if df.empty or "signal" not in df.columns:
        return "NO DATA"
    return df["signal"].iloc[-1]
