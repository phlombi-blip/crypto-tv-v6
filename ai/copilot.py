from __future__ import annotations
import pandas as pd

# Placeholder – später kannst du hier echte LLM-Aufrufe integrieren.
# Jetzt geben wir deterministische, sichere Antworten zurück.

def ask_copilot(question: str, df: pd.DataFrame | None = None) -> str:
    if not question or not question.strip():
        return "Frag mich etwas zum aktuellen Chart (Trend, RSI, Volumen, Zonen etc.)."

    base = "🤖 Copilot: "
    q = question.lower()

    if "trend" in q:
        return base + "Der Trend wird hauptsächlich über MA200 und die jüngste Steigung beurteilt. Momentan liefert die KI-Sektion oben eine Einschätzung."
    if "rsi" in q:
        return base + "RSI 30/70 Marken sind relevant. Achte auf Divergenzen – die Erkennung steht in der KI-Sektion."
    if "support" in q or "widerstand" in q or "resistance" in q or "support" in q:
        return base + "Nutze lokale Hochs/Tiefs sowie Bollinger-Midline/EMA50 als dynamische Zonen. Bestätigungen über Volumen helfen."
    if "volume" in q or "volumen" in q:
        return base + "Volumenspitzen (x2 oder mehr gegenüber 20er Durchschnitt) deuten oft auf Breakouts oder Exhaustion hin."

    return base + "Die KI-Zusammenfassung über Trend/Divergenzen/Volumen findest du oberhalb des Charts. Stell mir gern eine spezifischere Frage."
