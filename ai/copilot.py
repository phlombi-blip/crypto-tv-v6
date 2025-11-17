# ai/copilot.py
import openai
import os

# → DU MUSST im System deine OPENAI_API_KEY als Umgebungsvariable setzen!
# export OPENAI_API_KEY="sk-..."

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_copilot(prompt: str, market_state: dict) -> str:
    """
    Ruft das GPT-Modell auf.
    Marktstate enthält:
      rsi, ema20, ema50, ma200, bb_up/down, trend, divergences, volatility, price
    """
    system_prompt = f"""
    Du bist ein professioneller Trading-CoPilot, spezialisiert auf:
    - BTCUSD technische Analyse
    - Candlestick Patterns
    - RSI Divergenzen
    - Volatilität
    - Trendanalyse (EMA20/50, MA200)
    - Bollinger Band Verhalten
    - Breakout- und Reversal-Erkennung

    Du sollst den Nutzer beraten, wie ein erfahrener Trader.
    Du antwortest kurz, klar und ohne Disclaimer.

    Aktuelle Marktdaten:
    Preis: {market_state.get('price')}
    RSI14: {market_state.get('rsi')}
    EMA20: {market_state.get('ema20')}
    EMA50: {market_state.get('ema50')}
    MA200: {market_state.get('ma200')}
    Bollinger: {market_state.get('bb_lo')} - {market_state.get('bb_up')}
    Trend: {market_state.get('trend')}
    Divergenzen: {market_state.get('divergences')}
    Volatilität: {market_state.get('volatility')}
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=350,
        temperature=0.2
    )

    return response.choices[0].message["content"]
