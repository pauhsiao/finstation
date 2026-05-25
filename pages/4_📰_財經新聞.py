import streamlit as st
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.news import get_financial_news

load_dotenv()

st.set_page_config(page_title="財經新聞 | FinStation", page_icon="📰", layout="wide")
st.title("📰 財經新聞")

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("搜尋關鍵字", value="Taiwan stock market")
with col2:
    days = st.selectbox("時間範圍", [1, 3, 7], index=1, format_func=lambda x: f"最近 {x} 天")

with st.spinner("載入新聞..."):
    news = get_financial_news(query=query, days=days, page_size=15)

if not news:
    st.info("沒有找到相關新聞，或 NewsAPI Key 未設定（未設定時自動使用 Yahoo Finance RSS）")
else:
    st.caption(f"共找到 {len(news)} 則新聞")
    for article in news:
        with st.container():
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.markdown(f"**[{article['title']}]({article['url']})**")
                if article.get("description"):
                    st.caption(article["description"][:150] + "...")
            with col_b:
                st.caption(article["published"])
                st.caption(f"📌 {article['source']}")
            st.divider()
