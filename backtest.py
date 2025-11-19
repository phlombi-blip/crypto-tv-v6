# backtest.py
import numpy as np
import pandas as pd

def compute_backtest_trades(df: pd.DataFrame) -> pd.DataFrame:
    """
    Long-only Logik: Einstieg bei BUY/STRONG BUY, Ausstieg beim nächsten SELL/STRONG SELL
    (oder bei der letzten Kerze, falls kein Gegensignal mehr kommt).
    """
    if df.empty or "signal" not in df.columns or "close" not in df.columns:
        return pd.DataFrame()

    rows = []
    closes = df["close"].values
    signals = df["signal"].values
    idx = df.index

    in_pos = False
    entry_price = None
    entry_idx = None
    entry_sig = None
    entry_pos = None

    for i, sig in enumerate(signals):
        price = closes[i]

        if not in_pos and sig in ["BUY", "STRONG BUY"]:
            entry_price = price
            entry_idx = idx[i]
            entry_sig = sig
            entry_pos = i
            in_pos = True
            continue

        if in_pos and sig in ["SELL", "STRONG SELL"]:
            exit_price = price
            exit_idx = idx[i]
            ret_pct = (exit_price - entry_price) / entry_price * 100
            hold_bars = i - entry_pos
            hold_time = exit_idx - entry_idx if isinstance(exit_idx, pd.Timestamp) else None
            rows.append({
                "entry_time": entry_idx,
                "exit_time": exit_idx,
                "signal": entry_sig,
                "exit_signal": sig,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "ret_pct": ret_pct,
                "correct": ret_pct > 0,
                "hold_bars": hold_bars,
                "hold_time": hold_time,
            })
            in_pos = False

    # Offene Position am Ende schließen
    if in_pos:
        exit_price = closes[-1]
        exit_idx = idx[-1]
        ret_pct = (exit_price - entry_price) / entry_price * 100
        hold_bars = len(df) - 1 - entry_pos
        hold_time = exit_idx - entry_idx if isinstance(exit_idx, pd.Timestamp) else None
        rows.append({
            "entry_time": entry_idx,
            "exit_time": exit_idx,
            "signal": entry_sig,
            "exit_signal": "END",
            "entry_price": entry_price,
            "exit_price": exit_price,
            "ret_pct": ret_pct,
            "correct": ret_pct > 0,
            "hold_bars": hold_bars,
            "hold_time": hold_time,
        })

    return pd.DataFrame(rows)


def summarize_backtest(df_bt: pd.DataFrame):
    if df_bt.empty:
        return {}

    summary = {
        "total_trades": len(df_bt),
        "overall_avg_return": df_bt["ret_pct"].mean(),
        "overall_hit_rate": df_bt["correct"].mean() * 100,
    }

    per = []
    for sig in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
        sub = df_bt[df_bt["signal"] == sig]
        if sub.empty: continue
        per.append({
            "Signal": sig,
            "Trades": len(sub),
            "Avg Return %": sub["ret_pct"].mean(),
            "Hit Rate %": sub["correct"].mean() * 100,
        })

    summary["per_type"] = per
    return summary
