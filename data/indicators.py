import pandas as pd


def add_moving_averages(df: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    df = df.copy()
    for w in windows:
        if len(df) >= w:
            df[f"MA{w}"] = df["Close"].rolling(w).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("inf"))
    df["RSI"] = 100 - 100 / (1 + rs)
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    df = df.copy()
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
    return df


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    df = df.copy()
    mid = df["Close"].rolling(period).mean()
    s = df["Close"].rolling(period).std()
    df["BB_Upper"] = mid + std * s
    df["BB_Mid"] = mid
    df["BB_Lower"] = mid - std * s
    return df
