# charts.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import SIGNAL_COLORS


def create_price_rsi_figure(df, symbol_label, timeframe_label, theme):

    # Candles
    BULL = "#22c55e"
    BEAR = "#ef4444"

    # EMA Farben
    EMA20 = "#2962FF"
    EMA50 = "#FF6D00"
    MA200 = "#C51162"

    # Bollinger Farben (neutral grau)
    BB_LINE = "#d1d5db"
    BB_FILL = "rgba(209,213,219,0.12)"
    BB_MID = "#9ca3af"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.04,
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        subplot_titles=(f"{symbol_label}/USD – {timeframe_label}", "RSI (14)"),
    )

    # 1) BOLLINGER FILL — HINTER ALLES
    if "bb_up" in df and df["bb_up"].notna().any():
        xs = df.index
        up = df["bb_up"].bfill().ffill()
        lo = df["bb_lo"].bfill().ffill()

        fig.add_shape(
            type="rect",
            x0=xs.min(), x1=xs.max(),
            y0=lo.min(), y1=up.max(),
            fillcolor=BB_FILL,
            line=dict(width=0),
            layer="below",
            row=1, col=1,
        )

    # 2) CANDLES
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_fillcolor=BULL,
            increasing_line_color=BULL,
            decreasing_fillcolor=BEAR,
            decreasing_line_color=BEAR,
            name="Price",
        ),
        row=1, col=1
    )

    # 3) Bollinger Linien
    if "bb_up" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_up"], line=dict(color=BB_LINE, width=1), name="BB Up"), row=1, col=1)
    if "bb_lo" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_lo"], line=dict(color=BB_LINE, width=1), name="BB Low"), row=1, col=1)
    if "bb_mid" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_mid"], line=dict(color=BB_MID, width=1, dash="dot"), name="BB Mid"), row=1, col=1)

    # 4) EMA20 / EMA50 / MA200
    if "ema20" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], line=dict(color=EMA20, width=1.5), name="EMA20"), row=1, col=1)
    if "ema50" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], line=dict(color=EMA50, width=1.5), name="EMA50"), row=1, col=1)
    if "ma200" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["ma200"], line=dict(color=MA200, width=1.5), name="MA200"), row=1, col=1)

    # 5) Volume
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume", opacity=0.3, marker=dict(color="#f59e0b")),
        row=1, col=1, secondary_y=True
    )

    # RSI PANEL
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi14"], line=dict(color="#a855f7"), name="RSI14"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#aaaaaa", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#aaaaaa", row=2, col=1)

    fig.update_layout(
        height=740,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        showlegend=True
    )

    return fig


def create_signal_history_figure(df, allowed, theme):
    fig = go.Figure()

    LEVELS = {
        "STRONG SELL": -2,
        "SELL": -1,
        "BUY": 1,
        "STRONG BUY": 2,
    }

    df2 = df[df["signal"].isin(LEVELS.keys())].copy()
    df2["lvl"] = df2["signal"].map(LEVELS)
    df2 = df2[df2["signal"].isin(allowed)]

    for sig, lvl in LEVELS.items():
        sub = df2[df2["signal"] == sig]
        if sub.empty: continue
        fig.add_trace(
            go.Scatter(
                x=sub.index,
                y=[lvl] * len(sub),
                mode="markers",
                marker=dict(size=9, color=SIGNAL_COLORS.get(sig)),
                name=sig,
                text=sub["signal_reason"],
                hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
            )
        )

    fig.update_layout(
        height=240,
        hovermode="x unified",
    )
    fig.update_yaxes(
        tickvals=[-2, -1, 1, 2],
        ticktext=list(LEVELS.keys()),
        range=[-2.5, 2.5]
    )

    return fig
