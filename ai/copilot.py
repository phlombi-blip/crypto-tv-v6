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

    Erwartete Secrets-Struktur in .streamlit/secrets.toml:
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
# Hilfsfunktionen
# ---------------------------------------------------------
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
# Daten kompakt für LLM zusammenfassen (mit dynamischem Lookback & Längenlimit)
# ---------------------------------------------------------
def _compress_df_for_llm(
    df: pd.DataFrame,
    timeframe: str,
    max_override: Optional[int] = None,
    max_chars: int = 2000,
) -> str:
    """
    Reduziert den Chart auf ein kompaktes Text-Preview für den Prompt.

    Schutz vor zu großem Input:
    - Verwendet je nach Timeframe unterschiedlich viele Kerzen (Lookback).
    - Optional kann max_override gesetzt werden, um den Lookback hart zu überschreiben.
    - Zusätzlich wird der erzeugte Text auf max_chars Zeichen begrenzt.
    """

    if df is None or df.empty:
        return "Keine Kursdaten verfügbar."

    # Dynamische Lookbacks pro Timeframe
    lookbacks = {
        "1m": 300,   # ca. ein paar Stunden
        "5m": 300,   # ca. ein Tag
        "15m": 300,  # 2–3 Tage
        "1h": 300,   # ca. 12–13 Tage
        "4h": 250,   # ca. 6–7 Wochen
        "1d": 250,   # ca. 8 Monate
    }

    max_rows = max_override if max_override is not None else lookbacks.get(timeframe, 250)

    # Nur die letzten max_rows Kerzen verwenden
    if len(df) > max_rows:
        df = df.iloc[-max_rows:].copy()

    last = df.iloc[-1]

    # Basiswerte (mit get, falls Spalten fehlen)
    close = float(last.get("close", float("nan")))
    rsi = float(last.get("rsi14", float("nan")))
    ema20 = float(last.get("ema20", float("nan")))
    ema50 = float(last.get("ema50", float("nan")))
    ma200 = float(last.get("ma200", float("nan")))  # WICHTIG: MA200, kein EMA200

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
        f"Aktuelle Candle (auf Basis von {len(df)} Kerzen im Timeframe {timeframe}):",
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

    summary = "\n".join(parts)

    # Zusätzliche Sicherheitsbremse: max_chars
    if len(summary) > max_chars:
        summary = summary[: max_chars - 40].rstrip() + "\n…(Chart-Zusammenfassung gekürzt)…"

    return summary


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

    Sicherheitsaspekte:
    - Frage wird auf eine maximale Länge begrenzt.
    - DF-Zusammenfassung ist in Kerzen und Zeichen limitiert.
    - Antwort ist immer Text/Markdown, ohne HTML.
    - HTML-Fehlerseiten von Groq/Cloudflare werden erkannt und in saubere Meldungen übersetzt.
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

    # Benutzerfrage hart begrenzen (z.B. 1200 Zeichen),
    # um grobe Prompt-Explosionen zu vermeiden.
    raw_question = str(question).strip()
    max_question_chars = 1200
    if len(raw_question) > max_question_chars:
        raw_question = raw_question[: max_question_chars - 40].rstrip() + " … (Frage gekürzt)"

    # Kompakte Beschreibung der Marktdaten für den Prompt
    df_summary = _compress_df_for_llm(df, timeframe=timeframe, max_chars=2000)

    # SYSTEM PROMPT — MIT MA200 & ohne HTML
    user_prompt = (
        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n"
        f"Aktueller Signalscore: {last_signal}\n\n"
        f"Technische Daten (kompakt):\n{df_summary}\n\n"
        f"Benutzerfrage:\n{raw_question}\n\n"
        "Strukturiere deine Antwort bitte genau in diese 4 Abschnitte:\n\n"
        "1) Kurzfassung (max. 3 Bulletpoints)\n"
        "- Maximal 1 Satz pro Bullet.\n"
        "- Fokus: Trend, Risiko, Chance.\n\n"
        "2) Technische Analyse des Charts\n"
        "- Trend & Kreuzungen: Lage von EMA20/EMA50 zur MA200, z.B. Golden/Death Cross, "
        "Kurs über/unter diesen Linien, Pullbacks zur EMA20/EMA50.\n"
        "- RSI(14): Überkauft/überverkauft, Divergenzen, ob er steigt oder fällt.\n"
        "- Bollinger-Bänder: Position des Kurses (oberes/mittleres/unteres Band), "
        "Bandbreite (enge Range vs. Expansion), mögliche Ausbrüche oder Mean-Reversion.\n"
        "- Candlesticks: auffällige Kerzen (lange Dochte, Engulfing, Hammer/Shooting Star), "
        "ob sie Stärke oder Schwäche zeigen.\n"
        "- Unterstützungen/Widerstände: wichtige Preiszonen, die aus dem Verlauf "
        "und den Indikatoren ableitbar sind.\n\n"
        "3) Szenarien\n"
        "- Bullisches Szenario: Was müsste passieren, damit sich der Kurs nach oben "
        "durchsetzt (welche Signale von RSI, EMAs, BB, Candles)?\n"
        "- Bärisches Szenario: Was müsste passieren, damit der Abwärtstrend sich fortsetzt "
        "oder verstärkt?\n\n"
        "4) Hypothetische, rein technische Handelsidee (keine Anlageberatung)\n"
        "- Nenne eine mögliche Einstiegszone (Preisbereich) mit Begründung "
        "(z.B. Rücklauf auf EMA20, Test einer Unterstützung, Rebound am unteren Bollinger-Band).\n"
        "- Nenne eine grobe Stop-Zone (Preisbereich) mit Begründung "
        "(z.B. Bruch unter wichtige Unterstützung oder unteres Band).\n"
        "- Nenne eine grobe Zielzone (Preisbereich) mit Begründung "
        "(z.B. Rücklauf zur MA200, Retest eines Widerstands, mittleres/oberes Bollinger-Band).\n"
        "- Ordne die Idee als eher konservativ oder aggressiv ein und erkläre kurz warum.\n"
        "- Schließe mit einem klaren Satz ab, dass dies KEINE Anlageberatung ist, "
        "sondern nur ein mögliches, unsicheres Szenario aus technischer Sicht.\n\n"
        "WICHTIG:\n"
        "- Schreibe kompakt und vermeide Wiederholungen.\n"
        "- Antworte nur in Text oder Markdown, ohne HTML-Tags.\n"
    )



    # USER PROMPT — MIT MA200 & klaren Aufgaben
    user_prompt = (
        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n"
        f"Aktueller Signalscore: {last_signal}\n\n"
        f"Technische Daten (kompakt):\n{df_summary}\n\n"
        f"Benutzerfrage:\n{raw_question}\n\n"
        "Strukturiere deine Antwort bitte genau in diese 4 Abschnitte:\n\n"
        "1) Kurzfassung (max. 3 Bulletpoints)\n"
        "- Maximal 1 Satz pro Bullet.\n"
        "- Fokus: Trend, Risiko, Chance.\n\n"
        "2) Technische Analyse des Charts\n"
        "- Trend & Kreuzungen: Lage von EMA20/EMA50 zur MA200, z.B. Golden/Death Cross, "
        "Kurs über/unter diesen Linien, Pullbacks zur EMA20/EMA50.\n"
        "- RSI(14): Überkauft/überverkauft, Divergenzen, ob er steigt oder fällt.\n"
        "- Bollinger-Bänder: Position des Kurses (oberes/mittleres/unteres Band), "
        "Bandbreite (enge Range vs. Expansion), mögliche Ausbrüche oder Mean-Reversion.\n"
        "- Candlesticks: auffällige Kerzen (lange Dochte, Engulfing, Hammer/Shooting Star), "
        "ob sie Stärke oder Schwäche zeigen.\n"
        "- Unterstützungen/Widerstände: wichtige Preiszonen, die aus dem Verlauf "
        "und den Indikatoren ableitbar sind.\n\n"
        "3) Szenarien\n"
        "- Bullisches Szenario: Was müsste passieren, damit sich der Kurs nach oben "
        "durchsetzt (welche Signale von RSI, EMAs, BB, Candles)?\n"
        "- Bärisches Szenario: Was müsste passieren, damit der Abwärtstrend sich fortsetzt "
        "oder verstärkt?\n\n"
        "4) Hypothetische, rein technische Handelsidee (keine Anlageberatung)\n"
        "- Nenne eine mögliche Einstiegszone (Preisbereich) mit Begründung "
        "(z.B. Rücklauf auf EMA20, Test einer Unterstützung, Rebound am unteren Bollinger-Band).\n"
        "- Nenne eine grobe Stop-Zone (Preisbereich) mit Begründung "
        "(z.B. Bruch unter wichtige Unterstützung oder unteres Band).\n"
        "- Nenne eine grobe Zielzone (Preisbereich) mit Begründung "
        "(z.B. Rücklauf zur MA200, Retest eines Widerstands, mittleres/oberes Bollinger-Band).\n"
        "- Ordne die Idee als eher konservativ oder aggressiv ein und erkläre kurz warum.\n"
        "- Schließe mit einem klaren Satz ab, dass dies KEINE Anlageberatung ist, "
        "sondern nur ein mögliches, unsicheres Szenario aus technischer Sicht.\n\n"
        "WICHTIG:\n"
        "- Schreibe kompakt und vermeide Wiederholungen.\n"
        "- Antworte nur in Text oder Markdown, ohne HTML-Tags.\n"
    )


    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_completion_tokens=1800,  # Output begrenzen
        )

        content = response.choices[0].message.content or ""
        stripped = content.strip()

        # Falls Groq/Cloudflare uns eine HTML-Seite als "Antwort" schickt:
        if _looks_like_html_error(stripped):
            return (
                "❌ KI Fehler (Groq): Der KI-Dienst hat eine HTML-Fehlerseite "
                "(z.B. 500 / Cloudflare) zurückgegeben.\n"
                "Das liegt an der Gegenstelle, nicht an deiner Anfrage. "
                "Bitte später erneut versuchen."
            )

        return stripped

    except Exception as e:
        msg = str(e).strip()
        lower_msg = msg.lower()

        # Wenn der Fehlertext selbst nach HTML aussieht → generische, kurze Meldung
        if _looks_like_html_error(msg):
            return (
                "❌ KI Fehler (Groq): Der KI-Server hat intern eine HTML-Fehlerseite "
                "(z.B. 500 / Cloudflare) geliefert.\n"
                "Du kannst daran nichts ändern – der Dienst war vermutlich kurzzeitig "
                "nicht erreichbar. Bitte später erneut versuchen."
            )

        # Falls die Exception z.B. sowas enthält wie
        # "... 500 Internal Server Error ... <!DOCTYPE html> ...",
        # schneiden wir ab dem HTML-Teil weg:
        if "<!doctype html" in lower_msg:
            msg = msg.split("<!doctype html", 1)[0].strip()
            lower_msg = msg.lower()

        # Token-/Größenlimit / Rate-Limit
        if (
            "request too large" in lower_msg
            or "tokens per minute" in lower_msg
            or "413" in lower_msg
        ):
            return (
                "❌ KI Fehler (Groq): Die Anfrage war zu groß oder hat ein Token-/Rate-Limit überschritten.\n"
                "Wähle einen kürzeren Zeitraum oder stelle eine einfachere Frage."
            )

        # Generischer, gekürzter Fehler
        if len(msg) > 400:
            msg = msg[:400] + " …"

        return f"❌ KI Fehler (Groq): {msg}"
