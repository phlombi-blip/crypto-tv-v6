# ai/commentary.py
from ai.analyzers import detect_trend, detect_rsi_divergence, detect_volatility
from ai.copilot import ask_copilot


def market_commentary(df):
    if df.empty:
        return "Keine Daten verfügbar."

    last = df.iloc[-1]

    trend = detect_trend(df)
    div = detect_rsi_divergence(df)
    vol = detect_volatility(df)

    market_state = {
        "price": float(last["close"]),
        "rsi": float(last["rsi14"]),
        "ema20": float(last["ema20"]),
        "ema50": float(last["ema50"]),
        "ma200": float(last["ma200"]),
        "bb_up": float(last["bb_up"]),
        "bb_lo": float(last["bb_lo"]),
        "trend": trend,
        "divergences": div,
        "volatility": vol,
    }

    prompt = "Gib mir eine kurze Marktanalyse basierend auf den Daten."

    return ask_copilot(prompt, market_state)
