# config.py
"""
Zentrale Konfiguration für das TradingView-Projekt.
Alle Konstanten & Settings werden hier verwaltet.
"""

# ---------------------------------------------------------
# API Settings
# ---------------------------------------------------------
BITFINEX_BASE_URL = "https://api-pub.bitfinex.com/v2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CryptoTV/1.0; +https://streamlit.io)"
}

# ---------------------------------------------------------
# Symbole (Bitfinex)
# ---------------------------------------------------------
SYMBOLS = {
    "BTC": "tBTCUSD",
    "ETH": "tETHUSD",
    "XRP": "tXRPUSD",
    "SOL": "tSOLUSD",
    "DOGE": "tDOGE:USD",
}

# ---------------------------------------------------------
# Timeframes (Mapping UI → Bitfinex)
# ---------------------------------------------------------
TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}

DEFAULT_TIMEFRAME = "1d"

# Länge der Historie für Candle-Download
YEARS_HISTORY = 3.0

# ---------------------------------------------------------
# Signale & Farben
# ---------------------------------------------------------
VALID_SIGNALS = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]

# Konsistente Farbdefinition (PEP8-konforme Konstante)
SIGNAL_COLORS = {
    "STRONG BUY": "#00e676",  # kräftiges Grün
    "BUY":        "#81c784",  # helleres Grün
    "SELL":       "#e57373",  # hellrot
    "STRONG SELL":"#d32f2f",  # starkes Rot
    "HOLD":       "#9E9E9E",  # grau
    "NO DATA":    "#BDBDBD",  # hellgrau
}

def badge_color(signal: str) -> str:
    """Farbe, die im UI für Signal-Badges verwendet wird."""
    return SIGNAL_COLORS.get(signal, "#9E9E9E")

# ---------------------------------------------------------
# Theme-Farben
# ---------------------------------------------------------
THEMES = {
    "Dark": {
        "bg": "#020617",
        "fg": "#E5E7EB",
        "grid": "#111827",
        "rsi_line": "#e5e7eb",
    },
    "Light": {
        "bg": "#FFFFFF",
        "fg": "#111827",
        "grid": "#E5E7EB",
        "rsi_line": "#6B7280",
    },
}
