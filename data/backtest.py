import numpy as np
import pandas as pd


def run_backtest(df: pd.DataFrame, signals: pd.Series, initial_capital: float = 100000) -> dict:
    """
    signals: +1=買入, -1=賣出, 0=持有
    回傳績效指標
    """
    df = df.copy().reset_index(drop=True)
    capital = initial_capital
    position = 0
    shares = 0
    equity = []
    trades = []

    for i, row in df.iterrows():
        price = row["Close"]
        sig = signals.iloc[i] if i < len(signals) else 0

        if sig == 1 and position == 0:
            shares = capital / price
            capital = 0
            position = 1
            trades.append({"type": "buy", "date": row["date"], "price": price, "idx": i})
        elif sig == -1 and position == 1:
            capital = shares * price
            shares = 0
            position = 0
            trades.append({"type": "sell", "date": row["date"], "price": price, "idx": i})

        equity.append(capital + shares * price)

    if position == 1:
        capital = shares * df.iloc[-1]["Close"]
        equity[-1] = capital

    equity = np.array(equity)
    returns = np.diff(equity) / equity[:-1]

    total_return = (equity[-1] - initial_capital) / initial_capital * 100
    buy_hold = (df.iloc[-1]["Close"] - df.iloc[0]["Close"]) / df.iloc[0]["Close"] * 100

    drawdowns = equity / np.maximum.accumulate(equity) - 1
    max_drawdown = drawdowns.min() * 100

    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    wins = sum(
        1 for j in range(0, len(trades) - 1, 2)
        if trades[j + 1]["price"] > trades[j]["price"]
    ) if len(trades) >= 2 else 0
    total_trades = len(trades) // 2
    win_rate = wins / total_trades * 100 if total_trades > 0 else 0

    return {
        "total_return": total_return,
        "buy_hold_return": buy_hold,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "equity": equity.tolist(),
        "trades": trades,
    }


def ma_cross_signals(df: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.Series:
    fast_ma = df["Close"].rolling(fast).mean()
    slow_ma = df["Close"].rolling(slow).mean()
    prev_fast = fast_ma.shift(1)
    prev_slow = slow_ma.shift(1)
    signals = pd.Series(0, index=df.index)
    signals[(fast_ma > slow_ma) & (prev_fast <= prev_slow)] = 1
    signals[(fast_ma < slow_ma) & (prev_fast >= prev_slow)] = -1
    return signals


def rsi_signals(df: pd.DataFrame, period: int = 14, oversold: int = 30, overbought: int = 70) -> pd.Series:
    from data.indicators import add_rsi
    df2 = add_rsi(df.copy(), period)
    col = f"RSI_{period}"
    signals = pd.Series(0, index=df2.index)
    signals[(df2[col] < oversold) & (df2[col].shift(1) >= oversold)] = 1
    signals[(df2[col] > overbought) & (df2[col].shift(1) <= overbought)] = -1
    return signals


def bb_signals(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.Series:
    from data.indicators import add_bollinger_bands
    df2 = add_bollinger_bands(df.copy(), period, std)
    signals = pd.Series(0, index=df2.index)
    signals[(df2["Close"] < df2["BB_Lower"]) & (df2["Close"].shift(1) >= df2["BB_Lower"])] = 1
    signals[(df2["Close"] > df2["BB_Upper"]) & (df2["Close"].shift(1) <= df2["BB_Upper"])] = -1
    return signals


def optimize_ma(df: pd.DataFrame, fast_range=(3, 15), slow_range=(10, 60)) -> pd.DataFrame:
    results = []
    for fast in range(fast_range[0], fast_range[1] + 1, 2):
        for slow in range(slow_range[0], slow_range[1] + 1, 5):
            if fast >= slow:
                continue
            sigs = ma_cross_signals(df, fast, slow)
            r = run_backtest(df, sigs)
            results.append({"fast": fast, "slow": slow, "sharpe": round(r["sharpe"], 2),
                            "return%": round(r["total_return"], 2), "trades": r["total_trades"]})
    return pd.DataFrame(results).sort_values("sharpe", ascending=False)


def calc_var(returns: pd.Series, confidence: float = 0.95) -> float:
    return float(np.percentile(returns.dropna(), (1 - confidence) * 100))
