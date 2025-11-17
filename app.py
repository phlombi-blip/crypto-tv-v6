# app.py
import streamlit as st
import ui

# Page Config hier im "Hauptskript"
st.set_page_config(
    page_title="Crypto Live Ticker – TradingView Style V5",
    layout="wide",
)

if __name__ == "__main__":
    ui.main()
