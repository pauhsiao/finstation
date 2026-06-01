import pandas as pd
from data.taiwan_stocks import get_taiwan_stock_price, get_monthly_revenue, get_financial_statements
from data.institutional import get_institutional_history, get_margin_trading
from data.indicators import add_moving_averages, add_macd, add_bollinger_bands


def score_stock(stock_id: str) -> dict:
    details = {}
    tech_score = 0
    chips_score = 0
    fund_score = 0

    # ── 技術面 45分 ──────────────────────────────────────────
    try:
        df = get_taiwan_stock_price(stock_id, days=120)
        if not df.empty and len(df) >= 20:
            df = add_moving_averages(df)
            df = add_macd(df)
            df = add_bollinger_bands(df)
            latest = df.iloc[-1]
            close = float(latest["Close"])

            # 1. 均線多頭排列 (10分)
            ma5 = latest.get("MA5")
            ma20 = latest.get("MA20")
            ma60 = latest.get("MA60")
            ma_score = 0
            if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60):
                if ma5 > ma20 > ma60:
                    ma_score = 10
                elif ma5 > ma20 or ma20 > ma60:
                    ma_score = 5
            elif pd.notna(ma5) and pd.notna(ma20):
                if ma5 > ma20:
                    ma_score = 5
            details["ma_bullish"] = {"score": ma_score, "max": 10, "desc": "均線多頭排列"}
            tech_score += ma_score

            # 2. MACD 轉強 (10分)
            macd_score = 0
            macd_val = latest.get("MACD")
            macd_sig = latest.get("MACD_Signal")
            if pd.notna(macd_val) and pd.notna(macd_sig):
                if macd_val > macd_sig:
                    macd_score += 5
                if macd_val > 0:
                    macd_score += 5
            details["macd"] = {"score": macd_score, "max": 10, "desc": "MACD 轉強（DIF>DEA/MACD>0）"}
            tech_score += macd_score

            # 3. 突破近60/20日高點 (10分)
            high60 = float(df["High"].tail(60).max()) if len(df) >= 60 else float(df["High"].max())
            high20 = float(df["High"].tail(20).max())
            if close >= high60:
                break_score = 10
                break_desc = "突破近60日高點"
            elif close >= high20:
                break_score = 5
                break_desc = "突破近20日高點"
            else:
                break_score = 0
                break_desc = "未突破近期高點"
            details["breakthrough"] = {"score": break_score, "max": 10, "desc": break_desc}
            tech_score += break_score

            # 4. 布林通道位置 (8分)
            bb_upper = latest.get("BB_Upper")
            bb_lower = latest.get("BB_Lower")
            bb_score = 0
            if pd.notna(bb_upper) and pd.notna(bb_lower) and bb_upper != bb_lower:
                ratio = (close - float(bb_lower)) / (float(bb_upper) - float(bb_lower))
                ratio = max(0.0, min(1.0, ratio))
                bb_score = round(ratio * 8)
            details["bb_position"] = {"score": bb_score, "max": 8, "desc": f"布林通道位置（{bb_score}/8）"}
            tech_score += bb_score

            # 5. 量能放大 (7分)
            vol_score = 0
            if "Volume" in df.columns and len(df) >= 20:
                vol5 = df["Volume"].tail(5).mean()
                vol20 = df["Volume"].tail(20).mean()
                if vol20 > 0:
                    ratio = vol5 / vol20
                    if ratio >= 1.2:
                        vol_score = 7
                    elif ratio >= 1.0:
                        vol_score = 4
            details["volume"] = {"score": vol_score, "max": 7, "desc": "量能放大（5日均量/20日均量）"}
            tech_score += vol_score
    except Exception as e:
        details["tech_error"] = {"score": 0, "max": 45, "desc": f"技術面資料取得失敗: {e}"}

    # ── 籌碼面 35分 ──────────────────────────────────────────
    try:
        df_inst = get_institutional_history(stock_id, days=10)
        if not df_inst.empty:
            recent5 = df_inst.head(5)

            # 6. 外資連買 (12分)
            foreign_buy_days = 0
            for _, row in recent5.iterrows():
                if row.get("外資", 0) > 0:
                    foreign_buy_days += 1
                else:
                    break
            if foreign_buy_days >= 5:
                foreign_score = 12
            elif foreign_buy_days >= 3:
                foreign_score = 8
            elif foreign_buy_days >= 1:
                foreign_score = 4
            else:
                foreign_score = 0
            details["foreign"] = {"score": foreign_score, "max": 12, "desc": f"外資連買 {foreign_buy_days} 日"}
            chips_score += foreign_score

            # 7. 投信連買 (10分)
            trust_buy_days = 0
            for _, row in recent5.iterrows():
                if row.get("投信", 0) > 0:
                    trust_buy_days += 1
                else:
                    break
            if trust_buy_days >= 5:
                trust_score = 10
            elif trust_buy_days >= 3:
                trust_score = 6
            elif trust_buy_days >= 1:
                trust_score = 3
            else:
                trust_score = 0
            details["trust"] = {"score": trust_score, "max": 10, "desc": f"投信連買 {trust_buy_days} 日"}
            chips_score += trust_score
    except Exception:
        pass

    # 8. 融資/融券訊號 (8分)
    try:
        df_margin = get_margin_trading(stock_id, days=5)
        if not df_margin.empty and len(df_margin) >= 2:
            latest_m = df_margin.iloc[0]
            prev_m = df_margin.iloc[1]
            margin_up = latest_m.get("MarginPurchaseBalance", 0) > prev_m.get("MarginPurchaseBalance", 0)
            short_down = latest_m.get("ShortSaleBalance", 0) < prev_m.get("ShortSaleBalance", 0)
            if margin_up and short_down:
                margin_score = 8
                margin_desc = "融資增加且融券減少（多頭訊號）"
            elif margin_up or short_down:
                margin_score = 4
                margin_desc = "融資增加或融券減少"
            else:
                margin_score = 0
                margin_desc = "融資融券無明顯訊號"
            details["margin"] = {"score": margin_score, "max": 8, "desc": margin_desc}
            chips_score += margin_score
    except Exception:
        pass

    # 9. 新聞情緒 (5分) — 預設中性 2分
    details["news_sentiment"] = {"score": 2, "max": 5, "desc": "新聞情緒（中性，需個別查詢）"}
    chips_score += 2

    # ── 基本面 20分 ──────────────────────────────────────────
    # 10. 月營收年增率 (10分)
    try:
        df_rev = get_monthly_revenue(stock_id, months=14)
        if not df_rev.empty and "YoY" in df_rev.columns:
            yoy = df_rev.dropna(subset=["YoY"])
            if not yoy.empty:
                latest_yoy = float(yoy.iloc[-1]["YoY"])
                if latest_yoy > 20:
                    rev_score = 10
                elif latest_yoy > 10:
                    rev_score = 7
                elif latest_yoy > 0:
                    rev_score = 4
                else:
                    rev_score = 0
                details["revenue_yoy"] = {"score": rev_score, "max": 10, "desc": f"月營收年增率 {latest_yoy:.1f}%"}
                fund_score += rev_score
    except Exception:
        pass

    # 11. 毛利率趨勢 (10分)
    try:
        df_fs = get_financial_statements(stock_id, n_quarters=4)
        if not df_fs.empty and "gross_margin" in df_fs.columns:
            gm_data = df_fs.dropna(subset=["gross_margin"])
            if len(gm_data) >= 2:
                latest_gm = float(gm_data.iloc[-1]["gross_margin"])
                prev_gm = float(gm_data.iloc[-2]["gross_margin"])
                if latest_gm > prev_gm + 1:
                    gm_score = 10
                    gm_trend = "上升"
                elif latest_gm >= prev_gm - 1:
                    gm_score = 5
                    gm_trend = "持平"
                else:
                    gm_score = 0
                    gm_trend = "下降"
                details["gross_margin"] = {
                    "score": gm_score, "max": 10,
                    "desc": f"毛利率 {latest_gm:.1f}%（{gm_trend}，前季 {prev_gm:.1f}%）"
                }
                fund_score += gm_score
    except Exception:
        pass

    total = tech_score + chips_score + fund_score

    return {
        "total": total,
        "tech": tech_score,
        "chips": chips_score,
        "fundamental": fund_score,
        "details": details,
    }
