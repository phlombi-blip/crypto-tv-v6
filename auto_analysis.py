"""
auto_analysis.py

Auto-Analyse (Autosend) + E-Mail-Benachrichtigung bei Signalwechsel.
Die eigentliche Chart-/Signal-Logik bleibt in ui.py und indicators.py.
"""

import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import pandas as pd
import streamlit as st

from ai import groq_market_analysis


def send_email_notification(subject: str, body: str) -> bool:
    """Versendet eine E-Mail über SMTP (z.B. Gmail App-Passwort)."""
    try:
        sender = st.secrets["EMAIL_SENDER"]
        password = st.secrets["EMAIL_PASSWORD"]
        smtp_server = st.secrets.get("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(st.secrets.get("EMAIL_SMTP_PORT", 587))
        recipient = st.secrets.get("EMAIL_RECIPIENT", sender)
    except Exception:
        # Secrets nicht konfiguriert – stiller Fallback
        st.warning(
            "E-Mail-Secrets nicht konfiguriert (EMAIL_SENDER / EMAIL_PASSWORD). "
            "Signal-Änderungen werden nicht per Mail versendet."
        )
        return False

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(sender, password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"E-Mail-Versand fehlgeschlagen: {e}")
        return False


def build_auto_context(
    df: pd.DataFrame,
    latest_signal: str,
    signal_reason: str,
    symbol_label: str,
    tf_label: str,
) -> str:
    """Baut einen kompakten Kontext-Text für die Groq-Auto-Analyse."""
    last = df.iloc[-1]

    last_price = last["close"]
    ema20 = last.get("ema20")
    ema50 = last.get("ema50")
    ma200 = last.get("ma200")
    rsi14 = last.get("rsi14")
    bb_up = last.get("bb_up")
    bb_mid = last.get("bb_mid")
    bb_lo = last.get("bb_lo")

    context = f"""Symbol: {symbol_label} (Bitfinex)
Timeframe: {tf_label}

Letzter Schlusskurs: {last_price:.2f}
Aktuelles Handelssignal: {latest_signal}
Signal-Begründung (regelbasiert): {signal_reason}

Indikatoren (letzte Kerze):
- EMA20: {ema20:.2f} | EMA50: {ema50:.2f} | MA200: {ma200:.2f}
- Bollinger: Upper={bb_up:.2f}, Mid={bb_mid:.2f}, Lower={bb_lo:.2f}
- RSI(14): {rsi14:.1f}

Gib bitte eine kurze, strukturierte Markteinschätzung mit Fokus auf:
- Trend (aufwärts/abwärts/seitwärts)
- Momentum & Überkauft/Überverkauft
- Volatilität & mögliche Szenarien
- aber KEINE direkten Trading-Empfehlungen.
"""
    return context


def run_auto_analysis_if_needed(
    df: pd.DataFrame,
    latest_signal: str,
    signal_reason: str,
    symbol_label: str,
    tf_label: str,
) -> None:
    """Führt eine Auto-Analyse nur dann aus, wenn sich der Kontext geändert hat."""
    if not st.session_state.get("auto_enabled", True):
        return
    if df.empty or latest_signal == "NO DATA":
        return

    context = build_auto_context(df, latest_signal, signal_reason, symbol_label, tf_label)

    # Nur neu an Groq schicken, wenn sich der Kontext tatsächlich geändert hat
    last_context = st.session_state.get("last_auto_context")
    if last_context == context:
        return

    st.session_state["last_auto_context"] = context

    try:
        reply = groq_market_analysis(context)
    except Exception as e:
        st.session_state["groq_status"] = f"Fehler: {e}"
        st.error(f"Fehler bei Auto-Analyse (Groq): {e}")
        return

    st.session_state["last_auto_reply"] = reply
    st.session_state["groq_status"] = "ok"


def log_and_notify_signal_change(
    symbol_label: str,
    tf_label: str,
    latest_signal: str,
    last_price: float,
    change_pct: float,
    signal_reason: str,
) -> None:
    """Schreibt Signalwechsel in den Verlauf und verschickt optional eine Mail."""
    prev_sig: Optional[str] = st.session_state.get("last_signal")

    if latest_signal == "NO DATA":
        return
    if prev_sig == latest_signal:
        # kein Wechsel
        return

    st.session_state["last_signal"] = latest_signal

    # Signal in Verlauf speichern
    ts = st.session_state.get("last_signal_time")
    entry = {
        "timestamp": ts or "",
        "symbol": symbol_label,
        "timeframe": tf_label,
        "signal": latest_signal,
        "price": float(last_price),
        "change_pct": float(change_pct),
        "reason": signal_reason,
    }
    st.session_state.setdefault("signal_log", []).append(entry)

    # E-Mail verschicken
    subject = f"BTC Signal-Änderung: {latest_signal}"
    body = (
        f"Neues Handelssignal für {symbol_label} ({tf_label}): {latest_signal}\n\n"
        f"Preis: {last_price:.2f} USD\n"
        f"Änderung (letzte Kerze): {change_pct:.2f}%\n\n"
        f"Begründung: {signal_reason}\n"
    )
    send_email_notification(subject, body)
