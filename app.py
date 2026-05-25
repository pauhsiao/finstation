import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="FinStation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "watchlist_tw" not in st.session_state:
    st.session_state["watchlist_tw"] = ["2330", "2454", "2317", "2308", "2891"]

st.title("📊 FinStation")
st.caption("個人金融研究工作站")

# Market overview
st.subheader("市場概覽")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))


@st.cache_data(ttl=300)
def load_taiex():
    from data.taiwan_stocks import get_taiwan_market_summary
    return get_taiwan_market_summary()


@st.cache_data(ttl=300)
def load_indices():
    from data.us_stocks import get_major_indices
    return get_major_indices()


col_tw, col_us = st.columns(2)

with col_tw:
    st.markdown("**🇹🇼 台股**")
    try:
        taiex = load_taiex()
        if not taiex.empty:
            latest = taiex.iloc[-1]
            prev = taiex.iloc[-2] if len(taiex) > 1 else latest
            change = latest["Close"] - prev["Close"]
            change_pct = change / prev["Close"] * 100
            st.metric("加權指數 TAIEX", f"{latest['Close']:,.2f}",
                      f"{'▲' if change >= 0 else '▼'} {change_pct:+.2f}%")
    except Exception:
        st.caption("數據暫時無法取得")

with col_us:
    st.markdown("**🇺🇸 美股**")
    try:
        indices = load_indices()
        if indices:
            show = [i for i in indices if i["name"] in ("S&P 500", "NASDAQ", "Dow Jones")][:3]
            sub_cols = st.columns(len(show)) if show else []
            for col, idx in zip(sub_cols, show):
                arrow = "▲" if idx["change_pct"] >= 0 else "▼"
                col.metric(idx["name"], f"{idx['price']:,.2f}",
                           f"{arrow} {idx['change_pct']:+.2f}%")
    except Exception:
        st.caption("數據暫時無法取得")

st.divider()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.info("🇹🇼 **台股市場**\n\nK線 + 技術指標")
with col2:
    st.info("🇺🇸 **美股市場**\n\n指數 + 個股查詢")
with col3:
    st.info("🌐 **總體經濟**\n\n利率、CPI、殖利率")
with col4:
    st.info("📰 **財經新聞**\n\n即時新聞動態")
with col5:
    st.info("⭐ **自選股**\n\n追蹤你的持股清單")

st.divider()
st.caption("Phase 2 — 技術指標 + 成交量 + 自選股")
