import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_taiwan_stock_info, get_taiwan_market_summary
from utils.charts import build_stock_chart

load_dotenv()

st.set_page_config(page_title="台股市場 | FinStation", page_icon="🇹🇼", layout="wide")
st.title("🇹🇼 台股市場")

if "watchlist_tw" not in st.session_state:
    st.session_state["watchlist_tw"] = ["2330", "2454", "2317", "2308", "2891"]


@st.cache_data(ttl=300)
def cached_taiex():
    return get_taiwan_market_summary()


@st.cache_data(ttl=300)
def cached_stock(stock_id: str, days: int):
    return get_taiwan_stock_price(stock_id, days=days), get_taiwan_stock_info(stock_id)


# 大盤
st.subheader("加權指數（TAIEX）")
with st.spinner("載入大盤數據..."):
    taiex = cached_taiex()

if not taiex.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=taiex["date"], y=taiex["Close"],
        mode="lines", name="TAIEX",
        line=dict(color="#00d4ff", width=2),
        fill="tozeroy", fillcolor="rgba(0,212,255,0.05)",
    ))
    fig.update_layout(
        template="plotly_dark",
        height=240,
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

# 技術指標
with st.expander("📐 技術指標設定", expanded=False):
    ic1, ic2, ic3, ic4, ic5 = st.columns(5)
    show_ma = ic1.checkbox("均線 MA", value=True)
    show_vol = ic2.checkbox("成交量", value=True)
    show_rsi = ic3.checkbox("RSI(14)", value=False)
    show_macd = ic4.checkbox("MACD", value=False)
    show_bb = ic5.checkbox("布林通道", value=False)

if stock_id:
    with st.spinner(f"載入 {stock_id} 數據..."):
        df, info = cached_stock(stock_id.strip(), days)

    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        change = latest["Close"] - prev["Close"]
        change_pct = change / prev["Close"] * 100
        color_arrow = "🔺" if change >= 0 else "🔻"

        mc1, mc2, mc3, mc4, mc5 = st.columns([2, 2, 1, 1, 1])
        mc1.metric("股票名稱", info.get("stock_name", stock_id))
        mc2.metric("收盤價", f"{latest['Close']:.2f}",
                   f"{color_arrow} {change:+.2f} ({change_pct:+.2f}%)")
        mc3.metric("最高", f"{latest.get('High', 0):.2f}")
        mc4.metric("最低", f"{latest.get('Low', 0):.2f}")

        wl = st.session_state["watchlist_tw"]
        in_wl = stock_id.strip() in wl
        btn_label = "⭐ 移除自選" if in_wl else "☆ 加入自選"
        if mc5.button(btn_label):
            if in_wl:
                wl.remove(stock_id.strip())
            else:
                wl.append(stock_id.strip())
            st.rerun()

        fig = build_stock_chart(
            df, stock_id.strip(),
            show_ma=show_ma, show_volume=show_vol,
            show_rsi=show_rsi, show_macd=show_macd, show_bb=show_bb,
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("查看原始數據"):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.error(f"找不到股票 {stock_id} 的數據，請確認代號是否正確")
