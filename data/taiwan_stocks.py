import requests
import pandas as pd
from datetime import datetime, timedelta
import os

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
TWSE_REALTIME = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


def get_realtime_quote(stock_id: str):
    """
    從 TWSE/TPEX 即時 API 取得盤中報價。
    盤後或無資料時回傳 None，呼叫端應 fallback 到 EOD 資料。
    回傳 dict: price, change, change_pct, high, low, volume, open, prev_close
    """
    headers = {"Referer": "https://mis.twse.com.tw/"}
    for exchange in ("tse", "otc"):
        try:
            ex_ch = f"{exchange}_{stock_id}.tw"
            r = requests.get(
                TWSE_REALTIME,
                params={"ex_ch": ex_ch, "json": "1", "delay": "0"},
                headers=headers,
                timeout=5,
            )
            data = r.json().get("msgArray", [])
            if not data:
                continue
            d = data[0]
            price_str = d.get("z", "-")
            if price_str in ("-", ""):
                # 盤後或停牌：用昨收當作當前價（仍有意義的 fallback）
                price_str = d.get("y", "-")
                if price_str in ("-", ""):
                    continue
                price = float(price_str)
                prev_close = price
                change = 0.0
                change_pct = 0.0
            else:
                price = float(price_str)
                prev_close = float(d.get("y", price))
                change = price - prev_close
                change_pct = change / prev_close * 100 if prev_close else 0.0

            def _f(key):
                v = d.get(key, "-")
                return float(v) if v not in ("-", "") else None

            return {
                "price": price,
                "change": change,
                "change_pct": change_pct,
                "prev_close": prev_close,
                "open": _f("o"),
                "high": _f("h"),
                "low": _f("l"),
                "volume": int(float(d.get("v", 0) or 0)),
                "name": d.get("n", ""),
                "is_realtime": d.get("z", "-") not in ("-", ""),
            }
        except Exception:
            continue
    return None


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


_stock_list_cache: list[dict] = []
_stock_list_ts: float = 0


def _get_all_stocks() -> list[dict]:
    """取得全部台股清單，快取 1 小時"""
    import time
    global _stock_list_cache, _stock_list_ts
    if _stock_list_cache and time.time() - _stock_list_ts < 3600:
        return _stock_list_cache
    try:
        r = requests.get(FINMIND_BASE, params={"dataset": "TaiwanStockInfo", "token": FINMIND_TOKEN}, timeout=15)
        _stock_list_cache = r.json().get("data", [])
        _stock_list_ts = time.time()
    except Exception:
        pass
    return _stock_list_cache


def search_taiwan_stocks(keyword: str) -> list[dict]:
    """搜尋台股股票代號或名稱"""
    keyword = keyword.lower()
    seen: set = set()
    results = []
    for s in _get_all_stocks():
        sid = s.get("stock_id", "")
        if (keyword in sid.lower() or keyword in s.get("stock_name", "").lower()) and sid not in seen:
            seen.add(sid)
            results.append(s)
    return results[:20]


def get_taiwan_market_summary() -> pd.DataFrame:
    """取得大盤指數（加權指數 TAIEX）"""
    return get_taiwan_stock_price("TAIEX", days=90)



def get_financial_statements(stock_id: str, n_quarters: int = 8) -> pd.DataFrame:
    """取得個股財務報表（近 n_quarters 季），回傳含 EPS、毛利率等欄位"""
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset": "TaiwanStockFinancialStatements",
            "data_id": stock_id,
            "token": FINMIND_TOKEN,
        }, timeout=15)
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        pivot = df.pivot_table(index="date", columns="type", values="value", aggfunc="last").reset_index()
        pivot.columns.name = None
        pivot["date"] = pd.to_datetime(pivot["date"])
        pivot = pivot.sort_values("date").tail(n_quarters).reset_index(drop=True)
        if "Revenue" in pivot.columns and "GrossProfit" in pivot.columns:
            pivot["gross_margin"] = pivot["GrossProfit"] / pivot["Revenue"].replace(0, float("nan")) * 100
        for col in ["EPS", "Revenue", "GrossProfit", "NetIncome"]:
            if col not in pivot.columns:
                pivot[col] = float("nan")
        return pivot
    except Exception as e:
        print(f"[FinMind] {stock_id} 財報取得失敗: {e}")
        return pd.DataFrame()


def get_monthly_revenue(stock_id: str, months: int = 14) -> pd.DataFrame:
    """取得個股月營收（近 months 個月），含年增率 YoY"""
    try:
        start = (datetime.now() - timedelta(days=months * 35)).strftime("%Y-%m-%d")
        r = requests.get(FINMIND_BASE, params={
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": stock_id,
            "start_date": start,
            "token": FINMIND_TOKEN,
        }, timeout=15)
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
        # 計算年增率
        df["YoY"] = df["revenue"].pct_change(12) * 100
        return df[["date", "revenue", "YoY"]].tail(months)
    except Exception as e:
        print(f"[FinMind] {stock_id} 月營收取得失敗: {e}")
        return pd.DataFrame()
