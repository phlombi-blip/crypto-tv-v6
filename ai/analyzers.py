# ai/analyzers.py
import numpy as np


def detect_trend(df):
    if df.empty:
        return "unknown"

    last = df.iloc[-1]
    ema20 = last["ema20"]
    ema50 = last["ema50"]
    ma200 = last["ma200"]
    price = last["close"]

    if price > ema20 > ema50 and price > ma200:
        return "strong_uptrend"
    if price > ema20 and ema20 > ema50:
        return "uptrend"
    if price < ema20 and ema20 < ema50:
        return "downtrend"
    return "neutral"


def detect_volatility(df):
    if df.empty:
        return "unknown"

    last = df.iloc[-1]
    bb_width = (last["bb_up"] - last["bb_lo"]) / last["bb_mid"] if last["bb_mid"] != 0 else 0

    if bb_width > 0.18:
        return "high"
    if bb_width < 0.07:
        return "low"
    return "normal"


def detect_rsi_divergence(df):
    """
    Simple divergence detection:
    Preis macht neues Tief/Hoch, RSI nicht.
    """
    if len(df) < 20:
        return "none"

    closes = df["close"].values[-10:]
    rsi = df["rsi14"].values[-10:]

    price_low_new = closes[-1] < np.min(closes[:-1])
    rsi_low_new = rsi[-1] < np.min(rsi[:-1])

    price_high_new = closes[-1] > np.max(closes[:-1])
    rsi_high_new = rsi[-1] > np.max(rsi[:-1])

    if price_low_new and not rsi_low_new:
        return "bullish_divergence"
    if price_high_new and not rsi_high_new:
        return "bearish_divergence"

    return "none"
