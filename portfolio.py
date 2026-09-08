"""Regime filter, buffered quarterly rebalance, and position sizing."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


# ------------------------------------------------------------------ regime
def market_regime(bench: pd.Series, vix: float | None) -> dict:
    """Three states drive how much capital is deployed."""
    if bench is None or len(bench) < 220:
        return {"state": "unknown", "invested": 1.0, "positions": config.PORTFOLIO_SIZE,
                "detail": "Benchmark history unavailable — defaulting to fully invested.",
                "last": None, "sma200": None, "rising": None, "vix": vix}

    last = float(bench.iloc[-1])
    sma200 = float(bench.rolling(200).mean().iloc[-1])
    sma200_prev = float(bench.rolling(200).mean().iloc[-21])
    rising = sma200 > sma200_prev
    above = last > sma200

    if above:
        state, invested, positions = "risk-on", 1.0, config.PORTFOLIO_SIZE
        detail = "Nifty 500 is above a rising 200-day average. Run the full book."
        if not rising:
            detail = "Nifty 500 has reclaimed its 200-day average but the average is still falling. Full book, tighter stops."
    elif rising:
        state, invested, positions = "caution", 1.0, config.PORTFOLIO_SIZE
        detail = "Index below its 200-day average, but the average is still rising. Stay invested and tighten stops."
    else:
        state, invested, positions = "risk-off", 0.5, 10
        detail = "Index below a falling 200-day average. Cut to half the book and the ten strongest names."

    if vix and vix > config.VIX_PANIC and not above:
        state, invested, positions = "defensive", 0.3, 8
        detail = f"India VIX at {vix:.0f} with the index below its 200-day average. Hold 30% invested."

    return {"state": state, "invested": invested, "positions": positions,
            "detail": detail, "last": last, "sma200": sma200,
            "rising": bool(rising), "vix": vix}


# --------------------------------------------------------------- rebalance
def is_rebalance_due(today, last_rebalance: str | None) -> bool:
    """Quarterly: first run of Jan, Apr, Jul, Oct."""
    if last_rebalance is None:
        return True
    prev = pd.Timestamp(last_rebalance)
    now = pd.Timestamp(today.date())
    if now.month not in (1, 4, 7, 10):
        return False
    return (now.year, now.month) != (prev.year, prev.month)


def build_target(scored: pd.DataFrame, holdings: dict, regime: dict,
                 rebalance: bool) -> pd.DataFrame:
    """Apply the buffer rule and sector caps to produce the target book.

    Between rebalances the target is simply the current book, so the
    dashboard shows what you own and only flags risk exits.
    """
    # Ranking uses every eligible name, so a holding keeps a meaningful rank
    # even while it is temporarily too extended to be a fresh buy.
    pool = scored[scored["eligible"] & scored["g_sector"]].copy()
    pool = pool.sort_values("composite", ascending=False)
    pool["rank"] = range(1, len(pool) + 1)
    buyable = pool[pool["entry_ok"]]

    size = regime["positions"]
    held = list(holdings.keys())

    if not rebalance:
        target = [t for t in held if t in scored.index]
        keep = scored.loc[target].copy() if target else scored.head(0).copy()
        keep["action"] = "hold"
        keep["reason"] = "Between rebalances"
        return _size_positions(keep, regime)

    # 1. survivors: still ranked inside the buffer
    survivors = [t for t in held if t in pool.index and pool.loc[t, "rank"] <= config.BUFFER_RANK]
    dropped = [t for t in held if t not in survivors]

    # 2. fill the rest from the top of the list, respecting the sector cap
    selected = list(survivors)
    sector_count: dict[str, int] = {}
    for t in selected:
        s = pool.loc[t, "sector"]
        sector_count[s] = sector_count.get(s, 0) + 1

    # The turnover cap limits *churn*, not the initial build. If the book is
    # short of target (first run, or names dropped out), fill it regardless.
    vacancies = max(0, size - len(survivors))
    add_limit = max(config.MAX_TURNOVER, vacancies)

    added: list[str] = []
    for t, row in buyable.iterrows():
        if len(selected) >= size:
            break
        if t in selected:
            continue
        s = row["sector"]
        if sector_count.get(s, 0) >= config.MAX_PER_SECTOR:
            continue
        if len(added) >= add_limit:
            break
        selected.append(t)
        added.append(t)
        sector_count[s] = sector_count.get(s, 0) + 1

    # 3. if the book is still over size, cut the weakest survivors
    if len(selected) > size:
        ranked = pool.reindex(selected).sort_values("composite", ascending=False)
        selected = list(ranked.index[:size])

    target = scored.reindex(selected).copy()
    target["action"] = ["buy" if t in added else "hold" for t in target.index]
    target["reason"] = [
        (scored.loc[t, "catalyst_note"] or "Enters the top ranks") if t in added
        else f"Held — rank {int(pool.loc[t, 'rank'])} is inside the {config.BUFFER_RANK} buffer"
        for t in target.index
    ]
    target.attrs["dropped"] = dropped
    return _size_positions(target, regime)


def _size_positions(target: pd.DataFrame, regime: dict) -> pd.DataFrame:
    if target.empty:
        target["weight"] = []
        return target
    investable = (1 - config.CASH_BUFFER) * regime["invested"]
    if config.WEIGHTING == "inverse_vol":
        inv = 1 / target["ann_vol"].replace(0, np.nan)
        w = inv / inv.sum()
        w = w.clip(config.MIN_WEIGHT, config.MAX_WEIGHT)
        w = w / w.sum()
    else:
        w = pd.Series(1 / len(target), index=target.index)
    target["weight"] = w * investable
    return target


# ------------------------------------------------------------------- exits
def check_exits(target: pd.DataFrame, holdings: dict,
                close: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Daily exit checks. Returns (alerts, tickers to sell now).

    Order matters: the initial stop is checked first because it is the
    tightest and the least forgiving.
    """
    alerts, to_sell = [], []
    for t, row in target.iterrows():
        h = holdings.get(t, {})
        entry = h.get("entry_price")
        fired = None

        if entry and row["price"] <= entry * (1 - config.INITIAL_STOP):
            fired = {
                "symbol": row["symbol"], "kind": "Stop hit",
                "detail": f"Down {(1 - row['price'] / entry) * 100:.1f}% from your "
                          f"entry at Rs {entry:,.0f}. Sell.",
            }
        elif (config.EXIT_BELOW_21WEMA and pd.notna(row.get("ema21w"))
              and pd.notna(row.get("weekly_close"))
              and row["weekly_close"] < row["ema21w"]):
            fired = {
                "symbol": row["symbol"], "kind": "Below the 21-week EMA",
                "detail": f"Weekly close of Rs {row['weekly_close']:,.0f} is under the "
                          f"21-week EMA at Rs {row['ema21w']:,.0f}. Sell.",
            }
        elif config.EXIT_BELOW_SMA200 and row["price"] < row["sma200"]:
            fired = {
                "symbol": row["symbol"], "kind": "Below the 200-day average",
                "detail": f"Trading {(1 - row['price'] / row['sma200']) * 100:.1f}% under "
                          f"its 200-day average. Sell.",
            }
        elif config.TRAILING_STOP and entry and t in close.columns:
            peak = float(close[t].dropna().tail(250).max())
            if peak and row["price"] < peak * (1 - config.TRAILING_STOP):
                fired = {
                    "symbol": row["symbol"], "kind": "Trailing stop",
                    "detail": f"Down {(1 - row['price'] / peak) * 100:.1f}% from its high "
                              f"since entry. Sell.",
                }

        if fired:
            alerts.append(fired)
            to_sell.append(t)
    return alerts, to_sell


def refill(scored: pd.DataFrame, keep: list[str], vacancies: int) -> list[str]:
    """Fill seats vacated by an exit, without waiting for the quarter.

    Candidates must clear the entry criteria, not merely the ranking gates.
    """
    if vacancies <= 0 or not config.REFILL_ON_EXIT:
        return []
    pool = scored[scored["entry_ok"] & scored["g_sector"]].sort_values(
        "composite", ascending=False)
    sector_count: dict[str, int] = {}
    for t in keep:
        if t in scored.index:
            s = scored.loc[t, "sector"]
            sector_count[s] = sector_count.get(s, 0) + 1

    picks = []
    for t, row in pool.iterrows():
        if len(picks) >= min(vacancies, config.MAX_REFILLS_PER_RUN):
            break
        if t in keep:
            continue
        s = row["sector"]
        if sector_count.get(s, 0) >= config.MAX_PER_SECTOR:
            continue
        picks.append(t)
        sector_count[s] = sector_count.get(s, 0) + 1
    return picks
