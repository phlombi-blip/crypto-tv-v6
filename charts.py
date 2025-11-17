# charts.py

"""
Plotly-Chart-Modul für:
- Price + EMA20/50 + MA200 + Bollinger + Volume
- RSI Panel
- Signal History (STRONG BUY / BUY / SELL / STRONG SELL)

Dieses Modul enthält KEIN Streamlit. Nur Figures → pure Plotly.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ---------------------------------------------------------
# Helpers: Theme Colors
# ---------------------------------------------------------
def base_layout_kwargs(theme: str):
    if theme == "Dark":
        bg, fg = "#020617", "#E5E7EB"
    else:
        bg, fg = "#FFFFFF", "#111827"

    return dict(
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        font=dict(color=fg)
    )


def grid_color_for_theme(theme: str) -> str:
    return "#111827" if theme == "Dark" else "#E5E7EB"


# Farben für Signal-History
signal_colors = {
    "STRONG BUY": "#00e676",  # kräftiges Grün
    "BUY": "#81c784",         # helleres Grün
    "SELL": "#e57373",        # hellrot
    "STRONG SELL": "#d32f2f", # kräftiges Rot
}


# ---------------------------------------------------------
# PRICE + RSI CHART
# ---------------------------------------------------------
def create_price_rsi_figure(df: pd.DataFrame, symbol_label: str, timeframe_label: str, theme: str):
    """
    TradingView-style:
    - Candles + EMA + MA200
    - Bollinger als Shape hinter Candles
    - Volume
    - RSI panel
    """

    # --- Basic Colors ---
    BULL = "#22c55e"
    BEAR = "#ef4444"
    EMA20_COLOR = "#2962FF"
    EMA50_COLOR = "#FF6D00"
    MA200_COLOR = "#C51162"

    if theme == "Dark":
        BB_LINE = "#d1d5db"
        BB_FILL = "rgba(209,213,219,0.10)"
        BB_MID = "#9ca3af"
    else:
        BB_LINE = "#94a3b8"
        BB_FILL = "rgba(148,163,184,0.07)"
        BB_MID = "#6b7280"

    # Basic layout values
    layout_kwargs = base_layout_kwargs(theme)
    bg = layout_kwargs["plot_bgcolor"]
    fg = layout_kwargs["font"]["color"]
    grid = grid_color_for_theme(theme)

    # ----------------------------------------------------
    # Setup: 2-row Subplot
    # ----------------------------------------------------
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.03,
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        subplot_titles=(f"{symbol_label}/USD — {timeframe_label}", "RSI (14)")
    )

    fig.update_layout(
        height=720,
        showlegend=True,
        hovermode="x unified",
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        font=dict(color=fg),
        margin=dict(l=10, r=10, t=60, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=10),
        ),
        xaxis_rangeslider_visible=False,
    )

    # ----------------------------------------------------
    # Bollinger-Band als Shape hinter Candles
    # ----------------------------------------------------
    if {"bb_up", "bb_lo", "bb_mid"}.issubset(df.columns):
        bb_up_f = df["bb_up"].bfill().ffill()
        bb_lo_f = df["bb_lo"].bfill().ffill()

        xs = df.index
        up = bb_up_f
        lo = bb_lo_f

        # Path für gefülltes Polyon
        path = "M " + " L ".join(f"{x},{y}" for x, y in zip(xs, up))
        path += " L " + " L ".join(f"{x},{y}" for x, y in zip(xs[::-1], lo[::-1])) + " Z"

        fig.add_shape(
            type="path",
            path=path,
            fillcolor=BB_FILL,
            line=dict(width=0),
            layer="below",
            row=1,
            col=1,
        )

        # BB Linien
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=up,
                name="BB Upper",
                mode="lines",
                line=dict(width=1, color=BB_LINE),
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=lo,
                name="BB Lower",
                mode="lines",
                line=dict(width=1, color=BB_LINE),
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=df["bb_mid"],
                name="BB Basis",
                mode="lines",
                line=dict(width=1, dash="dot", color=BB_MID),
            ),
            row=1, col=1
        )

    # ----------------------------------------------------
    # Candles
    # ----------------------------------------------------
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color=BULL,
            increasing_fillcolor=BULL,
            decreasing_line_color=BEAR,
            decreasing_fillcolor=BEAR,
        ),
        row=1, col=1
    )

    # ----------------------------------------------------
    # EMAs + MA200
    # ----------------------------------------------------
    if "ema20" in df:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["ema20"],
                name="EMA20",
                mode="lines",
                line=dict(width=1.5, color=EMA20_COLOR),
            ),
            row=1, col=1
        )

    if "ema50" in df:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["ema50"],
                name="EMA50",
                mode="lines",
                line=dict(width=1.5, color=EMA50_COLOR),
            ),
            row=1, col=1
        )

    if "ma200" in df:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["ma200"],
                name="MA200",
                mode="lines",
                line=dict(width=1.5, color=MA200_COLOR),
            ),
            row=1, col=1
        )

    # ----------------------------------------------------
    # Volume (Secondary Y)
    # ----------------------------------------------------
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["volume"],
            name="Volume",
            opacity=0.35,
            marker=dict(color="#f59e0b"),
        ),
        row=1,
        col=1,
        secondary_y=True,
    )

    # ----------------------------------------------------
    # RSI Panel
    # ----------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["rsi14"],
            name="RSI14",
            mode="lines",
            line=dict(width=1.4, color="#a855f7"),
        ),
        row=2, col=1
    )

    # RSI Level lines
    line_color = "#e5e7eb" if theme == "Dark" else "#6B7280"

    fig.add_hline(y=70, line_dash="dash", line_color=line_color, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color=line_color, row=2, col=1)

    # ----------------------------------------------------
    # Axes Styling
    # ----------------------------------------------------
    fig.update_yaxes(
        title_text="Price",
        showgrid=True,
        gridcolor=grid,
        row=1, col=1
    )

    fig.update_yaxes(
        title_text="",
        showgrid=False,
        row=1, col=1,
        secondary_y=True,
    )

    fig.update_yaxes(
        title_text="RSI",
        range=[0, 100],
        showgrid=True,
        gridcolor=grid,
        row=2, col=1,
    )

    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_xaxes(showgrid=False, row=1, col=1)

    return fig


# ---------------------------------------------------------
# SIGNAL HISTORY
# ---------------------------------------------------------
def create_signal_history_figure(df: pd.DataFrame, allowed: list, theme: str):
    """
    Zeigt STRONG BUY / BUY / SELL / STRONG SELL
    OHNE HOLD.
    """

    levels = {
        "STRONG BUY": 2,
        "BUY": 1,
        "SELL": -1,
        "STRONG SELL": -2,
    }

    df2 = df[df["signal"].isin(levels.keys())].copy()
    if df2.empty:
        return go.Figure()

    df2["lvl"] = df2["signal"].map(levels)

    layout_kwargs = base_layout_kwargs(theme)
    bg = layout_kwargs["plot_bgcolor"]
    fg = layout_kwargs["font"]["color"]
    grid = grid_color_for_theme(theme)

    fig = go.Figure()

    for sig, lvl in levels.items():
        if sig not in allowed:
            continue

        sub = df2[df2["signal"] == sig]
        if sub.empty:
            continue

        fig.add_trace(
            go.Scatter(
                x=sub.index,
                y=[lvl] * len(sub),
                mode="markers",
                name=sig,
                marker=dict(
                    size=9,
                    color=signal_colors.get(sig, "#ffffff"),
                    line=dict(width=0)
                ),
                text=sub["signal_reason"],
                hovertemplate="<b>%{x}</b><br>Signal: " + sig + "<br>%{text}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Signal History",
        height=220,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        font=dict(color=fg),
        showlegend=True,
    )

    fig.update_yaxes(
        tickvals=[-2, -1, 1, 2],
        ticktext=["STRONG SELL", "SELL", "BUY", "STRONG BUY"],
        range=[-2.5, 2.5],
        showgrid=True,
        gridcolor=grid,
    )

    return fig
