# backtest.py
import numpy as np
import pandas as pd

def compute_backtest_trades(df: pd.DataFrame, max_hold_bars: int = 40, tp_mult: float = 1.2, atr_mult: float = 2.0) -> pd.DataFrame:
    """
    Long-only Logik: Einstieg bei BUY/STRONG BUY, Ausstieg beim nächsten SELL/STRONG SELL
    (oder bei der letzten Kerze, falls kein Gegensignal mehr kommt).
    """
    if df.empty or "signal" not in df.columns or "close" not in df.columns:
        return pd.DataFrame()

    rows = []
    closes = df["close"].values
    highs = df["high"].values if "high" in df.columns else closes
    lows = df["low"].values if "low" in df.columns else closes
    signals = df["signal"].values
    idx = df.index
    atrs = df["atr14"].values if "atr14" in df.columns else np.full(len(df), np.nan)

    in_pos = False
    entry_price = None
    entry_idx = None
    entry_sig = None
    entry_pos = None
    entry_atr = None

    for i, sig in enumerate(signals):
        price = closes[i]

        if not in_pos and sig in ["BUY", "STRONG BUY"]:
            entry_price = price
            entry_idx = idx[i]
            entry_sig = sig
            entry_pos = i
            entry_atr = atrs[i] if i < len(atrs) else np.nan
            in_pos = True
            continue

        # Exit durch Gegensignal
        if in_pos and sig in ["SELL", "STRONG SELL"]:
            exit_price = price
            exit_idx = idx[i]
            hold_bars = i - entry_pos
            hold_time = exit_idx - entry_idx if isinstance(exit_idx, pd.Timestamp) else None
            risk_abs = (entry_atr * atr_mult) if entry_atr and not np.isnan(entry_atr) else entry_price * 0.02
            tp_level = entry_price + risk_abs * tp_mult
            # TP/Stop Simulation auf Close-Basis (vereinfachend)
            hit_tp = any(closes[j] >= tp_level for j in range(entry_pos, i + 1))
            ret_abs = exit_price - entry_price
            if hit_tp:
                # Hälfte bei TP, Rest beim finalen Exit
                ret_final = 0.5 * (tp_level - entry_price) + 0.5 * (exit_price - entry_price)
                ret_pct = ret_final / entry_price * 100
                r_multiple = ret_final / risk_abs if risk_abs else np.nan
            else:
                ret_pct = ret_abs / entry_price * 100
                r_multiple = ret_abs / risk_abs if risk_abs else np.nan
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
                "r_multiple": r_multiple,
            })
            in_pos = False
            continue

        # Time-Stop (max_hold_bars)
        if in_pos and max_hold_bars and (i - entry_pos) >= max_hold_bars:
            exit_price = price
            exit_idx = idx[i]
            hold_bars = i - entry_pos
            hold_time = exit_idx - entry_idx if isinstance(exit_idx, pd.Timestamp) else None
            risk_abs = (entry_atr * atr_mult) if entry_atr and not np.isnan(entry_atr) else entry_price * 0.02
            tp_level = entry_price + risk_abs * tp_mult
            hit_tp = any(closes[j] >= tp_level for j in range(entry_pos, i + 1))
            ret_abs = exit_price - entry_price
            if hit_tp:
                ret_final = 0.5 * (tp_level - entry_price) + 0.5 * (exit_price - entry_price)
                ret_pct = ret_final / entry_price * 100
                r_multiple = ret_final / risk_abs if risk_abs else np.nan
            else:
                ret_pct = ret_abs / entry_price * 100
                r_multiple = ret_abs / risk_abs if risk_abs else np.nan
            rows.append({
                "entry_time": entry_idx,
                "exit_time": exit_idx,
                "signal": entry_sig,
                "exit_signal": "TIME_STOP",
                "entry_price": entry_price,
                "exit_price": exit_price,
                "ret_pct": ret_pct,
                "correct": ret_pct > 0,
                "hold_bars": hold_bars,
                "hold_time": hold_time,
                "r_multiple": r_multiple,
            })
            in_pos = False

    # Offene Position am Ende schließen
    if in_pos:
        exit_price = closes[-1]
        exit_idx = idx[-1]
        hold_bars = len(df) - 1 - entry_pos
        hold_time = exit_idx - entry_idx if isinstance(exit_idx, pd.Timestamp) else None
        risk_abs = (entry_atr * atr_mult) if entry_atr and not np.isnan(entry_atr) else entry_price * 0.02
        tp_level = entry_price + risk_abs * tp_mult
        hit_tp = any(closes[j] >= tp_level for j in range(entry_pos, len(df)))
        ret_abs = exit_price - entry_price
        if hit_tp:
            ret_final = 0.5 * (tp_level - entry_price) + 0.5 * (exit_price - entry_price)
            ret_pct = ret_final / entry_price * 100
            r_multiple = ret_final / risk_abs if risk_abs else np.nan
        else:
            ret_pct = ret_abs / entry_price * 100
            r_multiple = ret_abs / risk_abs if risk_abs else np.nan
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
            "r_multiple": r_multiple,
        })

    return pd.DataFrame(rows)


def summarize_backtest(df_bt: pd.DataFrame):
    if df_bt.empty:
        return {}

    summary = {
        "total_trades": len(df_bt),
        "overall_avg_return": df_bt["ret_pct"].mean(),
        "overall_hit_rate": df_bt["correct"].mean() * 100,
        "overall_avg_r": df_bt["r_multiple"].mean() if "r_multiple" in df_bt.columns else np.nan,
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
            "Avg R": sub["r_multiple"].mean() if "r_multiple" in sub.columns else np.nan,
        })

    summary["per_type"] = per
    return summary
