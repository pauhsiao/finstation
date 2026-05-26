import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_taiwan_stock_info, get_realtime_quote
from data.db import wl_load, wl_add, wl_remove
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="自選股 | FinStation", page_icon="⭐", layout="wide")
st.title("⭐ 自選股")

# 從 Supabase 載入，fallback 到 session_state 預設
if "watchlist_tw" not in st.session_state:
    loaded = wl_load()
    st.session_state["watchlist_tw"] = loaded if loaded else ["2330", "2454", "2317", "2308", "2891"]

wl: list = st.session_state["watchlist_tw"]

# 新增股票
with st.form("add_form", clear_on_submit=True):
    c1, c2 = st.columns([4, 1])
    new_id = c1.text_input("新增股票代號", placeholder="例如：2330、6472")
    if c2.form_submit_button("新增", use_container_width=True) and new_id.strip():
        sid = new_id.strip()
        if sid not in wl:
            wl.append(sid)
            wl_add(sid)
            st.success(f"已加入 {sid}")
        else:
            st.info(f"{sid} 已在自選股中")

st.divider()

if not wl:
    st.info("自選股清單為空，請在上方輸入股票代號加入")
    st.stop()


@st.cache_data(ttl=30)
def fetch_watchlist(stock_ids: tuple) -> list[dict]:
    rows = []
    for sid in stock_ids:
        info = get_taiwan_stock_info(sid)
        rt = get_realtime_quote(sid)
        if rt:
            rows.append({
                "代號": sid,
                "名稱": info.get("stock_name", sid),
                "現價": f"{rt['price']:.2f}",
                "漲跌": f"{rt['change']:+.2f}",
                "漲跌幅": f"{rt['change_pct']:+.2f}%",
                "成交量(張)": f"{rt['volume']:,}",
                "即時": "✅" if rt["is_realtime"] else "—",
            })
        else:
            df = get_taiwan_stock_price(sid, days=5)
            if not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                change = latest["Close"] - prev["Close"]
                change_pct = change / prev["Close"] * 100
                rows.append({
                    "代號": sid,
                    "名稱": info.get("stock_name", sid),
                    "現價": f"{latest['Close']:.2f}",
                    "漲跌": f"{change:+.2f}",
                    "漲跌幅": f"{change_pct:+.2f}%",
                    "成交量(張)": f"{int(latest.get('Volume', 0)):,}" if "Volume" in latest else "—",
                    "即時": "—",
                })
            else:
                rows.append({
                    "代號": sid, "名稱": "—", "現價": "—",
                    "漲跌": "—", "漲跌幅": "—", "成交量(張)": "—", "即時": "—",
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


df_display = df_display[["代號", "名稱", "現價", "漲跌", "漲跌幅", "成交量(張)", "即時"]]
styled = df_display.style.map(color_pct, subset=["漲跌", "漲跌幅"])
st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# 移除按鈕
st.subheader("移除股票")
cols = st.columns(min(len(wl), 8))
for i, sid in enumerate(list(wl)):
    if cols[i % len(cols)].button(f"✕ {sid}", key=f"rm_{sid}"):
        wl.remove(sid)
        wl_remove(sid)
        st.cache_data.clear()
        st.rerun()

st.caption("✅ 自選股已同步至雲端（Supabase），重新整理後仍會保留。")
