import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="FinStation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 FinStation")
st.caption("個人金融研究工作站 — Bloomberg + TradingView + AI，一站搞定")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.info("🇹🇼 **台股市場**\n\n查詢個股行情、K線圖、技術分析")

with col2:
    st.info("🇺🇸 **美股市場**\n\n S&P500、納斯達克、個股查詢")

with col3:
    st.info("🌐 **總體經濟**\n\n利率、CPI、失業率、殖利率曲線")

with col4:
    st.info("📰 **財經新聞**\n\n即時新聞、台股 & 國際市場動態")

st.divider()
st.markdown("""
**使用方式：**
- 左側選單選擇功能模組
- 每個頁面可獨立查詢不同數據

**目前版本：** Phase 1 — 數據基礎層
""")
