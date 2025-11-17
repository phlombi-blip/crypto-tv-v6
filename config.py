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
    "User-Agent": "Mozilla/5.0 (compatible; CryptoTV-V5/1.0; +https://streamlit.io)"
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

# Wie viele Jahre Historie sollen geladen werden?
YEARS_HISTORY = 3.0

# ---------------------------------------------------------
# Signale (Mapping & Farben)
# ---------------------------------------------------------
VALID_SIGNALS = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]

SIGNAL_COLORS = {
    "STRONG BUY": "#00e676",
    "BUY": "#81c784",
    "SELL": "#e57373",
    "STRONG SELL": "#d32f2f",
    "HOLD": "#9E9E9E",
    "NO DATA": "#BDBDBD",
}

# Für Badges (z.B. im Header)
def badge_color(signal: str) -> str:
    return SIGNAL_COLORS.get(signal, "#9E9E9E")

# ---------------------------------------------------------
# Themes
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
