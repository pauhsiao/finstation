import yfinance as yf
import pandas as pd


def get_us_stock_price(ticker: str, period: str = "6mo") -> pd.DataFrame:
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df
    except Exception as e:
        print(f"[yfinance] {ticker} 取得失敗: {e}")
        return pd.DataFrame()


def get_us_stock_info(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "name": info.get("longName", ticker),
            "sector": info.get("sector", "—"),
            "industry": info.get("industry", "—"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "currency": info.get("currency", "USD"),
        }
    except Exception:
        return {}


def get_major_indices() -> list[dict]:
    """取得主要美股指數"""
    indices = {
        "^GSPC": "S&P 500",
        "^DJI": "道瓊工業",
        "^IXIC": "納斯達克",
        "^VIX": "恐慌指數 VIX",
    }
    results = []
    for symbol, name in indices.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                curr = hist["Close"].iloc[-1]
                change_pct = (curr - prev) / prev * 100
                results.append({
                    "name": name,
                    "symbol": symbol,
                    "price": curr,
                    "change_pct": change_pct,
                })
        except Exception:
            pass
    return results
