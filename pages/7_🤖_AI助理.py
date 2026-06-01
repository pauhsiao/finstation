import streamlit as st
import anthropic
import re
import sys, os
import plotly.graph_objects as go
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import (get_taiwan_stock_price, get_taiwan_stock_info,
                                 get_realtime_quote, get_taiwan_market_summary,
                                 search_taiwan_stocks, get_financial_statements,
                                 get_monthly_revenue)
from data.news import get_financial_news
from data.db import wl_load, holdings_load
from utils.ai import ask_claude as _ask_claude
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


def ask_claude(system: str, user: str, max_tokens: int = 1024) -> str:
    with st.spinner("AI 分析中..."):
        return _ask_claude(system, user, max_tokens)


tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 個股分析", "⭐ 自選股摘要", "💬 市場問答",
    "💼 持倉建議", "📈 財報分析", "📰 新聞情緒",
])

# ── Tab 1: 個股分析 ──────────────────────────────────────────────────────
with tab1:
    col1, col2 = st.columns([3, 1])
    keyword = col1.text_input("輸入股票代號或中文名稱", value="2330", key="ai_stock")
    sid = keyword.strip()
    if sid and not sid.isdigit():
        matches = search_taiwan_stocks(sid)
        if matches:
            options = [f"{s['stock_id']} {s['stock_name']}" for s in matches[:10]]
            chosen = st.selectbox("搜尋結果，請選擇：", options, key="ai_stock_pick")
            sid = chosen.split(" ")[0]
        else:
            st.warning(f"找不到「{sid}」，請確認名稱或代號")
            sid = ""
    if col2.button("分析", use_container_width=True, key="btn_stock") and sid:
        ctx = build_stock_context(sid)
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
                    model="claude-sonnet-4-6",
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

# ── Tab 4: 持倉建議 ──────────────────────────────────────────────────────────
with tab4:
    if st.button("分析我的持倉", use_container_width=True):
        holdings = holdings_load()
        if holdings is None:
            st.error("⚠️ 無法連線 Supabase，請稍後再試")
        elif not holdings:
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

# ── Tab 5: 財報分析 ──────────────────────────────────────────────────────────
with tab5:
    col1, col2 = st.columns([3, 1])
    fs_keyword = col1.text_input("輸入股票代號或中文名稱", value="2330", key="fs_stock")
    fs_sid = fs_keyword.strip()
    if fs_sid and not fs_sid.isdigit():
        matches = search_taiwan_stocks(fs_sid)
        if matches:
            options = [f"{s['stock_id']} {s['stock_name']}" for s in matches[:10]]
            chosen = st.selectbox("搜尋結果：", options, key="fs_stock_pick")
            fs_sid = chosen.split(" ")[0]
        else:
            st.warning(f"找不到「{fs_sid}」")
            fs_sid = ""

    if col2.button("載入財報", use_container_width=True, key="btn_fs") and fs_sid:
        with st.spinner("取得財報資料..."):
            df_fs = get_financial_statements(fs_sid, n_quarters=8)
            df_rev = get_monthly_revenue(fs_sid, months=13)
            info = get_taiwan_stock_info(fs_sid)

        stock_name = info.get("stock_name", fs_sid)
        st.subheader(f"{fs_sid} {stock_name} 財報摘要")

        if not df_fs.empty:
            show_cols = [c for c in ["date", "Revenue", "GrossProfit", "gross_margin", "NetIncome", "EPS"] if c in df_fs.columns]
            df_show = df_fs[show_cols].copy()
            df_show["date"] = df_show["date"].dt.strftime("%Y-%m-%d")
            col_rename = {"date": "日期", "Revenue": "營業收入", "GrossProfit": "毛利",
                          "gross_margin": "毛利率(%)", "NetIncome": "淨利", "EPS": "EPS"}
            df_show.rename(columns=col_rename, inplace=True)
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.warning("無法取得財報資料（FinMind 可能需要付費方案）")

        if not df_rev.empty:
            st.subheader("月營收趨勢")
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(
                x=df_rev["date"], y=df_rev["revenue"],
                name="月營收", marker_color="#00d4ff",
            ))
            fig_rev.update_layout(template="plotly_dark", height=260,
                                   margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_rev, use_container_width=True)

            yoy_data = df_rev.dropna(subset=["YoY"])
            if not yoy_data.empty:
                latest_yoy = float(yoy_data.iloc[-1]["YoY"])
                yoy_color = "normal" if latest_yoy >= 0 else "inverse"
                st.metric("最新月營收年增率", f"{latest_yoy:.1f}%", delta_color=yoy_color)

        if not df_fs.empty or not df_rev.empty:
            if st.button("🤖 AI 解讀財報", key="btn_ai_fs"):
                fs_ctx = ""
                if not df_fs.empty:
                    gm_col = "毛利率(%)" if "毛利率(%)" in df_show.columns else "gross_margin"
                    fs_lines = []
                    for _, r in df_fs.tail(4).iterrows():
                        eps = r.get("EPS", "N/A")
                        gm = r.get("gross_margin", "N/A")
                        fs_lines.append(
                            f"  {str(r['date'])[:10]}：EPS={eps}，毛利率={gm:.1f}%" if isinstance(gm, float) else
                            f"  {str(r['date'])[:10]}：EPS={eps}"
                        )
                    fs_ctx = "【近4季財報】\n" + "\n".join(fs_lines) + "\n"
                if not df_rev.empty:
                    yoy_lines = []
                    for _, r in df_rev.dropna(subset=["YoY"]).tail(3).iterrows():
                        yoy_lines.append(f"  {str(r['date'])[:7]}：年增率 {r['YoY']:.1f}%")
                    fs_ctx += "【近3月營收年增率】\n" + "\n".join(yoy_lines)

                answer = ask_claude(
                    "你是一位基本面分析師，用繁體中文回答，語氣簡潔專業，300字以內。",
                    f"請根據以下財報資料分析 {fs_sid} {stock_name} 的基本面狀況：\n\n{fs_ctx}",
                    max_tokens=800,
                )
                st.markdown(answer)

