import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.taiwan_stocks import get_taiwan_stock_price, get_taiwan_stock_info, get_realtime_quote, search_taiwan_stocks
from data.backtest import (run_backtest, ma_cross_signals, rsi_signals, bb_signals,
                            optimize_ma, calc_var)
from data.db import holdings_load
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="回測分析 | FinStation", page_icon="📈", layout="wide")
st.title("📈 量化回測 & 風險分析")


def stock_search_widget(label: str, default: str, key: str) -> str:
    """輸入框支援代號或中文名稱，回傳最終 stock_id"""
    keyword = st.text_input(label, value=default, key=key,
                            placeholder="代號（2330）或中文名稱（台積電）")
    sid = keyword.strip()
    if sid and not sid.isdigit():
        matches = search_taiwan_stocks(sid)
        if matches:
            options = [f"{s['stock_id']} {s['stock_name']}" for s in matches[:10]]
            chosen = st.selectbox("搜尋結果，請選擇：", options, key=f"{key}_pick")
            sid = chosen.split(" ")[0]
        else:
            st.warning(f"找不到「{sid}」，請確認名稱或代號")
            sid = ""
    return sid


def fetch_price(sid: str, days: int) -> pd.DataFrame:
    """取得股價，失敗時顯示明確錯誤"""
    if not sid:
        return pd.DataFrame()
    for attempt in range(2):
        df = get_taiwan_stock_price(sid, days=days)
        if not df.empty:
            return df
    st.error(f"❌ 無法取得 {sid} 的數據，可能原因：FinMind API 暫時無回應、代號錯誤，或超出免費額度。請稍後再試。")
    return pd.DataFrame()


tab1, tab2, tab3, tab4 = st.tabs(["🔄 策略回測", "🎯 買賣訊號", "⚠️ 風險分析", "🔧 參數最佳化"])

# ── Tab 1: 策略回測 ─────────────────────────────────────────────────────
with tab1:
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        sid = stock_search_widget("股票代號或中文名稱", "2330", "bt_sid")
    strategy = c2.selectbox("策略", ["均線交叉 (MA Cross)", "RSI 超賣/超買", "布林通道突破"])
    period_opt = c3.selectbox("回測區間", ["180天", "365天", "730天"], index=1)
    days = {"180天": 180, "365天": 365, "730天": 730}[period_opt]

    with st.expander("策略參數", expanded=True):
        p1, p2 = st.columns(2)
        if "均線" in strategy:
            fast = p1.slider("快線 (天)", 3, 20, 5)
            slow = p2.slider("慢線 (天)", 10, 60, 20)
        elif "RSI" in strategy:
            rsi_period = p1.slider("RSI 週期", 7, 21, 14)
            oversold = p1.slider("超賣線", 20, 40, 30)
            overbought = p2.slider("超買線", 60, 80, 70)
        else:
            bb_period = p1.slider("布林週期", 10, 30, 20)
            bb_std = p2.slider("標準差倍數", 1.0, 3.0, 2.0, step=0.1)

    if st.button("開始回測", use_container_width=True):
        with st.spinner("回測中..."):
            df = fetch_price(sid, days)
            info = get_taiwan_stock_info(sid) if sid else {}

        if not df.empty:
            if "均線" in strategy:
                sigs = ma_cross_signals(df, fast, slow)
            elif "RSI" in strategy:
                sigs = rsi_signals(df, rsi_period, oversold, overbought)
            else:
                sigs = bb_signals(df, bb_period, bb_std)

            result = run_backtest(df, sigs)
            name = info.get("stock_name", sid)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("策略報酬", f"{result['total_return']:+.1f}%",
                      f"買持 {result['buy_hold_return']:+.1f}%")
            m2.metric("最大回撤", f"{result['max_drawdown']:.1f}%")
            m3.metric("夏普比率", f"{result['sharpe']:.2f}")
            m4.metric("勝率", f"{result['win_rate']:.0f}%")
            m5.metric("交易次數", f"{result['total_trades']} 次")

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["date"], y=result["equity"],
                mode="lines", name="策略", line=dict(color="#00d4ff", width=2)
            ))
            initial = 100000
            bh = [initial * (p / df.iloc[0]["Close"]) for p in df["Close"]]
            fig.add_trace(go.Scatter(
                x=df["date"], y=bh,
                mode="lines", name="買持", line=dict(color="#888", width=1, dash="dash")
            ))
            for t in result["trades"]:
                fig.add_vline(x=str(t["date"])[:10], line_dash="dot",
                              line_color="#ff4b4b" if t["type"] == "buy" else "#00cc44",
                              line_width=1)
            fig.update_layout(template="plotly_dark", height=300,
                              margin=dict(l=0, r=0, t=10, b=0), yaxis_title="資金（元）")
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: 買賣訊號 ─────────────────────────────────────────────────────
with tab2:
    c1, c2 = st.columns([2, 2])
    with c1:
        sid2 = stock_search_widget("股票代號或中文名稱", "2330", "sig_sid")
    sig_strategy = c2.selectbox("策略", ["均線交叉", "RSI", "布林通道"], key="sig_strat")

    if sig_strategy == "RSI":
        sp1, sp2, sp3 = st.columns(3)
        sig_rsi_period = sp1.slider("RSI 週期", 7, 21, 14, key="sig_rsi_p")
        sig_oversold = sp2.slider("超賣線", 20, 40, 30, key="sig_os")
        sig_overbought = sp3.slider("超買線", 60, 80, 70, key="sig_ob")
    elif sig_strategy == "均線交叉":
        sp1, sp2 = st.columns(2)
        sig_fast = sp1.slider("快線 (天)", 3, 20, 5, key="sig_fast")
        sig_slow = sp2.slider("慢線 (天)", 10, 60, 20, key="sig_slow")

    if st.button("顯示訊號", use_container_width=True):
        with st.spinner("載入中..."):
            df2 = fetch_price(sid2, 180)
        if not df2.empty:
            if sig_strategy == "均線交叉":
                sigs2 = ma_cross_signals(df2, sig_fast, sig_slow)
            elif sig_strategy == "RSI":
                sigs2 = rsi_signals(df2, sig_rsi_period, sig_oversold, sig_overbought)
            else:
                sigs2 = bb_signals(df2)

            buy_pts = df2[sigs2 == 1]
            sell_pts = df2[sigs2 == -1]

            fig2 = go.Figure()
            fig2.add_trace(go.Candlestick(
                x=df2["date"], open=df2["Open"], high=df2["High"],
                low=df2["Low"], close=df2["Close"], name="K線",
                increasing_line_color="#ff4b4b", decreasing_line_color="#00cc44"
            ))
            fig2.add_trace(go.Scatter(
                x=buy_pts["date"], y=buy_pts["Low"] * 0.98,
                mode="markers", marker=dict(symbol="triangle-up", size=12, color="#ff4b4b"),
                name="買入訊號"
            ))
            fig2.add_trace(go.Scatter(
                x=sell_pts["date"], y=sell_pts["High"] * 1.02,
                mode="markers", marker=dict(symbol="triangle-down", size=12, color="#00cc44"),
                name="賣出訊號"
            ))
            fig2.update_layout(template="plotly_dark", height=400,
                               margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig2, use_container_width=True)
            st.caption(f"🔺 買入訊號 {len(buy_pts)} 次　🔻 賣出訊號 {len(sell_pts)} 次")

