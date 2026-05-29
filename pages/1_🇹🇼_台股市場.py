import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_taiwan_stock_info, get_taiwan_market_summary, get_realtime_quote, search_taiwan_stocks
from data.institutional import get_institutional_history, get_market_institutional_today, get_institutional_holding
from data.tw_sectors import TW_SECTORS
from data.db import wl_load, wl_add, wl_remove
from utils.charts import build_stock_chart

load_dotenv()

st.set_page_config(page_title="台股市場 | FinStation", page_icon="🇹🇼", layout="wide")
st.title("🇹🇼 台股市場")

if "watchlist_tw" not in st.session_state:
    loaded = wl_load()
    st.session_state["watchlist_tw"] = loaded if loaded is not None else ["2330", "2454", "2317", "2308", "2891"]


@st.cache_data(ttl=300)
def cached_taiex():
    return get_taiwan_market_summary()


@st.cache_data(ttl=300)
def cached_stock(stock_id: str, days: int):
    return get_taiwan_stock_price(stock_id, days=days), get_taiwan_stock_info(stock_id)


def _fetch_one_sector_stock(sid: str) -> dict:
    rt = get_realtime_quote(sid)
    if rt:
        return {
            "_id": sid, "代號": sid,
            "現價": f"{rt['price']:.2f}",
            "漲跌": f"{rt['change']:+.2f}",
            "漲跌幅": f"{rt['change_pct']:+.2f}%",
            "成交量(張)": rt["volume"],
            "即時": "✅" if rt["is_realtime"] else "—",
        }
    df = get_taiwan_stock_price(sid, days=5)
    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        change = latest["Close"] - prev["Close"]
        change_pct = change / prev["Close"] * 100
        return {
            "_id": sid, "代號": sid,
            "現價": f"{latest['Close']:.2f}",
            "漲跌": f"{change:+.2f}",
            "漲跌幅": f"{change_pct:+.2f}%",
            "成交量(張)": int(latest.get("Volume", 0)) if "Volume" in latest.index else 0,
            "即時": "—",
        }
    return {"_id": sid, "代號": sid, "現價": "—", "漲跌": "—", "漲跌幅": "—", "成交量(張)": 0, "即時": "—"}


@st.cache_data(ttl=60)
def cached_sector(stock_ids: tuple) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(_fetch_one_sector_stock, stock_ids))
    return results


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
        template="plotly_dark", height=240,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="", yaxis_title="點數",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("大盤數據暫時無法取得")

st.divider()

# 三個 Tab
tab_stock, tab_sector, tab_inst = st.tabs(["📈 個股行情", "🏭 族群", "🏦 法人動向"])

