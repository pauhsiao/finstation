import os
import requests
import pandas as pd
from datetime import datetime, timedelta

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def get_fred_series(series_id: str, years: int = 3) -> pd.DataFrame:
    if not FRED_API_KEY:
        return pd.DataFrame()
    start = (datetime.now() - timedelta(days=365 * years)).strftime("%Y-%m-%d")
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start,
    }
    try:
        r = requests.get(FRED_BASE, params=params, timeout=10)
        data = r.json().get("observations", [])
        df = pd.DataFrame(data)[["date", "value"]]
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"[FRED] {series_id} 失敗: {e}")
        return pd.DataFrame()


MACRO_SERIES = {
    "FEDFUNDS": "聯邦基金利率 (%)",
    "CPIAUCSL": "美國 CPI（消費者物價）",
    "UNRATE": "美國失業率 (%)",
    "T10Y2Y": "10Y-2Y 殖利率利差",
    "DGS10": "10 年期公債殖利率",
    "DTWEXBGS": "美元指數（廣泛）",
}


def get_all_macro() -> dict[str, pd.DataFrame]:
    return {label: get_fred_series(sid) for sid, label in MACRO_SERIES.items()}
