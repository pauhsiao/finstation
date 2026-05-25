import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from data.indicators import add_moving_averages, add_rsi, add_macd, add_bollinger_bands


def build_stock_chart(
    df: pd.DataFrame,
    stock_id: str,
    date_col: str = "date",
    show_ma: bool = True,
    show_volume: bool = True,
    show_rsi: bool = False,
    show_macd: bool = False,
    show_bb: bool = False,
) -> go.Figure:
    df = add_moving_averages(df)
    if show_rsi:
        df = add_rsi(df)
    if show_macd:
        df = add_macd(df)
    if show_bb:
        df = add_bollinger_bands(df)

    has_volume = show_volume and "Volume" in df.columns and df["Volume"].sum() > 0

    subplot_rows = ["candle"]
    if has_volume:
        subplot_rows.append("volume")
    if show_rsi:
        subplot_rows.append("rsi")
    if show_macd:
        subplot_rows.append("macd")

    n_rows = len(subplot_rows)
    height_map = {"candle": 0.55, "volume": 0.15, "rsi": 0.15, "macd": 0.15}
    raw_heights = [height_map[r] for r in subplot_rows]
    total = sum(raw_heights)
    row_heights = [h / total for h in raw_heights]
    row_idx = {name: i + 1 for i, name in enumerate(subplot_rows)}

    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # Candlestick or line
    has_ohlc = all(c in df.columns for c in ["Open", "High", "Low", "Close"])
    if has_ohlc:
        fig.add_trace(go.Candlestick(
            x=df[date_col],
            open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            increasing_line_color="#ff4b4b",
            decreasing_line_color="#00cc44",
            name=stock_id, showlegend=False,
        ), row=row_idx["candle"], col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df["Close"],
            mode="lines", name=stock_id,
            line=dict(color="#00d4ff", width=2),
        ), row=row_idx["candle"], col=1)

    # Moving averages
    if show_ma:
        for ma, color in [("MA5", "#f0e68c"), ("MA20", "#00bfff"), ("MA60", "#ff8c00")]:
            if ma in df.columns:
                fig.add_trace(go.Scatter(
                    x=df[date_col], y=df[ma],
                    mode="lines", name=ma,
                    line=dict(color=color, width=1),
                ), row=row_idx["candle"], col=1)

    # Bollinger Bands
    if show_bb and "BB_Upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df["BB_Upper"],
            mode="lines", name="BB上軌",
            line=dict(color="rgba(180,160,255,0.7)", width=1, dash="dot"),
        ), row=row_idx["candle"], col=1)
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df["BB_Lower"],
            mode="lines", name="BB下軌",
            line=dict(color="rgba(180,160,255,0.7)", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(150,130,255,0.06)",
        ), row=row_idx["candle"], col=1)

    # Volume
    if has_volume:
        colors = ["#ff4b4b" if c >= o else "#00cc44"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df[date_col], y=df["Volume"],
            name="成交量", marker_color=colors, showlegend=False,
        ), row=row_idx["volume"], col=1)
        fig.update_yaxes(title_text="量", title_font_size=10, row=row_idx["volume"], col=1)

    # RSI
    if show_rsi and "RSI" in df.columns:
        r = row_idx["rsi"]
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df["RSI"],
            mode="lines", name="RSI(14)",
            line=dict(color="#ff69b4", width=1.5),
        ), row=r, col=1)
        x0, x1 = df[date_col].iloc[0], df[date_col].iloc[-1]
        for level, color in [(70, "rgba(255,80,80,0.5)"), (30, "rgba(80,220,80,0.5)"), (50, "rgba(150,150,150,0.3)")]:
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[level, level],
                mode="lines", showlegend=False,
                line=dict(color=color, width=1, dash="dot"),
            ), row=r, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], title_font_size=10, row=r, col=1)

    # MACD
    if show_macd and "MACD" in df.columns:
        r = row_idx["macd"]
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df["MACD"],
            mode="lines", name="MACD",
            line=dict(color="#00bfff", width=1.5),
        ), row=r, col=1)
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df["MACD_Signal"],
            mode="lines", name="Signal",
            line=dict(color="#ff8c00", width=1.5),
        ), row=r, col=1)
        hist_colors = ["#ff4b4b" if v >= 0 else "#00cc44" for v in df["MACD_Hist"]]
        fig.add_trace(go.Bar(
            x=df[date_col], y=df["MACD_Hist"],
            name="Hist", marker_color=hist_colors, showlegend=False,
        ), row=r, col=1)
        fig.update_yaxes(title_text="MACD", title_font_size=10, row=r, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=400 + (n_rows - 1) * 130,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="right", x=1, font_size=11,
        ),
    )

    return fig
