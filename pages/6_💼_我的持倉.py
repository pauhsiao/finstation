import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.db import holdings_load, holdings_add, holdings_delete
from data.taiwan_stocks import get_realtime_quote, get_taiwan_stock_info
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="我的持倉 | FinStation", page_icon="💼", layout="wide")
st.title("💼 我的持倉")

# ── 新增持倉 ──────────────────────────────────────────────────────────────
with st.expander("➕ 新增持倉", expanded=False):
    with st.form("add_holding"):
        c1, c2, c3, c4 = st.columns(4)
        sid = c1.text_input("股票代號", placeholder="例如：2330")
        shares = c2.number_input("持股數量（股）", min_value=1, value=1000)
        buy_price = c3.number_input("買入均價", min_value=0.01, value=100.0, step=0.1)
        buy_date = c4.date_input("買入日期")
        submitted = st.form_submit_button("新增", use_container_width=True)
        if submitted and sid.strip():
            info = get_taiwan_stock_info(sid.strip())
            holdings_add(
                stock_id=sid.strip(),
                stock_name=info.get("stock_name", sid.strip()),
                shares=shares,
                buy_price=float(buy_price),
                buy_date=str(buy_date),
            )
            st.success(f"已新增 {sid.strip()}")
            st.rerun()

st.divider()

# ── 載入持倉 ──────────────────────────────────────────────────────────────
holdings = holdings_load()

if not holdings:
    st.info("尚無持倉紀錄，請在上方新增")
    st.stop()

# ── 計算損益 ──────────────────────────────────────────────────────────────
rows = []
for h in holdings:
    sid = h["stock_id"]
    shares = h["shares"]
    buy_price = h["buy_price"]
    cost = shares * buy_price

    rt = get_realtime_quote(sid)
    cur_price = rt["price"] if rt else buy_price
    cur_value = shares * cur_price
    pnl = cur_value - cost
    pnl_pct = pnl / cost * 100

    rows.append({
        "_id": h["id"],
        "代號": sid,
        "名稱": h.get("stock_name", sid),
        "持股(股)": shares,
        "買入均價": f"{buy_price:.2f}",
        "現價": f"{cur_price:.2f}",
        "成本": cost,
        "現值": cur_value,
        "損益": pnl,
        "損益%": pnl_pct,
        "買入日期": h.get("buy_date", "—"),
    })

df = pd.DataFrame(rows)

# ── 總覽 ──────────────────────────────────────────────────────────────────
total_cost = df["成本"].sum()
total_value = df["現值"].sum()
total_pnl = total_value - total_cost
total_pnl_pct = total_pnl / total_cost * 100 if total_cost else 0

arrow = "🔺" if total_pnl >= 0 else "🔻"
ov1, ov2, ov3 = st.columns(3)
ov1.metric("總成本", f"${total_cost:,.0f}")
ov2.metric("總現值", f"${total_value:,.0f}")
ov3.metric("未實現損益", f"${total_pnl:,.0f}", f"{arrow} {total_pnl_pct:+.2f}%")

st.divider()

# ── 持倉明細表 ──────────────────────────────────────────────────────────────
st.subheader("持倉明細")

def color_pnl(val):
    if isinstance(val, (int, float)):
        if val > 0: return "color: #ff4b4b"
        if val < 0: return "color: #00cc44"
    return ""

display_df = df[["代號", "名稱", "持股(股)", "買入均價", "現價", "損益", "損益%", "買入日期"]].copy()
display_df["損益"] = display_df["損益"].apply(lambda x: f"{x:+,.0f}")
display_df["損益%"] = display_df["損益%"].apply(lambda x: f"{x:+.2f}%")
styled = display_df.style.map(lambda v: "color: #ff4b4b" if isinstance(v, str) and v.startswith("+") else ("color: #00cc44" if isinstance(v, str) and v.startswith("-") else ""), subset=["損益", "損益%"])
st.dataframe(styled, use_container_width=True, hide_index=True)

# ── 圖表 ──────────────────────────────────────────────────────────────────
col_bar, col_pie = st.columns(2)

with col_bar:
    st.subheader("個股損益")
    colors = ["#ff4b4b" if v >= 0 else "#00cc44" for v in df["損益"]]
    fig_bar = go.Figure(go.Bar(
        x=df["代號"] + " " + df["名稱"],
        y=df["損益"],
        marker_color=colors,
        text=df["損益"].apply(lambda x: f"{x:+,.0f}"),
        textposition="outside",
    ))
    fig_bar.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="損益（元）")
    st.plotly_chart(fig_bar, use_container_width=True)

with col_pie:
    st.subheader("持倉比重")
    fig_pie = go.Figure(go.Pie(
        labels=df["代號"] + " " + df["名稱"],
        values=df["現值"],
        hole=0.4,
        textinfo="label+percent",
    ))
    fig_pie.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

# ── 刪除 ──────────────────────────────────────────────────────────────────
st.divider()
st.subheader("移除持倉")
del_cols = st.columns(min(len(holdings), 6))
for i, h in enumerate(holdings):
    label = f"✕ {h['stock_id']} {h.get('stock_name','')}"
    if del_cols[i % len(del_cols)].button(label, key=f"del_{h['id']}"):
        holdings_delete(h["id"])
        st.rerun()
