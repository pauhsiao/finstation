import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="FinStation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "watchlist_tw" not in st.session_state:
    from data.db import wl_load
    loaded = wl_load()
    st.session_state["watchlist_tw"] = loaded if loaded is not None else ["2330", "2454", "2317", "2308", "2891"]

st.title("📊 FinStation")
st.caption("個人金融研究工作站")

# 防止 Ctrl+C 觸發 Streamlit 的清除快取快捷鍵
components.html("""
<script>
window.parent.document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        e.stopImmediatePropagation();
    }
}, true);
</script>
""", height=0)

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
            change_pct = change / prev["Close"] * 100 if prev["Close"] else 0
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
st.subheader("功能導覽")

pages = [
    ("pages/1_🇹🇼_台股市場.py",  "🇹🇼 台股市場",  "K線 + 技術指標 + 族群"),
    ("pages/2_🇺🇸_美股市場.py",  "🇺🇸 美股市場",  "指數 + 個股查詢"),
    ("pages/3_🌐_總體經濟.py",   "🌐 總體經濟",   "利率、CPI、殖利率"),
    ("pages/4_📰_財經新聞.py",   "📰 財經新聞",   "即時新聞動態"),
    ("pages/5_⭐_自選股.py",     "⭐ 自選股",     "追蹤你的持股清單"),
    ("pages/6_💼_我的持倉.py",   "💼 我的持倉",   "損益計算 + 圖表"),
    ("pages/7_🤖_AI助理.py",    "🤖 AI 投資助理", "個股分析 + 市場問答"),
    ("pages/8_📈_回測分析.py",   "📈 量化回測",   "策略回測 + 風險分析"),
    ("pages/9_🏆_股票篩選.py",   "🏆 股票篩選",   "多條件選股"),
]

for i in range(0, len(pages), 2):
    c1, c2 = st.columns(2)
    with c1:
        path, label, desc = pages[i]
        st.page_link(path, label=f"**{label}**\n\n{desc}", use_container_width=True)
    if i + 1 < len(pages):
        with c2:
            path, label, desc = pages[i + 1]
            st.page_link(path, label=f"**{label}**\n\n{desc}", use_container_width=True)
