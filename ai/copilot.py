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
    ma200 = float(last.get("ma200", float("nan")))  # MA200 (nicht EMA200)

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

    # SYSTEM PROMPT — Strategie-basiert & ohne HTML
    system_prompt = (
        "Du bist ein nüchterner, präzise formulierender technischer Analyst für Kryptowährungen.\n"
        "Du arbeitest ausschließlich mit technischer Analyse und verwendest diese Werkzeuge:\n"
        "- RSI(14)\n"
        "- EMA20\n"
        "- EMA50\n"
        "- MA200\n"
        "- Bollinger-Bänder (20)\n"
        "- Candlestick-Struktur\n"
        "- Volumen\n\n"
        "Du kennst zusätzlich die folgende Long-only-Strategie-Logik:\n"
        "- Es wird nur in Long-Richtung gehandelt, wenn der Kurs ÜBER der MA200 liegt.\n"
        "- Ist die MA200 nicht verfügbar oder der Kurs darunter, ist das Ergebnis immer HOLD.\n"
        "- STRONG BUY: starker Dip am unteren Bollinger-Band (Kurs am/unter bb_lo) mit RSI < 35.\n"
        "- BUY: gesunder Pullback, wenn der Kurs nahe/unter dem unteren Band (<= bb_lo * 1.01) "
        "und der RSI zwischen 30 und 48 liegt.\n"
        "- STRONG SELL: Blow-Off-Top, wenn der Kurs über dem oberen Band liegt, der RSI > 73 ist "
        "und der Schlusskurs schwächer ist als die vorherige Kerze.\n"
        "- SELL: normale Übertreibung, wenn der Kurs über dem oberen Band liegt, der RSI > 72 ist "
        "und der RSI gegenüber der vorherigen Kerze fällt.\n"
        "- In allen anderen Fällen: HOLD (kein klares Setup).\n\n"
        "WICHTIG: Du sollst BEIDES tun:\n"
        "1) Eine freie, saubere technische Analyse des Charts geben.\n"
        "2) Die Situation EXPLIZIT im Kontext dieser Strategie-Logik einordnen "
        "(ob sie eher zu STRONG BUY / BUY / SELL / STRONG SELL / HOLD passt).\n\n"
        "Du schreibst prägnant, analytisch und strukturiert und vermeidest Wiederholungen.\n"
        "Die gesamte Antwort soll ungefähr 200–300 Wörter lang sein.\n\n"
        "Du darfst hypothetische technische Handelsideen (Entry-/Stop-/Target-Zonen) formulieren, "
        "musst aber immer klar sagen, dass es KEINE Anlageberatung ist.\n\n"
        "WICHTIG:\n"
        "- Antworte nur in normalem Text oder Markdown.\n"
        "- Verwende KEINE HTML-Tags wie <p>, <ul>, <li>, <div>, <span>, <br>.\n"
    )

    # USER PROMPT — Chartkontext & Strategie-Einordnung
    user_prompt = (
        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n"
        f"Aktueller Signalscore laut System: {last_signal}\n\n"
        f"Technische Daten (kompakt):\n{df_summary}\n\n"
        f"Benutzerfrage:\n{raw_question}\n\n"
        "Strukturiere deine Antwort bitte genau in diese 4 Abschnitte:\n\n"
        "1) Kurzfassung (max. 3 Bulletpoints)\n"
        "- Maximal 1 Satz pro Bullet.\n"
        "- Fokus: Trend, Risiko, Chance im aktuellen Setup.\n\n"
        "2) Freie technische Analyse des Charts\n"
        "- Trend & Kreuzungen: Lage von EMA20/EMA50 relativ zur MA200, "
        "Kurs über/unter diesen Linien, Pullbacks zur EMA20/EMA50.\n"
        "- RSI(14): überkauft/überverkauft, ob der RSI steigt oder fällt, mögliche Divergenzen.\n"
        "- Bollinger-Bänder: Position des Kurses (oberes/mittleres/unteres Band), "
        "Bandbreite (enge Range vs. Expansion), Hinweise auf Ausbruch oder Mean-Reversion.\n"
        "- Candlesticks: auffällige Kerzen (Dochte, Engulfing, Hammer/Shooting Star) "
        "und was sie über Stärke oder Schwäche aussagen.\n"
        "- Unterstützungen/Widerstände: wichtige Preiszonen aus Verlauf und Indikatoren.\n\n"
        "3) Einordnung im Kontext der Strategie\n"
        "- Beurteile, ob die aktuelle Situation eher zu STRONG BUY, BUY, SELL, STRONG SELL oder HOLD passt "
        "gemäß der beschriebenen Strategie-Regeln (MA200-Filter, Bollinger-Bänder, RSI-Schwellen, Blow-Off-Top, Dip).\n"
        "- Vergleiche deine Einschätzung kurz mit dem angegebenen Signalscore.\n"
        "- Wenn der Kurs unter MA200 liegt oder MA200 fehlt, betone klar, dass die Strategie nur HOLD vorsieht, "
        "auch wenn einzelne Indikatoren (z.B. RSI < 30) etwas anderes nahelegen.\n\n"
        "4) Hypothetische, rein technische Handelsidee (keine Anlageberatung)\n"
        "- Nenne eine mögliche Einstiegszone (Preisbereich) mit Bezug auf die Analyse "
        "und optional die Strategie (z.B. Rebound am unteren Band, Pullback an EMA50, Rücklauf zur MA200).\n"
        "- Nenne eine grobe Stop-Zone (Preisbereich) mit Begründung "
        "(z.B. Bruch unter wichtige Unterstützung, unteres Band oder unter MA200).\n"
        "- Nenne eine grobe Zielzone (Preisbereich) mit Begründung "
        "(z.B. Rücklauf zur MA200, Retest eines markanten Widerstands, mittleres/oberes Bollinger-Band).\n"
        "- Sage explizit, ob die Idee eher konservativ oder aggressiv ist, und begründe das kurz.\n"
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
            max_completion_tokens=1200,  # genug Platz, aber nicht übertrieben
        )

        content = response.choices[0].message.content or ""
        stripped = content.strip()

        # Falls Groq/Cloudflare uns eine HTML-Seite als "Antwort" schickt:
        if _looks_like_html_error(stripped):
            return (
                "❌ KI Fehler (Groq): Der KI-Dienst hat offenbar eine HTML-Fehlerseite "
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
