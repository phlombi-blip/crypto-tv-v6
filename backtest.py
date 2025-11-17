# backtest.py

"""
Backtest-Modul:
- compute_backtest_trades(df, horizon)
- summarize_backtest(df_bt)

Das Modul erwartet ein DataFrame mit:
    close
    signal
    signal_reason (optional)

Signale: STRONG BUY / BUY / SELL / STRONG SELL
HOLD / NO DATA werden ignoriert.

Komplett UI-frei.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------
# Trades generieren
# ---------------------------------------------------------
def compute_backtest_trades(df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """
    horizon = Anzahl Kerzen, nach denen der Trade geschlossen wird.

    Return DataFrame mit:
      entry_time
      exit_time
      signal
      reason
      entry_price
      exit_price
      ret_pct
      correct (True/False)
    """

    if df.empty or "signal" not in df.columns:
        return pd.DataFrame()

    closes = df["close"].values
    signals = df["signal"].values
    idx = df.index

    has_reason = "signal_reason" in df.columns

    rows = []

    # Trades erzeugen
    for i in range(len(df) - horizon):
        sig = signals[i]

        # Nur echte Trade-Signale
        if sig not in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
            continue

        entry_price = closes[i]
        exit_price = closes[i + horizon]
        if entry_price == 0:
            continue

        ret_pct = (exit_price - entry_price) / entry_price * 100
        direction = 1 if sig in ["BUY", "STRONG BUY"] else -1

        correct = (np.sign(ret_pct) * direction) > 0
        reason = df["signal_reason"].iloc[i] if has_reason else ""

        rows.append(
            {
                "entry_time": idx[i],
                "exit_time": idx[i + horizon],
                "signal": sig,
                "reason": reason,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "ret_pct": float(ret_pct),
                "correct": bool(correct),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------
# Backtest Summaries
# ---------------------------------------------------------
def summarize_backtest(df_bt: pd.DataFrame) -> dict:
    """
    Gibt Stats zurück:
      - total_trades
      - overall_avg_return
      - overall_hit_rate

      pro Signal:
      - Trades
      - Avg Return
      - Hit Rate
    """
    if df_bt.empty:
        return {}

    summary = {
        "total_trades": int(len(df_bt)),
        "overall_avg_return": float(df_bt["ret_pct"].mean()),
        "overall_hit_rate": float(df_bt["correct"].mean() * 100),
        "per_type": []
    }

    for sig in ["STRONG BUY", "BUY", "SELL", "STRONG SELL"]:
        sub = df_bt[df_bt["signal"] == sig]
        if sub.empty:
            continue
        summary["per_type"].append(
            {
                "Signal": sig,
                "Trades": int(len(sub)),
                "Avg Return %": float(sub["ret_pct"].mean()),
                "Hit Rate %": float(sub["correct"].mean() * 100),
            }
        )

    return summary
