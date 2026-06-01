import streamlit as st
import pandas as pd
import threading
import sys, os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_realtime_quote, get_taiwan_stock_info
from data.tw_sectors import TW_SECTORS
from data.scoring import quick_tech_score
from data.db import wl_load

st.set_page_config(page_title="股票篩選 | FinStation", page_icon="🏆", layout="wide")
st.title("🏆 股票篩選排行")
st.caption("依技術面評分（45分制）對族群精選股票排行，每 30 分鐘自動更新")

# ── 篩選設定 ──────────────────────────────────────────────────────────────────
all_sector_names = list(TW_SECTORS.keys())

with st.expander("⚙️ 篩選設定", expanded=True):
    scope_col, sector_col = st.columns([1, 3])
    with scope_col:
        scope = st.radio("篩選範圍", ["族群精選", "自選股"], key="screen_scope")
    with sector_col:
        if scope == "族群精選":
            if st.checkbox("全選族群", value=True, key="screen_all"):
                selected_sectors = all_sector_names
            else:
                selected_sectors = st.multiselect(
                    "選擇族群", all_sector_names, default=all_sector_names[:5], key="screen_sectors"
                )
        else:
            selected_sectors = []

    top_n = st.select_slider("顯示前 N 名", options=[20, 50, 100, 999], value=50, key="screen_topn")
    run_btn = st.button("🔍 開始篩選", use_container_width=True, type="primary")

# ── 取得股票清單 ───────────────────────────────────────────────────────────────
def get_target_stocks(scope: str, selected_sectors: list) -> list[dict]:
    if scope == "自選股":
        wl = wl_load() or st.session_state.get("watchlist_tw", [])
        stocks = []
        for sid in wl:
            info = get_taiwan_stock_info(sid)
            stocks.append({"id": sid, "name": info.get("stock_name", sid)})
        return stocks

    seen = set()
    stocks = []
    for sector in selected_sectors:
        for s in TW_SECTORS.get(sector, []):
            if s["id"] not in seen:
                seen.add(s["id"])
                stocks.append({"id": s["id"], "name": s["name"], "sector": sector})
    return stocks


@st.cache_data(ttl=1800, show_spinner=False)
def run_screener(stock_ids: tuple, stock_names: dict) -> pd.DataFrame:
    results = []
    lock = threading.Lock()

    def score_one(sid):
        try:
            df = get_taiwan_stock_price(sid, days=120)
            ts = quick_tech_score(df)
            rt = get_realtime_quote(sid)
            change_pct = rt["change_pct"] if rt else None
            price = rt["price"] if rt else (float(df.iloc[-1]["Close"]) if not df.empty else None)
            row = {
                "代號": sid,
                "名稱": stock_names.get(sid, sid),
                "技術分": ts["total"],
                "均線": ts["ma"],
                "MACD": ts["macd"],
                "突破": ts["breakout"],
                "布林": ts["bb"],
                "量能": ts["vol"],
                "現價": price,
                "漲跌%": change_pct,
            }
            with lock:
                results.append(row)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=5) as ex:
        ex.map(score_one, stock_ids)

    if not results:
        return pd.DataFrame()
    df_result = pd.DataFrame(results).sort_values("技術分", ascending=False).reset_index(drop=True)
    df_result.index += 1
    return df_result


# ── 執行篩選 ───────────────────────────────────────────────────────────────────
if run_btn or "screener_result" in st.session_state:
    targets = get_target_stocks(scope, selected_sectors)
    if not targets:
        st.warning("找不到股票，請調整篩選條件")
    else:
        stock_ids = tuple(s["id"] for s in targets)
        stock_names = {s["id"]: s["name"] for s in targets}
        sectors_map = {s["id"]: s.get("sector", "") for s in targets}

        if run_btn:
            with st.spinner(f"正在評分 {len(stock_ids)} 支股票，約需 1-3 分鐘，請稍候..."):
                run_screener.clear()
                df_screen = run_screener(stock_ids, stock_names)
            st.session_state["screener_result"] = df_screen
            st.session_state["screener_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            st.session_state["screener_count"] = len(stock_ids)
        elif "screener_result" in st.session_state:
            df_screen = st.session_state["screener_result"]
        else:
            df_screen = pd.DataFrame()

        if not df_screen.empty:
            ts_str = st.session_state.get("screener_ts", "—")
            cnt = st.session_state.get("screener_count", len(stock_ids))
            st.caption(f"📅 資料更新：{ts_str}｜已評分 {len(df_screen)}/{cnt} 支股票")

            # ── 結果表格 ──────────────────────────────────────────────────────
            df_show = df_screen.head(top_n if top_n < 999 else len(df_screen)).copy()

            # 格式化
            df_show["現價"] = df_show["現價"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
            df_show["漲跌%"] = df_show["漲跌%"].apply(
                lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
            )
            df_show["族群"] = df_show["代號"].map(sectors_map).fillna("")

            # 技術分 bar 視覺化
            def score_bar(val):
                pct = val / 45 * 100
                color = "#00cc44" if val >= 30 else "#ffa500" if val >= 20 else "#888"
                return f"<div style='background:linear-gradient(90deg,{color} {pct:.0f}%,#333 {pct:.0f}%);border-radius:4px;padding:2px 6px;color:#fff;font-weight:bold'>{val}/45</div>"

            st.write(
                df_show[["代號", "名稱", "族群", "技術分", "均線", "MACD", "突破", "布林", "量能", "現價", "漲跌%"]]
                .to_html(escape=False, index=True),
                unsafe_allow_html=True,
            )

            st.divider()

            # ── 快速導覽 ──────────────────────────────────────────────────────
            st.subheader("🔍 查看個股完整評分")
            top10 = df_show.head(10)
            cols = st.columns(5)
            for i, (_, row) in enumerate(top10.iterrows()):
                col = cols[i % 5]
                col.link_button(
                    f"{row['代號']} {row['名稱']}  {row['技術分']}分",
                    f"/台股市場?stock={row['代號']}",
                    use_container_width=True,
                )

            # ── 技術分分佈 ────────────────────────────────────────────────────
            import plotly.graph_objects as go
            st.subheader("📊 評分分佈")
            fig = go.Figure(go.Histogram(
                x=df_screen["技術分"], nbinsx=15,
                marker_color="#00d4ff", opacity=0.8,
            ))
            fig.update_layout(
                template="plotly_dark", height=220,
                xaxis_title="技術評分（/45）", yaxis_title="股票數",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
