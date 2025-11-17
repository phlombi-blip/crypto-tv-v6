# ai/copilot.py

from openai import OpenAI

client = OpenAI()

def ask_copilot(question, df, symbol, timeframe):
    """
    KI-CoPilot analysiert den Chart und beantwortet Fragen.
    """

    if df is None or df.empty:
        chart_summary = "Keine Daten verfügbar."
    else:
        chart_summary = (
            f"Last Close: {df['close'].iloc[-1]:.2f}\n"
            f"RSI14: {df['rsi14'].iloc[-1]:.2f}\n"
            f"EMA20: {df['ema20'].iloc[-1]:.2f}\n"
            f"EMA50: {df['ema50'].iloc[-1]:.2f}\n"
            f"MA200: {df['ma200'].iloc[-1]:.2f}\n"
        )

    prompt = f"""
Du bist ein professioneller Trading-Assistent. Analysiere den Chart basierend auf:

Symbol: {symbol}
Timeframe: {timeframe}

Chart-Daten:
{chart_summary}

User-Frage:
{question}

Gib klare, präzise Hinweise und erkläre Trading-Kontext.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Du bist ein TradingView-Chart-Experte."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ KI Fehler: {str(e)}"