# ── Tab 3: 風險分析 ─────────────────────────────────────────────────────
with tab3:
    st.subheader("持倉風險分析")
    holdings = holdings_load()

    if not holdings:
        st.info("請先到「我的持倉」新增持倉")
    else:
        stock_ids = [h["stock_id"] for h in holdings]
        price_data = {}

        with st.spinner("載入持倉數據..."):
            for sid_h in stock_ids:
                df_h = get_taiwan_stock_price(sid_h, days=180)
                if not df_h.empty:
                    price_data[sid_h] = df_h.set_index("date")["Close"]

        if not price_data:
            st.error("❌ 無法取得持倉股票數據，請稍後再試")
        elif len(price_data) < 2:
            st.info("需要至少 2 支持倉才能計算相關性")
        else:
            prices_df = pd.DataFrame(price_data).dropna()
            returns_df = prices_df.pct_change().dropna()

            corr = returns_df.corr()
            names = [f"{s} {next((h['stock_name'] for h in holdings if h['stock_id']==s), s)}" for s in corr.columns]
            fig3 = go.Figure(go.Heatmap(
                z=corr.values, x=names, y=names,
                colorscale="RdBu_r", zmid=0,
                text=corr.round(2).values, texttemplate="%{text}",
            ))
            fig3.update_layout(template="plotly_dark", height=400,
                               title="持倉相關性（越紅越正相關，風險越集中）",
                               margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig3, use_container_width=True)

            st.subheader("個股 VaR（95% 信心水準，單日）")
            var_rows = []
            for sid_h, ret in returns_df.items():
                h = next((x for x in holdings if x["stock_id"] == sid_h), {})
                shares = h.get("shares", 0)
                rt = get_realtime_quote(sid_h)
                cur_price = rt["price"] if rt else prices_df[sid_h].iloc[-1]
                position_value = shares * cur_price
                var_pct = calc_var(ret) * 100
                var_amt = position_value * abs(calc_var(ret))
                var_rows.append({
                    "代號": sid_h,
                    "名稱": h.get("stock_name", sid_h),
                    "部位市值": f"${position_value:,.0f}",
                    "VaR%": f"{var_pct:.2f}%",
                    "VaR金額": f"${var_amt:,.0f}",
                })
            st.dataframe(pd.DataFrame(var_rows), use_container_width=True, hide_index=True)
            st.caption("VaR：在95%的情況下，單日最大可能虧損金額")

# ── Tab 4: 參數最佳化 ─────────────────────────────────────────────────────
with tab4:
    c1, c2 = st.columns([2, 2])
    with c1:
        sid4 = stock_search_widget("股票代號或中文名稱", "2330", "opt_sid")
    days4 = {"365天": 365, "730天": 730}[c2.selectbox("回測區間", ["365天", "730天"])]

    if st.button("尋找最佳 MA 參數", use_container_width=True):
        with st.spinner("最佳化中（約10秒）..."):
            df4 = fetch_price(sid4, days4)

        if not df4.empty:
            opt_df = optimize_ma(df4)
            st.subheader("MA Cross 參數最佳化結果（依夏普比率排序）")
            st.dataframe(opt_df.head(20), use_container_width=True, hide_index=True)

            best = opt_df.iloc[0]
            st.success(f"最佳參數：快線 {int(best['fast'])} 天 × 慢線 {int(best['slow'])} 天｜夏普 {best['sharpe']}｜報酬 {best['return%']}%")
