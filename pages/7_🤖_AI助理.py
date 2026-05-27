import streamlit as st
import anthropic
import re
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_taiwan_stock_info, get_realtime_quote, get_taiwan_market_summary
from data.news import get_financial_news
from data.db import wl_load, holdings_load
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="AI 助理 | FinStation", page_icon="🤖", layout="wide")
st.title("🤖 AI 投資助理")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


def build_stock_context(stock_id: str) -> str:
    info = get_taiwan_stock_info(stock_id)
    rt = get_realtime_quote(stock_id)
    df = get_taiwan_stock_price(stock_id, days=30)

    lines = [f"股票：{stock_id} {info.get('stock_name', '')}"]
    if rt:
        lines.append(f"現價：{rt['price']:.2f}，漲跌：{rt['change']:+.2f}（{rt['change_pct']:+.2f}%）")
    if not df.empty:
        recent = df.tail(10)
        prices = ", ".join(f"{r['Close']:.2f}" for _, r in recent.iterrows())
        lines.append(f"近10日收盤價：{prices}")
        high = df["High"].max()
        low = df["Low"].min()
        lines.append(f"近30日最高：{high:.2f}，最低：{low:.2f}")
    return "\n".join(lines)


def ask_claude(system: str, user: str) -> str:
    with st.spinner("AI 分析中..."):
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    return msg.content[0].text


tab1, tab2, tab3, tab4 = st.tabs(["📊 個股分析", "⭐ 自選股摘要", "💬 市場問答", "💼 持倉建議"])

# ── Tab 1: 個股分析 ──────────────────────────────────────────────────────
with tab1:
    col1, col2 = st.columns([3, 1])
    sid = col1.text_input("輸入股票代號", value="2330", key="ai_stock")
    if col2.button("分析", use_container_width=True, key="btn_stock"):
        ctx = build_stock_context(sid.strip())
        answer = ask_claude(
            "你是一位專業的台股分析師，用繁體中文回答，語氣簡潔專業，300字以內。",
            f"請根據以下資料分析這支股票的近期走勢與操作建議：\n\n{ctx}"
        )
        st.markdown(answer)

# ── Tab 2: 自選股摘要 ──────────────────────────────────────────────────────
with tab2:
    if st.button("一鍵分析自選股", use_container_width=True):
        wl = wl_load()
        if not wl:  # None（連線失敗）或空清單都 fallback
            wl = st.session_state.get("watchlist_tw", ["2330", "2454", "2317", "2308", "2891"])

        lines = []
        for s in wl:
            rt = get_realtime_quote(s)
            info = get_taiwan_stock_info(s)
            name = info.get("stock_name", s)
            if rt:
                lines.append(f"{s} {name}：現價 {rt['price']:.2f}，漲跌 {rt['change']:+.2f}（{rt['change_pct']:+.2f}%）")
            else:
                lines.append(f"{s} {name}：無法取得報價")

        ctx = "\n".join(lines)
        answer = ask_claude(
            "你是一位台股分析師，用繁體中文回答，語氣簡潔，400字以內。",
            f"以下是我的自選股今日行情，請幫我整理重點摘要，哪些值得關注：\n\n{ctx}"
        )
        st.markdown(answer)

# ── Tab 3: 市場問答 ──────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_taiex_context() -> str:
    df = get_taiwan_market_summary()
    if df.empty:
        return ""
    recent = df.tail(5)
    lines = ["【加權指數近5日】"]
    for _, r in recent.iterrows():
        lines.append(f"  {str(r['date'])[:10]}：{r['Close']:.0f} 點")
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    chg = latest["Close"] - prev["Close"]
    lines.append(f"  最新漲跌：{chg:+.0f} 點（{chg/prev['Close']*100:+.2f}%）")
    return "\n".join(lines)


@st.cache_data(ttl=600)
def get_news_context(query: str) -> str:
    articles = get_financial_news(query=query, days=2, page_size=5)
    if not articles:
        return ""
    lines = ["【相關新聞（近2日）】"]
    for a in articles:
        lines.append(f"  [{a['published']}] {a['title']} ({a['source']})")
    return "\n".join(lines)


def fetch_stocks_in_text(text: str) -> str:
    codes = re.findall(r'\b(\d{4})\b', text)
    if not codes:
        return ""
    parts = []
    for code in set(codes[:3]):  # 最多3支避免太慢
        info = get_taiwan_stock_info(code)
        if not info:
            continue
        rt = get_realtime_quote(code)
        df = get_taiwan_stock_price(code, days=10)
        name = info.get("stock_name", code)
        line = f"【{code} {name}】"
        if rt:
            line += f" 現價:{rt['price']:.2f} 漲跌:{rt['change']:+.2f}({rt['change_pct']:+.2f}%)"
        if not df.empty:
            recent = ", ".join(f"{r['Close']:.2f}" for _, r in df.tail(5).iterrows())
            line += f" 近5日收盤:{recent}"
        parts.append(line)
    return "\n".join(parts)

with tab3:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("問我任何台股問題..."):
        with st.chat_message("user"):
            st.markdown(prompt)

        stock_ctx = fetch_stocks_in_text(prompt)
        taiex_ctx = get_taiex_context()
        news_ctx = get_news_context(f"Taiwan stock {prompt[:50]}")

        ctx_parts = []
        if taiex_ctx:
            ctx_parts.append(taiex_ctx)
        if stock_ctx:
            ctx_parts.append(f"【個股即時資料】\n{stock_ctx}")
        if news_ctx:
            ctx_parts.append(news_ctx)

        user_content = prompt
        if ctx_parts:
            user_content = f"{prompt}\n\n" + "\n\n".join(ctx_parts)

        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        history = [{"role": m["role"], "content": m["content"]}
                   for m in st.session_state["chat_history"][:-1]]
        history.append({"role": "user", "content": user_content})

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    system="你是一位專業的台股投資顧問，用繁體中文回答，語氣簡潔務實。回答時以提供的即時市場資料為準，不要憑空猜測股票名稱或數字。",
                    messages=history,
                )
                reply = msg.content[0].text
            st.markdown(reply)

        st.session_state["chat_history"].append({"role": "assistant", "content": reply})

    if st.session_state["chat_history"]:
        if st.button("清除對話"):
            st.session_state["chat_history"] = []
            st.rerun()

# ── Tab 4: 持倉建議 ──────────────────────────────────────────────────────
with tab4:
    if st.button("分析我的持倉", use_container_width=True):
        holdings = holdings_load()
        if not holdings:
            st.info("尚無持倉紀錄，請先到「我的持倉」頁面新增")
        else:
            lines = []
            total_cost = sum(h["shares"] * h["buy_price"] for h in holdings)
            for h in holdings:
                rt = get_realtime_quote(h["stock_id"])
                cur_price = rt["price"] if rt else h["buy_price"]
                cost = h["shares"] * h["buy_price"]
                value = h["shares"] * cur_price
                pnl_pct = (value - cost) / cost * 100
                lines.append(
                    f"{h['stock_id']} {h.get('stock_name','')}："
                    f"持股 {h['shares']} 股，買入均價 {h['buy_price']:.2f}，"
                    f"現價 {cur_price:.2f}，損益 {pnl_pct:+.2f}%，"
                    f"佔總成本 {cost/total_cost*100:.1f}%"
                )
            ctx = "\n".join(lines)
            answer = ask_claude(
                "你是一位專業的投資組合顧問，用繁體中文回答，語氣簡潔，400字以內。",
                f"以下是我的持倉狀況，請分析風險集中度並給出再平衡建議：\n\n{ctx}"
            )
            st.markdown(answer)