# ── Tab 1: 個股 ──────────────────────────────────────────
with tab_stock:
    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("輸入股票代號或中文名稱（例如：2330、台積電）", value="2330")
    with col2:
        period = st.selectbox("時間區間", ["30天", "90天", "180天", "365天"], index=2)

    period_map = {"30天": 30, "90天": 90, "180天": 180, "365天": 365}
    days = period_map[period]

    # 解析輸入：純數字直接當代號，中文/英文名稱則搜尋
    stock_id = keyword.strip()
    if stock_id and not stock_id.isdigit():
        matches = search_taiwan_stocks(stock_id)
        if matches:
            options = [f"{s['stock_id']} {s['stock_name']}" for s in matches[:10]]
            chosen = st.selectbox("搜尋結果，請選擇：", options, key="tw_search_pick")
            stock_id = chosen.split(" ")[0]
        else:
            st.warning(f"找不到「{stock_id}」，請確認名稱或代號")
            stock_id = ""

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
            rt = get_realtime_quote(stock_id.strip())
            if rt:
                price = rt["price"]
                change = rt["change"]
                change_pct = rt["change_pct"]
                high = rt["high"] or df.iloc[-1].get("High", 0)
                low = rt["low"] or df.iloc[-1].get("Low", 0)
                price_label = "即時價格" if rt["is_realtime"] else "收盤價"
            else:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                price = latest["Close"]
                change = price - prev["Close"]
                change_pct = change / prev["Close"] * 100
                high = latest.get("High", 0)
                low = latest.get("Low", 0)
                price_label = "收盤價"

            color_arrow = "🔺" if change >= 0 else "🔻"
            mc1, mc2, mc3, mc4, mc5 = st.columns([2, 2, 1, 1, 1])
            mc1.metric("股票名稱", info.get("stock_name", stock_id))
            mc2.metric(price_label, f"{price:.2f}",
                       f"{color_arrow} {change:+.2f} ({change_pct:+.2f}%)")
            mc3.metric("最高", f"{high:.2f}" if high else "—")
            mc4.metric("最低", f"{low:.2f}" if low else "—")

            wl = st.session_state["watchlist_tw"]
            in_wl = stock_id.strip() in wl
            btn_label = "⭐ 移除自選" if in_wl else "☆ 加入自選"
            if mc5.button(btn_label):
                if in_wl:
                    wl.remove(stock_id.strip())
                    wl_remove(stock_id.strip())
                else:
                    try:
                        wl_add(stock_id.strip())
                        wl.append(stock_id.strip())
                    except RuntimeError as e:
                        st.error(str(e))
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

# ── Tab 2: 族群 ──────────────────────────────────────────
with tab_sector:
    sector_names = list(TW_SECTORS.keys())
    selected = st.selectbox("選擇族群", sector_names)

    stocks_in_sector = TW_SECTORS[selected]
    stock_ids = tuple(s["id"] for s in stocks_in_sector)
    name_map = {s["id"]: s["name"] for s in stocks_in_sector}

    with st.spinner(f"載入「{selected}」族群數據..."):
        rows = cached_sector(stock_ids)

    # 加上名稱欄（龍頭加 👑）
    leader_ids = {s["id"] for s in stocks_in_sector if s.get("leader")}
    for row in rows:
        name = name_map.get(row["_id"], row["代號"])
        row["名稱"] = f"👑 {name}" if row["_id"] in leader_ids else name

    df_sector = pd.DataFrame(rows)[["代號", "名稱", "現價", "漲跌", "漲跌幅", "成交量(張)", "即時"]]

    def color_change(val):
        if isinstance(val, str):
            if val.startswith("+"):
                return "color: #ff4b4b"
            if val.startswith("-"):
                return "color: #00cc44"
        elif isinstance(val, (int, float)):
            if val > 0:
                return "color: #ff4b4b"
            if val < 0:
                return "color: #00cc44"
        return ""

    styled = df_sector.style.map(color_change, subset=["漲跌", "漲跌幅"])

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # 點擊查看個股 K 線
    st.subheader("查看個股 K 線")
    sel_stock = st.selectbox(
        "選擇股票",
        [f"{s['id']} {s['name']}" for s in stocks_in_sector],
        key="sector_stock_sel",
    )
    sel_id = sel_stock.split(" ")[0]

    with st.spinner(f"載入 {sel_id} 數據..."):
        df_k, _ = cached_stock(sel_id, 180)

    if not df_k.empty:
        fig_k = build_stock_chart(df_k, sel_id, show_ma=True, show_volume=True)
        st.plotly_chart(fig_k, use_container_width=True)
    else:
        st.warning("無法取得該股票數據")

