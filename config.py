# config.py
"""
Globale Konfiguration für das CryptoTV Projekt (Flat Structure)
"""

# ---------------------------------------------------------
# API Settings
# ---------------------------------------------------------
BITFINEX_BASE_URL = "https://api-pub.bitfinex.com/v2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CryptoTV/1.0; +https://streamlit.io)"
}

# ---------------------------------------------------------
# Symbole
# ---------------------------------------------------------
SYMBOLS = {
    "BTC": "tBTCUSD",
    "ETH": "tETHUSD",
    "XRP": "tXRPUSD",
    "SOL": "tSOLUSD",
    "DOGE": "tDOGE:USD",
}

# ---------------------------------------------------------
# Timeframes
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
YEARS_HISTORY = 3.0

# ---------------------------------------------------------
# Signal-Farben
# ---------------------------------------------------------
SIGNAL_COLORS = {
    "STRONG BUY": "#00e676",
    "BUY":        "#81c784",
    "SELL":       "#e57373",
    "STRONG SELL": "#d32f2f",
    "HOLD":       "#9E9E9E",
    "NO DATA":    "#BDBDBD",
}
