import requests
import pandas as pd
from datetime import datetime, timedelta
import os

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"


def get_taiwan_stock_price(stock_id: str, days: int = 180) -> pd.DataFrame:
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start,
        "token": FINMIND_TOKEN,
    }
    try:
        r = requests.get(FINMIND_BASE, params=params, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={
            "open": "Open", "max": "High", "min": "Low",
            "close": "Close", "Trading_Volume": "Volume"
        })
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"[FinMind] {stock_id} 取得失敗: {e}")
        return pd.DataFrame()


def get_taiwan_stock_info(stock_id: str) -> dict:
    params = {
        "dataset": "TaiwanStockInfo",
        "data_id": stock_id,
        "token": FINMIND_TOKEN,
    }
    try:
        r = requests.get(FINMIND_BASE, params=params, timeout=10)
        data = r.json().get("data", [])
        return data[0] if data else {}
    except Exception:
        return {}


def search_taiwan_stocks(keyword: str) -> list[dict]:
    """搜尋台股股票代號或名稱"""
    params = {
        "dataset": "TaiwanStockInfo",
        "token": FINMIND_TOKEN,
    }
    try:
        r = requests.get(FINMIND_BASE, params=params, timeout=15)
        data = r.json().get("data", [])
        keyword = keyword.lower()
        return [
            s for s in data
            if keyword in s.get("stock_id", "").lower()
            or keyword in s.get("stock_name", "").lower()
        ][:20]
    except Exception:
        return []


def get_taiwan_market_summary() -> pd.DataFrame:
    """取得大盤指數（加權指數 TAIEX）"""
    return get_taiwan_stock_price("TAIEX", days=90)