# ── Tab 6: 新聞情緒 ──────────────────────────────────────────────────────────
with tab6:
    col1, col2 = st.columns([3, 1])
    news_keyword = col1.text_input("輸入股票代號、公司名稱或關鍵字", value="台積電", key="news_query")
    news_days = col2.selectbox("天數", [3, 7, 14], index=1, key="news_days")

    if st.button("分析新聞情緒", use_container_width=True, key="btn_news"):
        with st.spinner("抓取新聞中..."):
            articles = get_financial_news(query=news_keyword, days=news_days, page_size=10)

        if not articles:
            st.warning("找不到相關新聞，請更換關鍵字或縮短天數")
        else:
            news_text = "\n".join(
                f"{i+1}. [{a['published']}] {a['title']} — {a.get('description', '')[:80]}"
                for i, a in enumerate(articles)
            )

            prompt = (
                f"以下是關於「{news_keyword}」的新聞（共 {len(articles)} 篇）：\n\n"
                f"{news_text}\n\n"
                "請：\n"
                "1. 對每篇新聞標記情緒：正面 / 負面 / 中性\n"
                "2. 給出整體情緒分數（-100 到 +100，正面為正）\n"
                "3. 用 100 字摘要整體新聞趨勢\n\n"
                "請用以下格式回覆：\n"
                "SCORE: [數字]\n"
                "SUMMARY: [摘要]\n"
                "ARTICLES:\n"
                "1. [正面/負面/中性] - [標題前20字]\n"
                "2. ..."
            )

            with st.spinner("AI 情緒分析中..."):
                raw = _ask_claude(
                    "你是一位財經新聞分析師，用繁體中文回答，嚴格按照指定格式輸出。",
                    prompt, max_tokens=1000,
                )

            # 解析回應
            score_val = 0
            summary_text = ""
            article_sentiments = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("SCORE:"):
                    try:
                        score_val = int(line.replace("SCORE:", "").strip())
                    except ValueError:
                        pass
                elif line.startswith("SUMMARY:"):
                    summary_text = line.replace("SUMMARY:", "").strip()
                elif line and line[0].isdigit() and "." in line[:3]:
                    article_sentiments.append(line)

            score_color = "normal" if score_val >= 0 else "inverse"
            st.metric("整體情緒分數", f"{score_val:+d}", delta_color=score_color)
            if summary_text:
                st.info(summary_text)

            st.subheader("逐篇情緒")
            sentiment_map = {"正面": "🟢", "負面": "🔴", "中性": "🟡"}
            for i, a in enumerate(articles):
                prefix = ""
                if i < len(article_sentiments):
                    sent_line = article_sentiments[i]
                    for key, emoji in sentiment_map.items():
                        if key in sent_line:
                            prefix = emoji + " "
                            break
                st.markdown(f"{prefix}**{a['title']}**  \n"
                            f"<small>{a['source']} · {a['published']}</small>",
                            unsafe_allow_html=True)
