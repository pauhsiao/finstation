import streamlit as st
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.us_stocks import get_us_stock_price, get_us_stock_info, get_major_indices
from utils.charts import build_stock_chart

load_dotenv()

st.set_page_config(page_title="美股市場 | FinStation", page_icon="🇺🇸", layout="wide")
st.title("🇺🇸 美股市場")


@st.cache_data(ttl=300)
def cached_indices():
    return get_major_indices()


@st.cache_data(ttl=300)
def cached_us_stock(ticker: str, period: str):
    return get_us_stock_price(ticker, period=period), get_us_stock_info(ticker)


# 主要指數
st.subheader("主要指數")
with st.spinner("載入指數數據..."):
    indices = cached_indices()

if indices:
    cols = st.columns(len(indices))
    for col, idx in zip(cols, indices):
        arrow = "▲" if idx["change_pct"] >= 0 else "▼"
        col.metric(idx["name"], f"{idx['price']:,.2f}",
                   f"{arrow} {idx['change_pct']:+.2f}%",
                   delta_color="normal" if idx["change_pct"] >= 0 else "inverse")
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

with st.expander("📐 技術指標設定", expanded=False):
    ic1, ic2, ic3, ic4, ic5 = st.columns(5)
    show_ma = ic1.checkbox("均線 MA", value=True)
    show_vol = ic2.checkbox("成交量", value=True)
    show_rsi = ic3.checkbox("RSI(14)", value=False)
    show_macd = ic4.checkbox("MACD", value=False)
    show_bb = ic5.checkbox("布林通道", value=False)

if ticker:
    with st.spinner(f"載入 {ticker} 數據..."):
        df, info = cached_us_stock(ticker.upper().strip(), period)

    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        change = latest["Close"] - prev["Close"]
        change_pct = change / prev["Close"] * 100
        arrow = "🔺" if change >= 0 else "🔻"

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("公司名稱", info.get("name", ticker)[:20])
        mc2.metric("收盤價 (USD)", f"${latest['Close']:.2f}",
                   f"{arrow} {change_pct:+.2f}%")
        mc3.metric("產業", info.get("sector", "—"))
        mktcap = info.get("market_cap")
        mc4.metric("市值", f"${mktcap/1e9:.1f}B" if mktcap else "—")

        fig = build_stock_chart(
            df, ticker.upper().strip(),
            date_col="Date",
            show_ma=show_ma, show_volume=show_vol,
            show_rsi=show_rsi, show_macd=show_macd, show_bb=show_bb,
        )
        st.plotly_chart(fig, use_container_width=True)

        info_cols = st.columns(3)
        pe = info.get("pe_ratio")
        h52 = info.get("52w_high")
        l52 = info.get("52w_low")
        info_cols[0].metric("本益比 (P/E)", f"{pe:.1f}" if pe else "—")
        info_cols[1].metric("52週高點", f"${h52:.2f}" if h52 else "—")
        info_cols[2].metric("52週低點", f"${l52:.2f}" if l52 else "—")
    else:
        st.error(f"找不到 {ticker} 的數據，請確認代號是否正確")
