# ai/patterns.py

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List


@dataclass
class PatternHit:
    name: str            # z.B. "Double Top"
    score: int           # 0-100
    direction: str       # "bullish" / "bearish" / "neutral"
    rationale: str       # kurzer Hinweis
    projection: str      # erwartete Fortsetzung (technisch, kein Rat)


def _swing_points(series: pd.Series, window: int = 3):
    """Lokale Hochs/Tiefs für Muster-Checks."""
    highs, lows = [], []
    for i in range(window, len(series) - window):
        left = series.iloc[i - window : i]
        right = series.iloc[i + 1 : i + 1 + window]
        v = series.iloc[i]
        if v == max(series.iloc[i - window : i + window + 1]) and v > left.max() and v > right.max():
            highs.append(i)
        if v == min(series.iloc[i - window : i + window + 1]) and v < left.min() and v < right.min():
            lows.append(i)
    return highs, lows


def _ratio_closeness(a: float, b: float) -> float:
    """Relative Nähe zweier Preise (0 = identisch)."""
    return abs(a - b) / max(((a + b) / 2), 1e-9)


def detect_patterns(df: pd.DataFrame) -> List[PatternHit]:
    if df is None or df.empty or "close" not in df.columns:
        return []

    closes = df["close"].reset_index(drop=True)
    highs_series = df["high"].reset_index(drop=True) if "high" in df.columns else closes
    lows_series = df["low"].reset_index(drop=True) if "low" in df.columns else closes
    highs, lows = _swing_points(closes, window=3)
    hits: List[PatternHit] = []

    # Double Top
    if len(highs) >= 2:
        h1, h2 = highs[-2], highs[-1]
        closeness = _ratio_closeness(closes[h1], closes[h2])
        neckline = closes[min(h1, h2) : max(h1, h2)].min()
        broke_neckline = closes.iloc[-1] < neckline
        score = int((1 - closeness) * 100)
        if score >= 55:
            proj = "bärische Fortsetzung wahrscheinlicher, besonders unter Nackenlinie"
            hits.append(
                PatternHit(
                    name="Double Top",
                    score=min(score + (15 if broke_neckline else 0), 100),
                    direction="bearish",
                    rationale=f"zwei Hochs ähnlich hoch (+/-{closeness * 100:.1f}%)",
                    projection=proj,
                )
            )

    # Double Bottom
    if len(lows) >= 2:
        l1, l2 = lows[-2], lows[-1]
        closeness = _ratio_closeness(closes[l1], closes[l2])
        neckline = closes[min(l1, l2) : max(l1, l2)].max()
        broke_neckline = closes.iloc[-1] > neckline
        score = int((1 - closeness) * 100)
        if score >= 55:
            proj = "bullische Fortsetzung wahrscheinlicher, besonders über Nackenlinie"
            hits.append(
                PatternHit(
                    name="Double Bottom",
                    score=min(score + (15 if broke_neckline else 0), 100),
                    direction="bullish",
                    rationale=f"zwei Tiefs ähnlich tief (+/-{closeness * 100:.1f}%)",
                    projection=proj,
                )
            )

    # Descending Triangle
    if len(highs) >= 3:
        last_three = highs[-3:]
        lower_highs = closes[last_three[0]] > closes[last_three[1]] > closes[last_three[2]]
        if lower_highs:
            baseline = closes.iloc[min(last_three) :].min()
            squeeze = (closes[last_three[0]] - closes[last_three[2]]) / max(baseline, 1e-9)
            score = int(min(max((squeeze / 5) * 100, 0), 90))
            hits.append(
                PatternHit(
                    "Descending Triangle",
                    score,
                    "bearish",
                    "fallende Hochpunkte bei flacher Basis",
                    "Break nach unten bevorzugt, Volumen-Bestätigung abwarten",
                )
            )

    # Ascending Triangle
    if len(lows) >= 3:
        last_three = lows[-3:]
        higher_lows = closes[last_three[0]] < closes[last_three[1]] < closes[last_three[2]]
        if higher_lows:
            ceiling = closes.iloc[min(last_three) :].max()
            squeeze = (closes[last_three[2]] - closes[last_three[0]]) / max(ceiling, 1e-9)
            score = int(min(max((squeeze / 5) * 100, 0), 90))
            hits.append(
                PatternHit(
                    "Ascending Triangle",
                    score,
                    "bullish",
                    "steigende Tiefpunkte bei flacher Oberkante",
                    "Break nach oben bevorzugt, Volumen-Bestätigung abwarten",
                )
            )

    # Flaggen (Bull/Bear)
    if len(df) >= 40:
        recent = closes.tail(30)
        older = closes.tail(40).head(10)
        impulse_up = recent.mean() > older.mean() * 1.05
        impulse_down = recent.mean() < older.mean() * 0.95
        channel_range = (recent.max() - recent.min()) / max(recent.mean(), 1e-9)
        if impulse_up and channel_range < 0.06:
            hits.append(
                PatternHit(
                    name="Bull Flag",
                    score=70,
                    direction="bullish",
                    rationale="starker Impuls, enger Seitwärtskanal danach",
                    projection="Fortsetzungs-Breakout nach oben favorisiert",
                )
            )
        if impulse_down and channel_range < 0.06:
            hits.append(
                PatternHit(
                    name="Bear Flag",
                    score=70,
                    direction="bearish",
                    rationale="starker Abverkauf, enger Seitwärtskanal danach",
                    projection="Fortsetzungs-Break nach unten favorisiert",
                )
            )

    # Wedges (vereinfachte Version)
    if len(highs) >= 3 and len(lows) >= 3:
        h_slope = (closes[highs[-1]] - closes[highs[-3]]) / (highs[-1] - highs[-3] + 1)
        l_slope = (closes[lows[-1]] - closes[lows[-3]]) / (lows[-1] - lows[-3] + 1)
        if h_slope > 0 and l_slope > 0 and h_slope < l_slope:
            hits.append(
                PatternHit(
                    name="Rising Wedge",
                    score=65,
                    direction="bearish",
                    rationale="steigende Hochs/Tiefs, obere Trendlinie flacher",
                    projection="Ausbruch nach unten wahrscheinlicher",
                )
            )
        if h_slope < 0 and l_slope < 0 and h_slope > l_slope:
            hits.append(
                PatternHit(
                    name="Falling Wedge",
                    score=65,
                    direction="bullish",
                    rationale="fallende Hochs/Tiefs, untere Trendlinie flacher",
                    projection="Ausbruch nach oben wahrscheinlicher",
                )
            )

    # Symmetrisches Dreieck (zusammenlaufende Hochs/Tiefs)
    if len(highs) >= 3 and len(lows) >= 3:
        h1, h3 = highs[-3], highs[-1]
        l1, l3 = lows[-3], lows[-1]
        h_slope = (highs_series[h3] - highs_series[h1]) / (h3 - h1 + 1)
        l_slope = (lows_series[l3] - lows_series[l1]) / (l3 - l1 + 1)
        if h_slope < 0 and l_slope > 0:
            score = 60
            hits.append(
                PatternHit(
                    name="Symmetric Triangle",
                    score=score,
                    direction="neutral",
                    rationale="zusammenlaufende Hoch- und Tiefpunkte",
                    projection="Breakout in Trendrichtung wahrscheinlich; Volumen-Bestätigung abwarten",
                )
            )

    # Head & Shoulders (vereinfachtes 3-Peak-Muster)
    if len(highs) >= 3:
        h1, h2, h3 = highs[-3], highs[-2], highs[-1]
        p1, p2, p3 = highs_series[h1], highs_series[h2], highs_series[h3]
        neck = min(closes[min(h1, h2, h3):max(h1, h2, h3)])
        if p2 > p1 * 1.02 and p2 > p3 * 1.02 and abs(p1 - p3) / ((p1 + p3) / 2) < 0.03:
            broke_neck = closes.iloc[-1] < neck
            score = 70 + (10 if broke_neck else 0)
            hits.append(
                PatternHit(
                    name="Head and Shoulders",
                    score=min(score, 90),
                    direction="bearish",
                    rationale="mittleres Hoch deutlich höher, Schultern ähnlich",
                    projection="Abwärtsfortsetzung bevorzugt nach Nackenbruch",
                )
            )

    # Inverse Head & Shoulders
    if len(lows) >= 3:
        l1, l2, l3 = lows[-3], lows[-2], lows[-1]
        p1, p2, p3 = lows_series[l1], lows_series[l2], lows_series[l3]
        neck = max(closes[min(l1, l2, l3):max(l1, l2, l3)])
        if p2 < p1 * 0.98 and p2 < p3 * 0.98 and abs(p1 - p3) / ((p1 + p3) / 2) < 0.03:
            broke_neck = closes.iloc[-1] > neck
            score = 70 + (10 if broke_neck else 0)
            hits.append(
                PatternHit(
                    name="Inverse Head and Shoulders",
                    score=min(score, 90),
                    direction="bullish",
                    rationale="mittleres Tief deutlich tiefer, Schultern ähnlich",
                    projection="Aufwärtsfortsetzung bevorzugt nach Nackenbruch",
                )
            )

    # Rechteck / Range
    if len(df) >= 40:
        recent = closes.tail(30)
        rng = recent.max() - recent.min()
        mid = recent.mean()
        if rng / mid < 0.06:
            hits.append(
                PatternHit(
                    name="Rectangle Range",
                    score=55,
                    direction="neutral",
                    rationale="Seitwärtsrange mit enger Schwankung",
                    projection="Breakout über Range-Hoch bullisch, unter Range-Tief bärisch",
                )
            )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:3]
