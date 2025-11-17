# ai/commentary.py

from textwrap import dedent


def _trend_to_text(trend: str) -> str:
    return {
        "strong_uptrend": "starker Aufwärtstrend (EMA20 > EMA50 & über MA200)",
        "uptrend": "Aufwärtstrend (über MA200)",
        "sideways": "Seitwärtsphase",
        "downtrend": "Abwärtstrend (unter MA200)",
        "strong_downtrend": "starker Abwärtstrend (EMA20 < EMA50 & unter MA200)",
    }.get(trend, "Trend unklar")


def _div_to_text(div: str) -> str:
    return {
        "bullish_divergence": "bullishe RSI-Divergenz (bullish)",
        "bearish_divergence": "bearishe RSI-Divergenz (bearish)",
        "none": "keine Divergenz",
    }[div]


def _vol_to_text(vol: str) -> str:
    return {
        "low": "niedrige Volatilität (Ranging / Kompression)",
        "normal": "normale Volatilität",
        "high": "hohe Volatilität (Breakouts möglich)",
    }.get(vol, "Volatilität unklar")


def market_commentary(symbol: str, timeframe: str, trend: str, divergence: str, vol: str, last_price: float, last_signal: str):
    """
    Generiert einen kurzen automatischen Text für den KI-Marktkommentar.
    """

    trend_txt = _trend_to_text(trend)
    div_txt = _div_to_text(divergence)
    vol_txt = _vol_to_text(vol)

    text = f"""
    **{symbol}/{timeframe} — KI Markteinschätzung**

    • **Preis**: {last_price:,.2f} USD  
    • **Trend**: {trend_txt}  
    • **RSI Analyse**: {div_txt}  
    • **Volatilität**: {vol_txt}  
    • **Systemsignal**: {last_signal}

    **Interpretation:**  
    - Trend: {trend_txt}.  
    - Divergenz: {div_txt}.  
    - Volatilität: {vol_txt}.  

    Hinweis: Dies ist eine rein technische Einschätzung basierend auf deinem Chart.
    """

    return dedent(text).strip()
