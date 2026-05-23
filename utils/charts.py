from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

MA_COLORS = {
    5:   "#FFD700",
    10:  "#FFA040",
    20:  "#00BFFF",
    30:  "#7FFF00",
    60:  "#FF69B4",
    200: "#FF6347",
}


def _add_ma_traces(fig: go.Figure, df: pd.DataFrame, mas: list[int], row: int = 1):
    for period in mas:
        if len(df) >= period:
            ma = df["Close"].rolling(window=period).mean()
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=ma,
                    mode="lines",
                    name=f"MA{period}",
                    line=dict(color=MA_COLORS.get(period, "#AAAAAA"), width=1.2),
                    opacity=0.9,
                ),
                row=row, col=1,
            )


def create_candlestick_chart(
    df: pd.DataFrame,
    ticker: str,
    label: str = "",
    mas: list[int] | None = None,
) -> go.Figure:
    if mas is None:
        mas = []

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"],
            low=df["Low"],   close=df["Close"],
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
            name="K線",
        ),
        row=1, col=1,
    )

    _add_ma_traces(fig, df, mas, row=1)

    bar_colors = [
        "#ef5350" if c >= o else "#26a69a"
        for o, c in zip(df["Open"], df["Close"])
    ]
    fig.add_trace(
        go.Bar(x=df.index, y=df["Volume"], marker_color=bar_colors, name="成交量", opacity=0.7),
        row=2, col=1,
    )

    fig.update_layout(
        title=label or ticker,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=620,
        margin=dict(l=0, r=10, t=50, b=0),
        legend=dict(orientation="h", y=1.04, x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)")
    return fig


def create_line_chart(
    df: pd.DataFrame,
    ticker: str,
    label: str = "",
    mas: list[int] | None = None,
) -> go.Figure:
    if mas is None:
        mas = []

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    color = "#ef5350" if df["Close"].iloc[-1] >= df["Close"].iloc[0] else "#26a69a"
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["Close"],
            mode="lines", name="收盤價",
            line=dict(color=color, width=2),
            fill="tozeroy", fillcolor=f"{color}18",
        ),
        row=1, col=1,
    )

    _add_ma_traces(fig, df, mas, row=1)

    fig.add_trace(
        go.Bar(x=df.index, y=df["Volume"], marker_color="rgba(100,149,237,0.6)", name="成交量"),
        row=2, col=1,
    )

    fig.update_layout(
        title=label or ticker,
        template="plotly_dark",
        height=620,
        margin=dict(l=0, r=10, t=50, b=0),
        legend=dict(orientation="h", y=1.04, x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)")
    return fig
