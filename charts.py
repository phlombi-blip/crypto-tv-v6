# charts.py

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Nur für die Signal-Historie Punkte
signal_colors = {
    "STRONG BUY": "#00e676",  # kräftiges Grün
    "BUY": "#81c784",         # helleres Grün
    "SELL": "#e57373",        # hellrot
    "STRONG SELL": "#d32f2f", # kräftiges Rot
}


def base_layout_kwargs(theme: str):
    if theme == "Dark":
        bg, fg = "#020617", "#E5E7EB"
    else:
        bg, fg = "#FFFFFF", "#111827"

    return dict(
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        font=dict(color=fg),
    )


def grid_color_for_theme(theme: str) -> str:
    return "#111827" if theme == "Dark" else "#E5E7EB"


def create_price_rsi_figure(df, symbol_label, timeframe_label, theme):
    """
    Ein gemeinsamer Plot mit 2 Reihen:
    - oben: Price + EMA + Bollinger + Volume
    - unten: RSI (14)
    shared_xaxes=True → Zoom & Range sind synchron.
    """

    # --- Farb-Setup (TradingView-like) ---
    BULL_COLOR = "#22c55e"   # grüne Candles
    BEAR_COLOR = "#ef4444"   # rote Candles

    EMA20_COLOR = "#2962FF"
    EMA50_COLOR = "#FF6D00"
    EMA200_COLOR = "#C51162"

    # Bollinger-Farben (leicht ausgegraut)
    if theme == "Dark":
        BB_LINE_COLOR = "#9ca3af"                      # hellgrau
        BB_FILL_COLOR = "rgba(156,163,175,0.10)"       # sanftes transparentes Grau
        BB_MID_COLOR = "#6b7280"                       # Midline etwas dunkler
    else:
        BB_LINE_COLOR = "#6b7280"                      # neutral grau
        BB_FILL_COLOR = "rgba(107,114,128,0.10)"       # dezentes Grau
        BB_MID_COLOR = "#4b5563"

    layout_kwargs = base_layout_kwargs(theme)
    bg = layout_kwargs["plot_bgcolor"]
    fg = layout_kwargs["font"]["color"]
    grid = grid_color_for_theme(theme)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.03,
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        subplot_titles=(f"{symbol_label}/USD — {timeframe_label}", "RSI (14)"),
    )

    fig.update_layout(
        height=720,
        hovermode="x unified",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=10),
        ),
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        font=dict(color=fg),
        margin=dict(l=10, r=10, t=60, b=40),
        xaxis_rangeslider_visible=False,
    )

    # --- OBERES PANEL: BOLLINGER + PRICE + VOLUME ---

    # 1) Bollinger-Band (Fläche + Linien)
    has_bb = {"bb_up", "bb_lo", "bb_mid"}.issubset(df.columns)

    bb_up_f = bb_lo_f = bb_mid_f = None
    if has_bb and df["bb_up"].notna().any():
        bb_up_f = df["bb_up"].bfill().ffill()
        bb_lo_f = df["bb_lo"].bfill().ffill()
        bb_mid_f = df["bb_mid"].bfill().ffill()

        # Fläche: erst untere Linie (unsichtbar), dann obere mit fill='tonexty'
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=bb_lo_f,
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=bb_up_f,
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
                fill="tonexty",
                fillcolor=BB_FILL_COLOR,
                name="BB Range",
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

        # obere & untere Linie
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=bb_up_f,
                name="BB Upper",
                mode="lines",
                line=dict(width=1.2, color=BB_LINE_COLOR),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=bb_lo_f,
                name="BB Lower",
                mode="lines",
                line=dict(width=1.2, color=BB_LINE_COLOR),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

        # Midline (Basis, punktiert)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=bb_mid_f,
                name="BB Basis",
                mode="lines",
                line=dict(width=1, dash="dot", color=BB_MID_COLOR),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

    # 2) Candles (liegen über dem Band)
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_fillcolor=BULL_COLOR,
            increasing_line_color=BULL_COLOR,
            decreasing_fillcolor=BEAR_COLOR,
            decreasing_line_color=BEAR_COLOR,
        ),
        row=1,
        col=1,
        secondary_y=False,
    )

    # 3) EMA20 / EMA50 / MA200
    if "ema20" in df:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["ema20"],
                name="EMA20",
                mode="lines",
                line=dict(width=1.5, color=EMA20_COLOR),
            ),
            row=1,
            col=1,
            secondary_y=False,
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
            row=1,
            col=1,
            secondary_y=False,
        )

    if "ma200" in df:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["ma200"],
                name="MA200",
                mode="lines",
                line=dict(width=1.5, color=EMA200_COLOR),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

    # 4) Volume auf zweiter Y-Achse
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["volume"],
            name="Volume",
            opacity=0.3,
            marker=dict(color="#f59e0b"),
        ),
        row=1,
        col=1,
        secondary_y=True,
    )

    # --- UNTERES PANEL: RSI (14) ---
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["rsi14"],
            mode="lines",
            name="RSI14",
            line=dict(width=1.5, color="#a855f7"),
        ),
        row=2,
        col=1,
    )

    # RSI Level-Linien (nur im unteren Panel)
    line_color = "#e5e7eb" if theme == "Dark" else "#6B7280"
    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color=line_color,
        line_width=1,
        row=2,
        col=1,
    )
    fig.add_hline(
        y=30,
        line_dash="dash",
        line_color=line_color,
        line_width=1,
        row=2,
        col=1,
    )

    # --- Layout / Achsen ---
    fig.update_yaxes(
        title_text="Price",
        showgrid=True,
        gridcolor=grid,
        row=1,
        col=1,
        secondary_y=False,
    )

    fig.update_yaxes(
        title_text="",
        showgrid=False,
        row=1,
        col=1,
        secondary_y=True,
    )

    fig.update_yaxes(
        title_text="RSI",
        range=[0, 100],
        showgrid=True,
        gridcolor=grid,
        row=2,
        col=1,
    )

    fig.update_xaxes(
        title_text="Time",
        showgrid=False,
        row=2,
        col=1,
    )
    fig.update_xaxes(showgrid=False, row=1, col=1)

    return fig


def create_signal_history_figure(df, allowed, theme):
    """Signal-Historie als eigener Chart – mit Begründung im Hover."""
    fig = go.Figure()

    # y-Level ohne HOLD
    levels = {
        "STRONG SELL": -2,
        "SELL": -1,
        "BUY": 1,
        "STRONG BUY": 2,
    }

    if "signal" not in df.columns:
        df = df.copy()
        df["signal"] = "NO DATA"

    if "signal_reason" not in df.columns:
        df = df.copy()
        df["signal_reason"] = ""

    df2 = df[df["signal"].isin(levels.keys())].copy()
    df2["lvl"] = df2["signal"].map(levels)
    df2 = df2[df2["signal"].isin(allowed)]

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
                    line=dict(width=0),
                ),
                text=sub["signal_reason"],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"Signal: {sig}<br>"
                    "%{text}<extra></extra>"
                ),
            )
        )

    layout_kwargs = base_layout_kwargs(theme)
    bg = layout_kwargs["plot_bgcolor"]
    fg = layout_kwargs["font"]["color"]
    grid = grid_color_for_theme(theme)

    fig.update_layout(
        title="Signal History",
        height=220,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        font=dict(color=fg),
    )

    fig.update_yaxes(
        tickvals=[-2, -1, 1, 2],
        ticktext=list(levels.keys()),
        range=[-2.5, 2.5],
        showgrid=True,
        gridcolor=grid,
    )

    return fig
