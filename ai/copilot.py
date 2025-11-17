# ai/copilot.py

import openai

def ask_copilot(question, df, symbol, timeframe):
    """
    CoPilot beantwortet Fragen zum Chart.
    Der DataFrame wird in Textform zusammengefasst.
    """

    if df is None or df.empty:
        chart_summary = "Keine Daten verfügbar."
    else:
        chart_summary = (
            f"Letzter Close: {df['close'].iloc[-1]:.2f}\n"
            f"RSI: {df['rsi14'].iloc[-1]:.2f}\n"
            f"EMA20: {df['ema20'].iloc[-1]:.2f}\n"
            f"EMA50: {df['ema50'].iloc[-1]:.2f}\n"
            f"MA200: {df['ma200'].iloc[-1]:.2f}\n"
        )

    prompt = f"""
Du bist ein professioneller Trading-Assistent.

Symbol: {symbol}
Timeframe: {timeframe}

Chart-Daten:
{chart_summary}

Frage des Users:
{question}

Gib eine klare, präzise und handlungsorientierte Antwort.
"""

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        reply = resp["choices"][0]["message"]["content"]
        return reply

    except Exception as e:
        return f"❌ Fehler im KI-CoPilot: {str(e)}"
