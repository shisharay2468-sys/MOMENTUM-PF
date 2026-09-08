"""Synthetic NSE-like data so the pipeline can be verified without network.

Used by `python -m screener.run --offline-test`. Not part of the live path.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SECTORS = ["Capital Goods", "Pharmaceuticals", "Information Technology",
           "Financial Services", "Auto Components", "Chemicals", "Metals",
           "Consumer Durables", "Realty", "Power"]


def make_synthetic(n=260, days=520, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    tickers = [f"SYN{i:03d}.NS" for i in range(n)]

    closes, volumes, meta = {}, {}, []
    for i, t in enumerate(tickers):
        sector = SECTORS[i % len(SECTORS)]
        # sector-level drift so the sector overlay has something to find
        sector_drift = np.linspace(0.0018, -0.0006, len(SECTORS))[i % len(SECTORS)]
        idio = rng.normal(0, 0.0006)
        vol = rng.uniform(0.012, 0.035)
        r = rng.normal(sector_drift + idio, vol, days)
        px = 100 * np.exp(np.cumsum(r)) * rng.uniform(0.5, 6)
        closes[t] = pd.Series(px, index=idx)
        volumes[t] = pd.Series(rng.uniform(2e5, 4e6, days), index=idx)
        meta.append({
            "ticker": t, "name": f"Synthetic Industries {i}", "sector": sector,
            "industry": sector,
            "market_cap_cr": float(rng.uniform(600, 40000)),
            "revenue_growth": float(rng.uniform(-0.1, 0.5)),
            "earnings_growth": float(rng.uniform(-0.2, 0.9)),
            "roe": float(rng.uniform(0.02, 0.4)),
            "debt_to_equity": float(rng.uniform(0, 220)),
            "op_cashflow": float(rng.uniform(1e8, 9e9)),
            "net_income": float(rng.uniform(1e8, 6e9)),
            "pe": float(rng.uniform(8, 90)),
        })

    close = pd.DataFrame(closes)
    volume = pd.DataFrame(volumes)
    meta_df = pd.DataFrame(meta).set_index("ticker")

    b = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.008, days)))
    bench = pd.Series(b, index=idx)
    return close, volume, meta_df, bench, 13.4
