"""Entry point. Run: python -m screener.run  [--offline-test] [--force-rebalance]"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

from . import config, data, portfolio, render, scoring

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "index.html")


def _next_rebalance(today) -> str:
    ts = pd.Timestamp(today.date())
    for m in (1, 4, 7, 10):
        cand = pd.Timestamp(year=ts.year, month=m, day=1)
        if cand > ts:
            return cand.strftime("%-d %B %Y")
    return pd.Timestamp(year=ts.year + 1, month=1, day=1).strftime("%-d %B %Y")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline-test", action="store_true",
                    help="run the full pipeline on synthetic data")
    ap.add_argument("--force-rebalance", action="store_true")
    ap.add_argument("--force-warmup-rebalance", action="store_true",
                    help="build the book even while the universe is still loading")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the universe size (useful for a first run)")
    args = ap.parse_args(argv)

    today = data.today_ist()
    print(f"Momentum run — {today:%Y-%m-%d %H:%M} IST")

    if args.offline_test:
        from .synthetic import make_synthetic
        close, volume, meta, bench, vix = make_synthetic()
        universe_n = len(close.columns)
        pending = 0
        rs_bench = pd.Series(dtype=float)
    else:
        uni = data.load_universe()
        if args.limit:
            uni = uni.head(args.limit)
        tickers = uni["yf_ticker"].tolist()
        universe_n = len(tickers)
        print(f"Universe: {universe_n} NSE equities")

        print("Fetching metadata...")
        meta = data.fetch_meta(tickers)
        pending = int(meta.attrs.get("pending", 0))
        # Trim on market cap before pulling prices — this is the single
        # biggest saving in runtime.
        mc = meta["market_cap_cr"].fillna(0)
        keep = meta[(mc >= config.MIN_MARKET_CAP_CR)
                    & (mc <= config.MAX_MARKET_CAP_CR)].index.tolist()
        print(f"  {len(keep)} between Rs {config.MIN_MARKET_CAP_CR:,.0f} cr "
              f"and Rs {config.MAX_MARKET_CAP_CR:,.0f} cr")

        print("Fetching prices...")
        close, volume = data.fetch_prices(keep)
        bench = data.fetch_benchmark()
        rs_bench = data.fetch_rs_benchmark()
        vix = data.fetch_vix()

    print("Scoring...")
    catalysts = data.load_catalysts()
    themes = data.load_themes()
    if rs_bench is None or not len(rs_bench):
        rs_bench = data.build_midsmall_proxy(close)
        print("  relative strength measured against an equal-weight proxy "
              "built from the universe")
    metrics = scoring.compute_metrics(close, volume, meta, bench, rs_bench)
    metrics = scoring.catalyst_scores(metrics, catalysts, themes)
    gated = scoring.apply_gates(metrics)
    # Sector strength is measured across everything liquid and large enough.
    # Measuring it only on names that already passed the trend gates would
    # report 100% breadth for every sector, which tells you nothing.
    investable = gated[gated["g_mcap"] & gated["g_liquidity"]]
    sectors = scoring.sector_table(investable if len(investable) > 20 else gated)
    scored = scoring.composite(gated, sectors)
    scored = scoring.sub_scores(scored, sectors)
    ipos = scoring.new_listings(close, volume, meta, rs_bench)
    if ipos:
        print(f"  {len(ipos)} recent listings holding above their first-week high")
    eligible_n = int(scored["eligible"].sum())
    entry_n = int(scored["entry_ok"].sum())
    print(f"  {eligible_n} cleared the gates, {entry_n} are buyable today")

    # Quarterly results, only for the names that will appear on the page.
    shortlist = list(scored[scored["eligible"]].sort_values(
        "composite", ascending=False).head(config.QUARTERLY_MAX).index)
    quarterly = {} if args.offline_test else data.fetch_quarterly(shortlist)

    def qtr(t: str, key: str):
        v = quarterly.get(t, {}).get(key)
        return float(v) if v is not None else None

    state = data.load_state()
    holdings = state.get("holdings", {})
    regime = portfolio.market_regime(bench, vix)
    print(f"  regime: {regime['state']}")

    # Do not build the opening book off a half-loaded universe. On a cold
    # start the metadata arrives over several runs, and a book chosen from the
    # first 600 names is not the best 20 in the market. Wait for full coverage.
    warming = bool(pending) and not holdings
    if warming:
        print(f"  WARM-UP: {pending} companies still to load. "
              f"Holding off on the opening book.")

    due = (args.force_rebalance or
           portfolio.is_rebalance_due(today, state.get("last_rebalance")))
    if warming and not args.force_warmup_rebalance:
        due = False
    target = portfolio.build_target(scored, holdings, regime, due)
    dropped = list(target.attrs.get("dropped", [])) if due else []

    # Daily exit checks run on whatever the book is, rebalance day or not.
    alerts, exit_now = portfolio.check_exits(target, holdings, close)
    if exit_now:
        target = target.drop(index=exit_now)
        dropped += exit_now
        fills = portfolio.refill(scored, list(target.index),
                                 regime["positions"] - len(target))
        if fills:
            add = scored.reindex(fills).copy()
            add["action"] = "buy"
            add["reason"] = [scored.loc[t, "catalyst_note"] or "Replaces an exited position"
                             for t in fills]
            target = pd.concat([target, add])
        target = portfolio._size_positions(target, regime)

    # ------------------------------------------------------------ payload
    book = []
    for t, r in target.iterrows():
        book.append({
            "ticker": t, "symbol": r["symbol"], "name": str(r["name"])[:38],
            "sector": r["sector"], "rank": int(r["rank"]) if pd.notna(r.get("rank")) else 0,
            "composite": float(r["composite"]) if pd.notna(r.get("composite")) else 0.0,
            "r12m": float(r["r12m"]), "r6m": float(r["r6m"]), "r3m": float(r["r3m"]),
            "ann_vol": float(r["ann_vol"]), "price": float(r["price"]),
            "quality_score": float(r["quality_score"]),
            "weekly_rsi": float(r["weekly_rsi"]) if pd.notna(r.get("weekly_rsi")) else None,
            "ext20": float(r["ext20"]) if pd.notna(r.get("ext20")) else None,
            "ema21w": float(r["ema21w"]) if pd.notna(r.get("ema21w")) else None,
            "rs_days": int(r["rs_days_since_high"]) if pd.notna(r.get("rs_days_since_high")) else None,
            "stop": float(holdings.get(t, {}).get("entry_price", r["price"])) * (1 - config.INITIAL_STOP),
            "catalyst": r.get("catalyst_note") or "",
            "eps_growth": float(r["earnings_growth"]) if pd.notna(r.get("earnings_growth")) else None,
            "sales_growth": float(r["revenue_growth"]) if pd.notna(r.get("revenue_growth")) else None,
            "eps_qoq": qtr(t, "eps_qoq"), "sales_qoq": qtr(t, "sales_qoq"),
            "quarter": quarterly.get(t, {}).get("quarter"),
            "sector_score": float(r["sector_score"]) if pd.notna(r.get("sector_score")) else None,
            "earnings_score": float(r["earnings_score"]) if pd.notna(r.get("earnings_score")) else None,
            "growth_score": float(r["growth_score"]) if pd.notna(r.get("growth_score")) else None,

            "weight": float(r["weight"]), "action": r["action"],
            "reason": r.get("reason", ""),
        })

    sells = []
    for t in dropped:
        row = scored.loc[t] if t in scored.index else None
        rank = int(row["rank"]) if row is not None and pd.notna(row.get("rank")) else None
        sym = row["symbol"] if row is not None else t.replace(".NS", "")
        hit = next((a for a in alerts if a["symbol"] == sym), None)
        why = (hit["kind"] if hit else
               (f"Rank {rank} — outside the {config.BUFFER_RANK} buffer"
                if rank else "No longer clears the gates"))
        sells.append({"symbol": sym, "reason": why})

    # Names that became buyable since the last run. This is the "entering
    # today" list — it updates daily, independent of the rebalance calendar,
    # so a fresh setup is visible the evening it appears.
    buyable_now = set(scored[scored["entry_ok"] & scored["g_sector"]].index)
    prev_buyable = set(state.get("buyable", []))
    fresh = [t for t in buyable_now - prev_buyable if t not in target.index]
    fresh_rows = scored.reindex(fresh).sort_values("composite", ascending=False)
    new_signals = [
        {"symbol": r["symbol"], "sector": r["sector"],
         "rank": int(r["rank"]) if pd.notna(r.get("rank")) else 0,
         "composite": float(r["composite"]) if pd.notna(r.get("composite")) else 0.0,
         "r12m": float(r["r12m"]),
         "weekly_rsi": float(r["weekly_rsi"]) if pd.notna(r.get("weekly_rsi")) else None,
         "ext20": float(r["ext20"]) if pd.notna(r.get("ext20")) else None,
         "rs_days": int(r["rs_days_since_high"]) if pd.notna(r.get("rs_days_since_high")) else None,
         "eps_growth": float(r["earnings_growth"]) if pd.notna(r.get("earnings_growth")) else None,
         "sales_growth": float(r["revenue_growth"]) if pd.notna(r.get("revenue_growth")) else None,
         "eps_qoq": qtr(_, "eps_qoq"), "sales_qoq": qtr(_, "sales_qoq"),
         "quarter": quarterly.get(_, {}).get("quarter"),
         "catalyst": r.get("catalyst_note") or ""}
        for _, r in fresh_rows.head(12).iterrows()
    ]
    state["buyable"] = sorted(buyable_now)

    held_or_target = set(target.index)
    pool = scored[scored["eligible"] & scored["g_sector"]].sort_values("composite", ascending=False)
    watch = [
        {"symbol": r["symbol"], "sector": r["sector"],
         "rank": int(r["rank"]), "composite": float(r["composite"]),
         "buyable": bool(r["entry_ok"]),
         "blocked": r.get("entry_blocked_by", ""),
         "catalyst": r.get("catalyst_note") or ""}
        for _, r in pool.iterrows() if _ not in held_or_target
    ][:10]

    sect_rows = [
        {"sector": s, "rank": int(r["rank"]), "breadth": float(r["breadth"]),
         "median_r6m": float(r["median_r6m"]), "members": int(r["members"])}
        for s, r in sectors.iterrows()
    ][:14]

    candidates = [
        {"symbol": r["symbol"], "name": str(r["name"])[:38], "sector": r["sector"],
         "rank": int(r["rank"]), "composite": float(r["composite"]),
         "r12m": float(r["r12m"]), "r6m": float(r["r6m"]), "r3m": float(r["r3m"]),
         "ann_vol": float(r["ann_vol"]), "price": float(r["price"]),
         "market_cap_cr": float(r["market_cap_cr"]),
         "weekly_rsi": float(r["weekly_rsi"]) if pd.notna(r.get("weekly_rsi")) else None,
         "ext20": float(r["ext20"]) if pd.notna(r.get("ext20")) else None,
         "ext50": float(r["ext50"]) if pd.notna(r.get("ext50")) else None,
         "rs_days": int(r["rs_days_since_high"]) if pd.notna(r.get("rs_days_since_high")) else None,
         "quality_score": float(r["quality_score"]),
         "buyable": bool(r["entry_ok"]),
         "blocked": r.get("entry_blocked_by", ""),
         "held": t in target.index,
         "eps_growth": float(r["earnings_growth"]) if pd.notna(r.get("earnings_growth")) else None,
         "sales_growth": float(r["revenue_growth"]) if pd.notna(r.get("revenue_growth")) else None,
         "eps_qoq": qtr(t, "eps_qoq"), "sales_qoq": qtr(t, "sales_qoq"),
         "quarter": quarterly.get(t, {}).get("quarter"),
         "sector_score": float(r["sector_score"]) if pd.notna(r.get("sector_score")) else None,
         "earnings_score": float(r["earnings_score"]) if pd.notna(r.get("earnings_score")) else None,
         "growth_score": float(r["growth_score"]) if pd.notna(r.get("growth_score")) else None,
         "catalyst": r.get("catalyst_note") or ""}
        for t, r in pool.head(60).iterrows()
    ]

    payload = {
        "stamp": today.strftime("%-d %B %Y"),
        "universe_n": universe_n,
        "eligible_n": eligible_n,
        "entry_n": entry_n,
        "regime": regime,
        "book": book,
        "sells": sells,
        "new_signals": new_signals,
        "first_run": not prev_buyable,
        "alerts": alerts,
        "sectors": sect_rows,
        "watchlist": watch,
        "candidates": candidates,
        "ipos": ipos,
        "top_sectors": config.TOP_SECTORS,
        "watch_from": (watch[0]["rank"] if watch else 0),
        "watch_to": (watch[-1]["rank"] if watch else 0),
        "weight_note": ("equal weight" if config.WEIGHTING == "equal"
                        else "inverse-volatility weighted"),
        "vacant": max(0, regime["positions"] - len(book)),
        "warming": warming,
        "pending": pending,
        "next_rebalance": _next_rebalance(today),
        "rebalanced": bool(due),
    }

    render.render(payload, OUT)
    print(f"Dashboard written to {OUT}")

    if not args.offline_test:
        data.save_state(state)

    if (due or exit_now) and not args.offline_test:
        state["holdings"] = {
            t: {"entry_price": float(r["price"]),
                "entry_date": today.strftime("%Y-%m-%d"),
                "weight": float(r["weight"])}
            if r["action"] == "buy" else holdings.get(t, {"entry_price": float(r["price"])})
            for t, r in target.iterrows()
        }
        state["last_rebalance"] = today.strftime("%Y-%m-%d")
        state.setdefault("history", []).append({
            "date": today.strftime("%Y-%m-%d"),
            "bought": [b["symbol"] for b in book if b["action"] == "buy"],
            "sold": [s["symbol"] for s in sells],
        })
        data.save_state(state)
        print("State updated — rebalance recorded.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
