import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_taiwan_stock_info, get_taiwan_market_summary

load_dotenv()

st.set_page_config(page_title="台股市場 | FinStation", page_icon="🇹🇼", layout="wide")
st.title("🇹🇼 台股市場")

# 大盤走勢
st.subheader("加權指數（TAIEX）")
with st.spinner("載入大盤數據..."):
    taiex = get_taiwan_market_summary()

if not taiex.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=taiex["date"], y=taiex["Close"],
        mode="lines", name="TAIEX",
        line=dict(color="#00d4ff", width=2)
    ))
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="", yaxis_title="點數",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("大盤數據暫時無法取得")

st.divider()

# 個股查詢
st.subheader("個股行情")
col1, col2 = st.columns([2, 1])

with col1:
    stock_id = st.text_input("輸入股票代號（例如：2330、2317、6472）", value="2330")

with col2:
    period = st.selectbox("時間區間", ["30天", "90天", "180天", "365天"], index=2)

period_map = {"30天": 30, "90天": 90, "180天": 180, "365天": 365}
days = period_map[period]

if stock_id:
    with st.spinner(f"載入 {stock_id} 數據..."):
        df = get_taiwan_stock_price(stock_id.strip(), days=days)
        info = get_taiwan_stock_info(stock_id.strip())

    if not df.empty:
        # 基本資訊列
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        change = latest["Close"] - prev["Close"]
        change_pct = change / prev["Close"] * 100
        color = "🟢" if change >= 0 else "🔴"

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("股票名稱", info.get("stock_name", stock_id))
        mc2.metric("收盤價", f"{latest['Close']:.2f}", f"{color} {change:+.2f} ({change_pct:+.2f}%)")
        mc3.metric("最高", f"{latest.get('High', '—'):.2f}" if "High" in latest else "—")
        mc4.metric("最低", f"{latest.get('Low', '—'):.2f}" if "Low" in latest else "—")

        # K 線圖
        if all(c in df.columns for c in ["Open", "High", "Low", "Close"]):
            fig2 = go.Figure(data=[go.Candlestick(
                x=df["date"],
                open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"],
                increasing_line_color="#ff4b4b",
                decreasing_line_color="#00cc44",
                name=stock_id
            )])
        else:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df["date"], y=df["Close"], mode="lines", name=stock_id))

        fig2.update_layout(
            template="plotly_dark",
            height=400,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_rangeslider_visible=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 原始數據
        with st.expander("查看原始數據"):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.error(f"找不到股票 {stock_id} 的數據，請確認代號是否正確")
