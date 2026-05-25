import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_taiwan_stock_info

st.set_page_config(page_title="自選股 | FinStation", page_icon="⭐", layout="wide")
st.title("⭐ 自選股")

if "watchlist_tw" not in st.session_state:
    st.session_state["watchlist_tw"] = ["2330", "2454", "2317", "2308", "2891"]

wl: list = st.session_state["watchlist_tw"]

# 新增股票
with st.form("add_form", clear_on_submit=True):
    c1, c2 = st.columns([4, 1])
    new_id = c1.text_input("新增股票代號", placeholder="例如：2330、6472")
    if c2.form_submit_button("新增", use_container_width=True) and new_id.strip():
        sid = new_id.strip()
        if sid not in wl:
            wl.append(sid)
            st.success(f"已加入 {sid}")
        else:
            st.info(f"{sid} 已在自選股中")

st.divider()

if not wl:
    st.info("自選股清單為空，請在上方輸入股票代號加入")
    st.stop()


@st.cache_data(ttl=300)
def fetch_watchlist(stock_ids: tuple) -> list[dict]:
    rows = []
    for sid in stock_ids:
        df = get_taiwan_stock_price(sid, days=5)
        info = get_taiwan_stock_info(sid)
        if not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            change = latest["Close"] - prev["Close"]
            change_pct = change / prev["Close"] * 100
            rows.append({
                "代號": sid,
                "名稱": info.get("stock_name", sid),
                "收盤價": f"{latest['Close']:.2f}",
                "漲跌": f"{change:+.2f}",
                "漲跌幅": f"{change_pct:+.2f}%",
                "成交量(張)": f"{int(latest.get('Volume', 0)):,}" if "Volume" in latest else "—",
                "日期": str(latest["date"])[:10] if "date" in latest.index else "—",
            })
        else:
            rows.append({
                "代號": sid, "名稱": "—", "收盤價": "—",
                "漲跌": "—", "漲跌幅": "—", "成交量(張)": "—", "日期": "—",
            })
    return rows


st.subheader(f"共 {len(wl)} 支")

with st.spinner("載入數據..."):
    data = fetch_watchlist(tuple(wl))

df_display = pd.DataFrame(data)


def color_pct(val: str):
    if isinstance(val, str):
        if val.startswith("+"):
            return "color: #ff4b4b"
        if val.startswith("-"):
            return "color: #00cc44"
    return ""


styled = df_display.style.map(color_pct, subset=["漲跌", "漲跌幅"])
st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# 移除按鈕
st.subheader("移除股票")
cols = st.columns(min(len(wl), 8))
for i, sid in enumerate(list(wl)):
    if cols[i % len(cols)].button(f"✕ {sid}", key=f"rm_{sid}"):
        wl.remove(sid)
        st.cache_data.clear()
        st.rerun()

st.caption("⚠️ 自選股儲存於本次瀏覽 Session，重新整理後會重置為預設清單。Phase 3 將加入雲端持久化儲存。")
