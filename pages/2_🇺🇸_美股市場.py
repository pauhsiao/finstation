import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.us_stocks import get_us_stock_price, get_us_stock_info, get_major_indices

load_dotenv()

st.set_page_config(page_title="美股市場 | FinStation", page_icon="🇺🇸", layout="wide")
st.title("🇺🇸 美股市場")

# 主要指數概覽
st.subheader("主要指數")
with st.spinner("載入指數數據..."):
    indices = get_major_indices()

if indices:
    cols = st.columns(len(indices))
    for col, idx in zip(cols, indices):
        arrow = "▲" if idx["change_pct"] >= 0 else "▼"
        color = "normal" if idx["change_pct"] >= 0 else "inverse"
        col.metric(
            idx["name"],
            f"{idx['price']:,.2f}",
            f"{arrow} {idx['change_pct']:+.2f}%",
            delta_color=color,
        )
else:
    st.warning("指數數據暫時無法取得")

st.divider()

# 個股查詢
st.subheader("個股查詢")
col1, col2 = st.columns([2, 1])

with col1:
    ticker = st.text_input("輸入美股代號（例如：AAPL、NVDA、TSLA）", value="NVDA")

with col2:
    period = st.selectbox("時間區間", ["1mo", "3mo", "6mo", "1y", "2y"], index=2,
                          format_func=lambda x: {"1mo": "1個月", "3mo": "3個月",
                                                  "6mo": "6個月", "1y": "1年", "2y": "2年"}[x])

if ticker:
    with st.spinner(f"載入 {ticker} 數據..."):
        df = get_us_stock_price(ticker.upper().strip(), period=period)
        info = get_us_stock_info(ticker.upper().strip())

    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        change = latest["Close"] - prev["Close"]
        change_pct = change / prev["Close"] * 100

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("公司名稱", info.get("name", ticker)[:20])
        mc2.metric("收盤價 (USD)", f"${latest['Close']:.2f}", f"{change_pct:+.2f}%")
        mc3.metric("產業", info.get("sector", "—"))
        mktcap = info.get("market_cap")
        mc4.metric("市值", f"${mktcap/1e9:.1f}B" if mktcap else "—")

        # K 線圖
        fig = go.Figure(data=[go.Candlestick(
            x=df["Date"],
            open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            increasing_line_color="#ff4b4b",
            decreasing_line_color="#00cc44",
            name=ticker
        )])
        fig.update_layout(
            template="plotly_dark",
            height=400,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_rangeslider_visible=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        info_cols = st.columns(3)
        info_cols[0].metric("本益比 (P/E)", f"{info.get('pe_ratio', '—'):.1f}" if info.get('pe_ratio') else "—")
        info_cols[1].metric("52週高點", f"${info.get('52w_high', '—'):.2f}" if info.get('52w_high') else "—")
        info_cols[2].metric("52週低點", f"${info.get('52w_low', '—'):.2f}" if info.get('52w_low') else "—")
    else:
        st.error(f"找不到 {ticker} 的數據，請確認代號是否正確")
