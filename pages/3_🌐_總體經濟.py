import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.macro import get_fred_series, MACRO_SERIES

load_dotenv()

st.set_page_config(page_title="總體經濟 | FinStation", page_icon="🌐", layout="wide")
st.title("🌐 總體經濟數據")

import os
has_fred = bool(os.getenv("FRED_API_KEY"))
if not has_fred:
    st.warning("⚠️ 尚未設定 FRED_API_KEY，請複製 .env.example 為 .env 並填入免費 API Key（申請網址：https://fred.stlouisfed.org/docs/api/api_key.html）")
    st.stop()

series_list = list(MACRO_SERIES.items())
selected = st.multiselect(
    "選擇要顯示的指標",
    options=[label for _, label in series_list],
    default=["聯邦基金利率 (%)", "美國 CPI（消費者物價）", "10 年期公債殖利率"],
)

years = st.slider("顯示年數", min_value=1, max_value=10, value=3)

if selected:
    sid_map = {label: sid for sid, label in series_list}
    for label in selected:
        sid = sid_map[label]
        with st.spinner(f"載入 {label}..."):
            df = get_fred_series(sid, years=years)

        if df.empty:
            st.warning(f"{label} 數據取得失敗")
            continue

        latest_val = df["value"].iloc[-1]
        prev_val = df["value"].iloc[-2] if len(df) > 1 else latest_val
        change = latest_val - prev_val

        col1, col2 = st.columns([4, 1])
        with col1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["value"],
                mode="lines", name=label,
                line=dict(width=2),
                fill="tozeroy", fillcolor="rgba(0,212,255,0.08)"
            ))
            fig.update_layout(
                title=label,
                template="plotly_dark",
                height=250,
                margin=dict(l=0, r=0, t=30, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.metric("最新值", f"{latest_val:.2f}", f"{change:+.2f}")
            st.caption(f"更新至 {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
