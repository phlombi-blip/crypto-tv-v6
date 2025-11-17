import streamlit as st

# Bitfinex Public API (ohne API-Key)
BITFINEX_BASE_URL = "https://api-pub.bitfinex.com/v2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CryptoTV-V5/1.0; +https://streamlit.io)"
}

# Symbole auf Bitfinex
SYMBOLS = {
    "BTC": "tBTCUSD",
    "ETH": "tETHUSD",
    "XRP": "tXRPUSD",
    "SOL": "tSOLUSD",
    "DOGE": "tDOGE:USD",
}

signal_colors = {
    "STRONG BUY": "#00e676",  # kräftiges Grün
    "BUY": "#81c784",         # helleres Grün
    "SELL": "#e57373",        # hellrot
    "STRONG SELL": "#d32f2f", # kräftiges Rot
}

# Anzeige-Labels → interne Timeframes (Bitfinex: 1m..1D)
TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",  # Bitfinex schreibt 1D
}

DEFAULT_TIMEFRAME = "1d"
VALID_SIGNALS = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]

# Wie viele Jahre Historie sollen ungefähr geladen werden?
YEARS_HISTORY = 3.0

# THEME CSS
DARK_CSS = """
<style>
body, .main {
    background-color: #020617;
}
.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
}
.tv-card {
    background: #020617;
    border-radius: 0.75rem;
    border: 1px solid #1f2933;
    padding: 0.75rem 1rem;
}
.tv-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: #9ca3af;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.signal-badge {
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-weight: 600;
    display: inline-block;
}
</style>
"""

LIGHT_CSS = """
<style>
body, .main {
    background-color: #F3F4F6;
}
.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
}
.tv-card {
    background: #FFFFFF;
    border-radius: 0.75rem;
    border: 1px solid #E5E7EB;
    padding: 0.75rem 1rem;
}
.tv-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: #6B7280;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.signal-badge {
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-weight: 600;
    display: inline-block;
}
</style>
"""
