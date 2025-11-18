# ai/copilot.py
# -*- coding: utf-8 -*-

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
    """
    Erzeugt einmalig einen Groq-Client und cached ihn für die Session.
    Sucht den API-Key zuerst in Streamlit-Secrets, dann in Umgebungsvariablen.
    Erwartete Secrets-Struktur:
    [groq]
    api_key = "gsk_..."
    """
    api_key = None

    # 1) Streamlit Secrets bevorzugen
    try:
        api_key = st.secrets["groq"]["api_key"]
    except Exception:
        api_key = None

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
    Nutzt nur die letzten max_rows Kerzen.
    """
    if df is None or df.empty:
        return "Keine Kursdaten verfügbar."

    # Nur die letzten max_rows Kerzen verwenden
    if len(df) > max_rows:
        df = df.iloc[-max_rows:].copy()

    last = df.iloc[-1]

    # Basiswerte (mit get, falls Spalten fehlen)
    close = float(last.get("close", float("nan")))
    rsi = float(last.get("rsi14", float("nan")))
    ema20 = float(last.get("ema20", float("nan")))
    ema50 = float(last.get("ema50", float("nan")))
    ma200 = float(last.get("ma200", float("nan")))  # WICHTIG: MA200 hier!

    bb_mid = float(last.get("bb_mid", float("nan")))
    bb_up = float(last.get("bb_up", float("nan")))
    bb_lo = float(last.get("bb_lo", float("nan")))
    last_signal = str(last.get("signal", "NO DATA"))

    # Grobe Statistik über den betrachteten Zeitraum
    close_min = float(df["close"].min())
    close_max = float(df["close"].max())
    close_change_pct = (
        (df["close"].iloc[-1] / df["close"].iloc[0] - 1.0) * 100.0
        if df["close"].iloc[0] != 0
        else 0.0
    )

    if "rsi14" in df.columns:
        rsi_min = float(df["rsi14"].min())
        rsi_max = float(df["rsi14"].max())
    else:
        rsi_min = float("nan")
        rsi_max = float("nan")

    # Signals-Zusammenfassung
    sig_counts = {}
    if "signal" in df.columns:
        counts = df["signal"].value_counts()
        for sig, cnt in counts.items():
            sig_counts[str(sig)] = int(cnt)

    parts = [
        "Aktuelle Candle:",
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


def _looks_like_html_error(text: str) -> bool:
    """
    Erkenne typische HTML-Fehlerseiten (Cloudflare, 500er, etc.),
    damit wir sie nicht roh im UI anzeigen.
    """
    if not text:
        return False

    t = text.strip().lower()
    return (
        t.startswith("<!doctype html")
        or t.startswith("<html")
        or "cloudflare" in t
        or "cf-error" in t
        or "</html>" in t
    )


# ---------------------------------------------------------
# Hauptfunktion: CoPilot-Aufruf
# ---------------------------------------------------------
def ask_copilot(
    question: str,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    last_signal: Optional[str] = None,
) -> str:
    """
    Ruft Groq als CoPilot auf.
    - Nutzt kompakten Chart-Kontext
    - Liefert Text/Markdown (ohne HTML)
    - Erkennung von Groq/Cloudflare-HTML-Fehlerseiten
    """
    if not question or not str(question).strip():
        return "Bitte zuerst eine sinnvolle Frage an den CoPilot eingeben."

    client = get_groq_client()
    if client is None:
        return (
            "❌ KI nicht verfügbar: Kein Groq API-Key gefunden.\n\n"
            "Bitte in Streamlit unter `secrets.toml` eintragen:\n"
            "[groq]\napi_key = \"DEIN_GROQ_KEY_HIER\"\n"
            "oder die Umgebungsvariable `GROQ_API_KEY` setzen."
        )

    if last_signal is None:
        last_signal = "NO DATA"

    df_summary = _compress_df_for_llm(df)

    # SYSTEM PROMPT — MIT MA200
    system_prompt = (
        "Du bist ein nüchterner, technischer Analyst für Kryptowährungen.\n"
        "Du nutzt ausschließlich die folgenden Indikatoren:\n"
        "- RSI(14)\n"
        "- EMA20\n"
        "- EMA50\n"
        "- MA200\n"
        "- Bollinger-Bänder (20)\n"
        "- Candlestick-Struktur\n"
        "- Volumen\n\n"
        "Du interpretierst Trend, Momentum, Volatilität, Unterstützungen/Widerstände "
        "und mögliche psychologische Muster.\n\n"
        "Du gibst KEINE Finanz- oder Anlageberatung. Jede Handelsidee ist rein hypothetisch.\n\n"
        "WICHTIG:\n"
        "- Antworte nur in Text oder Markdown.\n"
        "- Verwende KEINE HTML-Tags wie <p>, <ul>, <li>, <div>, <span>, <br>."
    )

    # USER PROMPT — MIT MA200
    user_prompt = (
        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n"
        f"Aktueller Signalscore: {last_signal}\n\n"
        f"Technische Daten (kompakt):\n{df_summary}\n\n"
        f"Benutzerfrage:\n{question}\n\n"
        "Bitte:\n"
        "1. Beschreibe kurz das aktuelle Setup.\n"
        "2. Gehe ein auf:\n"
        "   - Trend (EMA20/EMA50/MA200)\n"
        "   - Momentum (RSI)\n"
        "   - Volatilität / Bollinger-Bänder\n"
        "   - Candlesticks (Druck, Stärke/Schwäche, Umkehr)\n"
        "   - Unterstützungen und Widerstände\n"
        "3. Gib ein bullisches und ein bärisches Szenario.\n"
        "4. Formuliere eine rein technische, hypothetische Handelsidee:\n"
        "   - mögliche Einstiegszone\n"
        "   - mögliche Stop-Zone\n"
        "   - mögliche Zielzone\n"
        "   - konservativ oder aggressiv\n"
        "5. Betone, dass es keine Anlageberatung ist.\n"
        "6. KEINE HTML-Tags verwenden — nur Markdown/Text.\n"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_completion_tokens=900,
        )

        content = response.choices[0].message.content or ""
        stripped = content.strip()

        # HTML-Error-Erkennung
        if _looks_like_html_error(stripped):
            return (
                "❌ KI Fehler (Groq): Der KI-Dienst hat eine HTML-Fehlerseite "
                "(z.B. 500 / Cloudflare) zurückgegeben.\n"
                "Bitte später erneut versuchen."
            )

        return stripped

    except Exception as e:
        msg = str(e).strip()
        lower_msg = msg.lower()

        if _looks_like_html_error(msg):
            return (
                "❌ KI Fehler (Groq): Eine HTML-Fehlerseite wurde zurückgegeben.\n"
                "Bitte später erneut versuchen."
            )

        if "<!doctype html" in lower_msg:
            msg = msg.split("<!doctype html")[0].strip()

        if any(x in lower_msg for x in ["request too large", "413", "tokens per minute"]):
            return (
                "❌ KI Fehler (Groq): Die Anfrage war zu groß oder überschreitet das Token-/Rate-Limit.\n"
                "Bitte Zeitraum verkleinern oder Frage vereinfachen."
            )

        if len(msg) > 400:
            msg = msg[:400] + " …"

        return f"❌ KI Fehler (Groq): {msg}"
