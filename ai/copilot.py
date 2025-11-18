# ai/copilot.py
import os
from typing import Optional

import pandas as pd
import streamlit as st
from groq import Groq


# ---------------------------------------------------------
# Groq Client holen (gecacht)
# ---------------------------------------------------------
@st.cache_resource
def get_groq_client() -> Optional[Groq]:
    api_key = None

    # 1) Streamlit Secrets bevorzugen
    try:
        api_key = st.secrets["groq"]["api_key"]
    except Exception:
        pass

    # 2) Fallback: Umgebungsvariable
    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return None

    return Groq(api_key=api_key)


# ---------------------------------------------------------
# Daten kompakt für LLM zusammenfassen
# ---------------------------------------------------------
def _compress_df_for_llm(df: pd.DataFrame, max_rows: int = 200) -> str:
    """
    Reduziert den Chart auf ein kompaktes Text-Preview,
    damit der Prompt klein bleibt und keine 413-Fehler kommen.
    """
    if df is None or df.empty:
        return "Keine Kursdaten verfügbar."

    # Nur die letzten max_rows Kerzen verwenden
    if len(df) > max_rows:
        df = df.iloc[-max_rows:].copy()

    last = df.iloc[-1]

    # Basiswerte
    close = float(last.get("close", float("nan")))
    rsi = float(last.get("rsi14", float("nan")))
    ema20 = float(last.get("ema20", float("nan")))
    ema50 = float(last.get("ema50", float("nan")))
    ma200 = float(last.get("ma200", float("nan")))
    bb_mid = float(last.get("bb_mid", float("nan")))
    bb_up = float(last.get("bb_up", float("nan")))
    bb_lo = float(last.get("bb_lo", float("nan")))
    last_signal = str(last.get("signal", "NO DATA"))

    # Grobe Statistik über den betrachteten Zeitraum
    close_min = float(df["close"].min())
    close_max = float(df["close"].max())
    close_change_pct = (
        (df["close"].iloc[-1] / df["close"].iloc[0] - 1.0) * 100.0
        if df["close"].iloc[0] != 0 else 0.0
    )

    rsi_min = float(df["rsi14"].min()) if "rsi14" in df.columns else float("nan")
    rsi_max = float(df["rsi14"].max()) if "rsi14" in df.columns else float("nan")

    # Signals-Zusammenfassung
    sig_counts = {}
    if "signal" in df.columns:
        counts = df["signal"].value_counts()
        for sig, cnt in counts.items():
            sig_counts[str(sig)] = int(cnt)

    parts = [
        f"Aktuelle Candle:",
        f"- Close: {close:.2f}",
        f"- RSI14: {rsi:.2f}",
        f"- EMA20: {ema20:.2f}",
        f"- EMA50: {ema50:.2f}",
        f"- MA200: {ma200:.2f}",
        f"- Bollinger: mid={bb_mid:.2f}, upper={bb_up:.2f}, lower={bb_lo:.2f}",
        f"- Letztes Signal: {last_signal}",
        "",
        "Zeitraum-Zusammenfassung:",
        f"- Min/Max Close: {close_min:.2f} / {close_max:.2f}",
        f"- Performance über Zeitraum: {close_change_pct:.2f} %",
        f"- RSI Spannweite: {rsi_min:.2f} – {rsi_max:.2f}",
    ]

    if sig_counts:
        sig_text = ", ".join([f"{k}: {v}" for k, v in sig_counts.items()])
        parts.append(f"- Signal-Häufigkeit: {sig_text}")

    return "\n".join(parts)


# ---------------------------------------------------------
# Hauptfunktion: CoPilot-Aufruf
# ---------------------------------------------------------
def ask_copilot(
    question: str,
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    last_signal: str,
) -> str:
    """
    Ruft Groq als CoPilot auf. Bei Fehlern wird eine kurze,
    saubere Fehlermeldung zurückgegeben (ohne HTML-Müll).
    """
    client = get_groq_client()
    if client is None:
        return (
            "❌ KI nicht verfügbar: Kein Groq API-Key gefunden.\n\n"
            "Bitte in Streamlit unter `secrets.toml` eintragen:\n"
            "[groq]\napi_key = \"DEIN_GROQ_KEY_HIER\""
        )

    # Kompakte Beschreibung der Marktdaten für den Prompt
    df_summary = _compress_df_for_llm(df)

    # Systemprompt: Rolle des CoPiloten
        system_prompt = (
        "Du bist ein erfahrener technischer Analyst für Kryptowährungen. "
        "Du interpretierst explizit RSI(14), EMA20, EMA50, MA200, Bollinger-Bänder "
        "und Candlestick-Strukturen (Trend, Pullbacks, Übertreibungen). "
        "Du gibst KEINE persönliche Anlageberatung und kennst weder Depotgröße noch Risikoprofil. "
        "Du darfst aber eine neutrale, hypothetische Handelsidee basierend auf der technischen Lage "
        "und typischer Marktpsychologie formulieren. "
        "Diese Idee muss immer klar als unsicheres Szenario dargestellt werden, mit Risiko-Hinweis. "
        "WICHTIG: Antworte ausschließlich in normalem Text bzw. Markdown "
        "und verwende KEINE HTML-Tags wie <p>, <ul>, <li>, <br> usw."
    )

    # User-Prompt: Chart-Kontext + Nutzerfrage
    user_prompt = (
        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n"
        f"Aktueller Signalscore: {last_signal}\n\n"
        f"Technische Daten (kompakt):\n{df_summary}\n\n"
        f"Benutzerfrage / Aufgabe:\n{question}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=900,  # bewusst begrenzt, damit die Antwort nicht explodiert
        )

        content = response.choices[0].message.content
        return content.strip()

    except Exception as e:
        # Rohtext der Exception
        msg = str(e)

        # 1) HTML / Cloudflare 5xx → kurze, saubere Meldung
        lower_msg = msg.lower()
        if "<!doctype html" in lower_msg or "<html" in lower_msg:
            return (
                "❌ KI Fehler (Groq): Der KI-Server hat eine technische 500-Fehlermeldung zurückgegeben.\n"
                "Das liegt nicht an deiner Anfrage, sondern an der Gegenstelle (Cloudflare / Groq).\n"
                "Bitte versuche es später erneut."
            )

        # 2) Token-/Größenlimit (413 / tokens)
        if "request too large" in lower_msg or "tokens per minute" in lower_msg or "413" in lower_msg:
            return (
                "❌ KI Fehler (Groq): Die Anfrage war zu groß für das aktuelle Modell/Limit.\n"
                "Versuche es mit einem kürzeren Zeitraum oder einer einfacheren Frage erneut."
            )

        # 3) Fallback: generische Fehlermeldung ohne HTML-Spam
        # Falls die Meldung extrem lang ist, abschneiden.
        if len(msg) > 400:
            msg = msg[:400] + " …"

        return f"❌ KI Fehler (Groq): {msg}"
