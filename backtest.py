# backtest.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Dict, Any

import numpy as np
import pandas as pd

SignalType = Literal["BUY", "SELL", "HOLD", "NONE", ""]


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    return_pct: float
    bars_held: int


def _normalize_signal(value: Any) -> SignalType:
    if value is None:
        return "NONE"
    s = str(value).strip().upper()
    if s in {"BUY", "SELL", "HOLD"}:
        return s  # type: ignore[return-value]
    return "NONE"


def backtest_on_signals(
    df: pd.DataFrame,
    price_col: str = "close",
    signal_col: str = "signal",
    initial_capital: float = 1000.0,
) -> Dict[str, Any]:
    """
    Einfacher Swing-Backtest:
    - BUY  -> kaufe alles zum Close
    - SELL -> verkaufe alles zum Close
    - Weitere BUYs während Position ignorieren
    - Weitere SELLs ohne Position ignorieren

    Erwartet:
        df.index: DatetimeIndex (oder etwas, das wie Timestamps aussieht)
        df[price_col]: float
        df[signal_col]: BUY/SELL/HOLD/NONE

    Returns:
        {
            "trades": List[Trade],
            "equity_curve": pd.Series,
            "stats": Dict[str, float]
        }
    """
    if price_col not in df.columns:
        raise ValueError(f"Spalte '{price_col}' nicht im DataFrame")
    if signal_col not in df.columns:
        raise ValueError(f"Spalte '{signal_col}' nicht im DataFrame")

    prices = df[price_col].astype(float)
    signals = df[signal_col].map(_normalize_signal)

    capital = float(initial_capital)
    position_qty: float = 0.0
    entry_price: Optional[float] = None
    entry_time: Optional[pd.Timestamp] = None

    trades: List[Trade] = []
    equity_values: List[float] = []
    equity_index: List[pd.Timestamp] = []

    for ts, price, sig in zip(df.index, prices, signals):
        # Aktualisiere Equity (Mark-to-Market)
        equity = capital + position_qty * price
        equity_index.append(ts)
        equity_values.append(equity)

        # Keine Signale -> weiter
        if sig in ("NONE", "HOLD"):
            continue

        # BUY-Signal
        if sig == "BUY":
            if position_qty > 0:
                # Schon in Position -> ignorieren (oder später: pyramiding, scaling etc.)
                continue
            if capital <= 0:
                continue
            position_qty = capital / price
            entry_price = price
            entry_time = pd.to_datetime(ts)
            capital = 0.0

        # SELL-Signal
        elif sig == "SELL":
            if position_qty <= 0:
                # Keine Position -> ignorieren
                continue
            exit_price = price
            exit_time = pd.to_datetime(ts)
            capital = position_qty * price
            bars_held = int(len(df.loc[entry_time:exit_time])) if entry_time is not None else 0
            ret_pct = (exit_price / entry_price - 1.0) * 100.0 if entry_price else 0.0
            trades.append(
                Trade(
                    entry_time=entry_time,
                    exit_time=exit_time,
                    entry_price=float(entry_price),
                    exit_price=float(exit_price),
                    return_pct=float(ret_pct),
                    bars_held=bars_held,
                )
            )
            position_qty = 0.0
            entry_price = None
            entry_time = None

    # Falls am Ende noch Position offen: zum letzten Close glattstellen
    if position_qty > 0:
        last_ts = df.index[-1]
        last_price = float(prices.iloc[-1])
        exit_time = pd.to_datetime(last_ts)
        exit_price = last_price
        capital = position_qty * last_price
        bars_held = int(len(df.loc[entry_time:exit_time])) if entry_time is not None else 0
        ret_pct = (exit_price / entry_price - 1.0) * 100.0 if entry_price else 0.0
        trades.append(
            Trade(
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=float(entry_price),
                exit_price=float(exit_price),
                return_pct=float(ret_pct),
                bars_held=bars_held,
            )
        )
        position_qty = 0.0

        # letzte Equity aktualisieren
        equity_values[-1] = capital

    equity_series = pd.Series(equity_values, index=pd.to_datetime(equity_index))
    total_return_pct = (equity_series.iloc[-1] / initial_capital - 1.0) * 100.0

    if len(trades) > 0:
        trade_returns = np.array([t.return_pct for t in trades], dtype=float)
        win_rate = float((trade_returns > 0).mean() * 100.0)
        avg_trade = float(trade_returns.mean())
        max_dd = float(
            ((equity_series.cummax() - equity_series) / equity_series.cummax()).max()
            * 100.0
        )
    else:
        win_rate = 0.0
        avg_trade = 0.0
        max_dd = 0.0

    stats = {
        "initial_capital": float(initial_capital),
        "final_equity": float(equity_series.iloc[-1]),
        "total_return_pct": float(total_return_pct),
        "num_trades": len(trades),
        "win_rate_pct": float(win_rate),
        "avg_trade_return_pct": float(avg_trade),
        "max_drawdown_pct": float(max_dd),
    }

    return {
        "trades": trades,
        "equity_curve": equity_series,
        "stats": stats,
    }
