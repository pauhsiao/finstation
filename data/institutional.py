import requests
import pandas as pd
from datetime import datetime, timedelta
import os

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
TWSE_BASE = "https://www.twse.com.tw/rwd/zh/fund"


def get_institutional_history(stock_id: str, days: int = 60) -> pd.DataFrame:
    """從 FinMind 取得個股三大法人歷史買賣超（單位：張）"""
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset": "InstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": start,
            "token": FINMIND_TOKEN,
        }, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])

        # 整理成每日一行（外資、投信、自營商）
        pivot = df.pivot_table(
            index="date", columns="name",
            values="buy_sell", aggfunc="sum"
        ).reset_index()
        pivot.columns.name = None

        col_map = {
            "外資及陸資(不含外資自營商)": "外資",
            "外資及陸資": "外資",
            "投信": "投信",
            "自營商": "自營商",
            "自營商(自行買賣)": "自營商",
        }
        pivot.rename(columns=col_map, inplace=True)

        # 確保三欄都存在
        for col in ["外資", "投信", "自營商"]:
            if col not in pivot.columns:
                pivot[col] = 0

        # 三大法人合計
        pivot["合計"] = pivot[["外資", "投信", "自營商"]].sum(axis=1)
        pivot = pivot.sort_values("date", ascending=False).reset_index(drop=True)
        return pivot[["date", "外資", "投信", "自營商", "合計"]]
    except Exception:
        return pd.DataFrame()


def get_market_institutional_today() -> pd.DataFrame:
    """從 TWSE 取得今日全市場三大法人買賣超（前20大）"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        r = requests.get(
            f"{TWSE_BASE}/T86",
            params={"response": "json", "date": today, "selectType": "ALL"},
            headers={"Referer": "https://www.twse.com.tw/"},
            timeout=8,
        )
        r.raise_for_status()
        js = r.json()
        rows = js.get("data", [])
        if not rows:
            return pd.DataFrame()

        cols = ["股票代號", "股票名稱", "外資買賣超", "投信買賣超", "自營商買賣超", "三大法人合計"]
        records = []
        for row in rows:
            if len(row) < 7:
                continue
            try:
                records.append({
                    "股票代號": row[0].strip(),
                    "股票名稱": row[1].strip(),
                    "外資買賣超": int(row[4].replace(",", "").replace("+", "")),
                    "投信買賣超": int(row[5].replace(",", "").replace("+", "")),
                    "自營商買賣超": int(row[6].replace(",", "").replace("+", "")),
                    "三大法人合計": int(row[3].replace(",", "").replace("+", "")),
                })
            except Exception:
                continue

        df = pd.DataFrame(records)
        return df.sort_values("三大法人合計", ascending=False)
    except Exception:
        return pd.DataFrame()


def get_institutional_holding(stock_id: str) -> dict:
    """從 FinMind 取得個股外資持股比例（最新一筆）"""
    try:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        r = requests.get(FINMIND_BASE, params={
            "dataset": "TaiwanStockHoldingShares",
            "data_id": stock_id,
            "start_date": start,
            "token": FINMIND_TOKEN,
        }, timeout=10)
        data = r.json().get("data", [])
        if not data:
            return {}
        latest = data[-1]
        return {
            "date": latest.get("date"),
            "foreign_holding_pct": latest.get("ForeignInvestmentSharesRatio", 0),
        }
    except Exception:
        return {}