# ── Tab 3: 法人動向 ──────────────────────────────────────────
with tab_inst:
    inst_mode = st.radio("查看模式", ["個股法人買賣超", "今日全市場法人排行"], horizontal=True)

    if inst_mode == "個股法人買賣超":
        col_a, col_b = st.columns([2, 1])
        with col_a:
            inst_kw = st.text_input("輸入股票代號", value="2330", key="inst_stock")
        with col_b:
            inst_days = st.selectbox("天數", [30, 60, 90], index=1, key="inst_days")

        inst_id = inst_kw.strip()
        if inst_id:
            @st.cache_data(ttl=300)
            def cached_inst(sid, d):
                return get_institutional_history(sid, d)

            with st.spinner(f"載入 {inst_id} 法人數據..."):
                df_inst = cached_inst(inst_id, inst_days)

            if not df_inst.empty:
                # 外資持股比例
                holding = get_institutional_holding(inst_id)
                if holding:
                    st.metric("外資持股比例", f"{holding.get('foreign_holding_pct', 0):.1f}%",
                              help=f"資料日期：{holding.get('date', '')}")

                # 近期買賣超柱狀圖
                import plotly.graph_objects as go
                fig_inst = go.Figure()
                df_plot = df_inst.head(30).sort_values("date")
                colors_total = ["#ff4b4b" if v >= 0 else "#00cc44" for v in df_plot["合計"]]
                fig_inst.add_trace(go.Bar(x=df_plot["date"], y=df_plot["外資"],
                                          name="外資", marker_color="#00d4ff", opacity=0.8))
                fig_inst.add_trace(go.Bar(x=df_plot["date"], y=df_plot["投信"],
                                          name="投信", marker_color="#ffa500", opacity=0.8))
                fig_inst.add_trace(go.Bar(x=df_plot["date"], y=df_plot["自營商"],
                                          name="自營商", marker_color="#9b59b6", opacity=0.8))
                fig_inst.update_layout(
                    template="plotly_dark", barmode="relative",
                    title=f"{inst_id} 三大法人買賣超（張）",
                    height=350, margin=dict(l=0, r=0, t=40, b=0),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig_inst, use_container_width=True)

                # 累計買賣超折線
                df_plot["累計"] = df_plot["合計"].cumsum()
                fig_cum = go.Figure()
                fig_cum.add_trace(go.Scatter(
                    x=df_plot["date"], y=df_plot["累計"],
                    mode="lines+markers", name="累計買賣超",
                    line=dict(color="#00d4ff", width=2),
                    fill="tozeroy", fillcolor="rgba(0,212,255,0.08)",
                ))
                fig_cum.update_layout(
                    template="plotly_dark", title="累計買賣超（張）",
                    height=220, margin=dict(l=0, r=0, t=40, b=0),
                )
                st.plotly_chart(fig_cum, use_container_width=True)

                # 原始數據
                with st.expander("查看原始數據"):
                    df_show = df_inst.copy()
                    df_show["date"] = df_show["date"].dt.strftime("%Y-%m-%d")
                    st.dataframe(df_show, use_container_width=True, hide_index=True)
            else:
                st.warning(f"查無 {inst_id} 的法人資料，請確認代號是否正確")

    else:  # 今日全市場排行
        @st.cache_data(ttl=600)
        def cached_market_inst():
            return get_market_institutional_today()

        with st.spinner("載入今日法人買賣超排行..."):
            df_mkt = cached_market_inst()

        if not df_mkt.empty:
            view = st.radio("排序", ["三大法人買超前20", "三大法人賣超前20", "外資買超前20"], horizontal=True)

            if view == "三大法人買超前20":
                df_view = df_mkt.nlargest(20, "三大法人合計")
            elif view == "三大法人賣超前20":
                df_view = df_mkt.nsmallest(20, "三大法人合計")
            else:
                df_view = df_mkt.nlargest(20, "外資買賣超")

            def color_num(val):
                if isinstance(val, (int, float)):
                    return "color: #ff4b4b" if val > 0 else ("color: #00cc44" if val < 0 else "")
                return ""

            styled_mkt = df_view.style.map(
                color_num, subset=["外資買賣超", "投信買賣超", "自營商買賣超", "三大法人合計"]
            )
            st.dataframe(styled_mkt, use_container_width=True, hide_index=True)
        else:
            st.info("今日法人資料尚未更新（通常盤後 18:00 後可查詢）")
