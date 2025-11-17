# ai/copilot.py

import pandas as pd
from textwrap import dedent
import os

# ---------------------------------------------------------
# CHOOSE MODEL (cloud or local)
# ---------------------------------------------------------

USE_OPENAI = True  # False = lokales Modell (Ollama)

# OPENAI-Konfiguration
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OLLAMA-Konfiguration (lokal)
OLLAMA_MODEL = "llama3.1"
# z.B. in Terminal installieren:
# ollama pull llama3.1


# ---------------------------------------------------------
# OPENAI CLIENT
# ---------------------------------------------------------
def _ask_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": "Du bist ein professioneller Trading-Analyst. Analysiere Charts, Trends und Risiken."},
                  {"role": "user", "content": prompt}],
        max_tokens=500,
    )

    return completion.choices[0].message["content"]


# ---------------------------------------------------------
# OLLAMA CLIENT (lokal)
# ---------------------------------------------------------
def _ask_ollama(prompt: str) -> str:
    import requests
    url = "http://localhost:11434/api/generate"

    resp = requests.post(
        url,
        json={"model": OLLAMA_MODEL, "prompt": prompt},
        timeout=60
    )
    if resp.status_code != 200:
        return f"[Ollama Error {resp.status_code}] {resp.text}"

    # Streaming-Response → letzte Zeile behalten
    output = ""
    for line in resp.text.split("\n"):
        if line.strip().startswith("{"):
            output = line

    import json
    try:
        return json.loads(output)["response"]
    except:
        return output


# ---------------------------------------------------------
# KI COPILOT — HAUPTFUNKTION
# ---------------------------------------------------------
def ask_copilot(question: str, symbol: str, timeframe: str, df: pd.DataFrame) -> str:
    """
    Kombiniert Chartdaten + Frage → KI-Antwort.
    """

    if df.empty:
        return "Ich kann leider nichts analysieren — dein Chart hat keine Daten."

    last = df.iloc[-1]
    prev = df.iloc[-2]

    prompt = f"""
    Du bist mein persönlicher Trading-CoPilot.

    Hier die aktuellen Daten für {symbol} ({timeframe}):

    Letzte Candle:
    - Open: {last['open']:.2f}
    - High: {last['high']:.2f}
    - Low: {last['low']:.2f}
    - Close: {last['close']:.2f}
    - RSI14: {last['rsi14']:.2f}
    - EMA20: {last['ema20']:.2f}
    - EMA50: {last['ema50']:.2f}
    - MA200: {last['ma200']:.2f}

    Frage des Nutzers:
    {question}

    Antworte wie ein professioneller Analyst:
    - klare, kurze Aussagen
    - konkrete Handlungsoptionen
    - Risiken erwähnen
    - ohne Finanzberatung!
    """

    if USE_OPENAI:
        return _ask_openai(prompt)
    else:
        return _ask_ollama(prompt)
