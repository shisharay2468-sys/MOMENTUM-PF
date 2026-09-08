"""Momentum metrics, trend gates, sector overlay and the composite score."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

TRADING_DAYS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}


def _z(s: pd.Series) -> pd.Series:
    """Winsorised z-score. Clipping at 3 sigma stops one 8x name from
    swamping every other component in the composite."""
    s = s.astype(float)
    mu, sd = s.mean(), s.std(ddof=0)
    if not sd or np.isnan(sd):
        return pd.Series(0.0, index=s.index)
    return ((s - mu) / sd).clip(-3, 3)


def weekly_rsi(px: pd.Series, period: int = 14) -> float:
    """Wilder's RSI on weekly closes."""
    wk = px.resample("W-FRI").last().dropna()
    if len(wk) < period + 5:
        return float("nan")
    delta = wk.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def weekly_ema(px: pd.Series, span: int = 21) -> tuple[float, float]:
    """Returns (last weekly close, 21-week EMA)."""
    wk = px.resample("W-FRI").last().dropna()
    if len(wk) < span + 3:
        return float("nan"), float("nan")
    ema = wk.ewm(span=span, adjust=False).mean()
    return float(wk.iloc[-1]), float(ema.iloc[-1])


def atr(px: pd.Series, period: int = 20) -> float:
    """Close-only ATR proxy. Intraday highs and lows are not needed here —
    the extension check only cares about typical daily range."""
    tr = px.diff().abs()
    if len(tr.dropna()) < period:
        return float("nan")
    return float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def episodic_pivot(px: pd.Series, vol: pd.Series) -> dict:
    """Detect the chart signature of a major announcement: one day of
    outsized volume and range that the stock has since held.

    This is a proxy for an order win or a capacity announcement. It catches
    most of them and mislabels the occasional block deal, which is why the
    hand-tagged catalyst file outranks it.
    """
    n = min(config.PIVOT_LOOKBACK, len(px) - 51)
    if n < 5:
        return {"found": False}
    avg_vol = vol.rolling(50).mean()
    rets = px.pct_change()
    last = float(px.iloc[-1])
    best = None
    for i in range(len(px) - n, len(px)):
        v, av = float(vol.iloc[i]), float(avg_vol.iloc[i])
        r = float(rets.iloc[i])
        if not np.isfinite(av) or av <= 0 or not np.isfinite(r):
            continue
        if v >= config.PIVOT_VOLUME_MULT * av and r >= config.PIVOT_MOVE:
            if last >= float(px.iloc[i]) * config.PIVOT_MUST_HOLD:
                cand = {"found": True, "date": px.index[i].strftime("%d %b %Y"),
                        "move": r, "vol_mult": v / av,
                        "days_ago": len(px) - 1 - i}
                if best is None or cand["move"] > best["move"]:
                    best = cand
    return best or {"found": False}


def compute_metrics(close: pd.DataFrame, volume: pd.DataFrame,
                    meta: pd.DataFrame, bench: pd.Series,
                    rs_bench: pd.Series | None = None) -> pd.DataFrame:
    """One row per ticker with every raw measure the system needs."""
    close = close.dropna(axis=1, how="all")
    rows = []

    bench = bench.reindex(close.index).ffill() if len(bench) else None
    if rs_bench is None or not len(rs_bench):
        rs_bench = bench
    else:
        rs_bench = rs_bench.reindex(close.index).ffill()

    for t in close.columns:
        px = close[t].dropna()
        if len(px) < config.MIN_HISTORY_DAYS:
            continue
        vol = volume[t].reindex(px.index).fillna(0) if t in volume else pd.Series(0, index=px.index)

        last = float(px.iloc[-1])
        rets = px.pct_change().dropna()

        d = TRADING_DAYS
        r12_1 = float(px.iloc[-d["1m"]] / px.iloc[-d["12m"]] - 1)
        r6 = float(last / px.iloc[-d["6m"]] - 1)
        r3 = float(last / px.iloc[-d["3m"]] - 1)
        r1 = float(last / px.iloc[-d["1m"]] - 1)
        r12 = float(last / px.iloc[-d["12m"]] - 1)

        ann_vol = float(rets.tail(d["12m"]).std(ddof=0) * np.sqrt(252))
        if ann_vol <= 0.01:
            continue

        raw_blend = (config.W_R12_1 * r12_1 + config.W_R6 * r6 + config.W_R3 * r3)
        risk_adj = raw_blend / ann_vol

        # consistency: share of the last 12 calendar months that were positive
        monthly = px.resample("ME").last().pct_change().dropna().tail(12)
        consistency = float((monthly > 0).mean()) if len(monthly) >= 6 else 0.0

        # acceleration: 3m annualised running ahead of the 12m trend
        acceleration = 1.0 if (r3 * 4) > r12_1 else 0.0

        high52 = float(px.tail(d["12m"]).max())
        proximity = last / high52 if high52 else 0.0

        sma50 = float(px.rolling(50).mean().iloc[-1])
        sma200 = float(px.rolling(200).mean().iloc[-1])
        sma200_prev = float(px.rolling(200).mean().iloc[-1 - config.SMA200_SLOPE_LOOKBACK])

        adv_cr = float((px.tail(20) * vol.tail(20)).mean() / 1e7)

        sma20 = float(px.rolling(20).mean().iloc[-1])
        atr20 = atr(px, 20)
        ext20 = last / sma20 - 1 if sma20 else np.nan
        ext50 = last / sma50 - 1 if sma50 else np.nan
        ext_atr = (last - sma20) / atr20 if atr20 and atr20 > 0 else np.nan

        rsi_w = weekly_rsi(px)
        wk_close, ema21w = weekly_ema(px, 21)
        pivot = episodic_pivot(px, vol)

        # Relative strength line against the mid-and-smallcap market: how
        # close it sits to its own 12-month high, and how long since it last
        # made a 50-day high.
        rs_near_high = 0.0
        rs_days_since_high = 9999
        if rs_bench is not None:
            b = rs_bench.reindex(px.index).ffill().dropna()
            common = px.index.intersection(b.index)
            if len(common) > d["12m"]:
                rs = (px.loc[common] / b.loc[common]).dropna()
                rs_high = float(rs.tail(d["12m"]).max())
                rs_near_high = float(rs.iloc[-1] / rs_high) if rs_high else 0.0

                # Rolling 50-day max of the ratio line. A new high means the
                # value equals that day's rolling max.
                win = config.RS_HIGH_LOOKBACK
                if len(rs) > win:
                    roll = rs.rolling(win).max()
                    at_high = rs >= roll * 0.999   # tolerance for float noise
                    recent = at_high.tail(config.RS_HIGH_RECENT_DAYS * 3)
                    hits = recent[recent].index
                    if len(hits):
                        rs_days_since_high = int(
                            len(rs.loc[hits[-1]:]) - 1)

        m = meta.loc[t] if t in meta.index else {}
        rows.append({
            "ticker": t,
            "symbol": t.replace(".NS", ""),
            "name": m.get("name", t.replace(".NS", "")),
            "sector": m.get("sector", "Unclassified"),
            "industry": m.get("industry", "Unclassified"),
            "market_cap_cr": float(m.get("market_cap_cr") or 0),
            "price": last,
            "r1m": r1, "r3m": r3, "r6m": r6, "r12m": r12, "r12_1": r12_1,
            "ann_vol": ann_vol,
            "risk_adj_mom": risk_adj,
            "consistency": consistency,
            "acceleration": acceleration,
            "proximity": proximity,
            "rs_near_high": rs_near_high,
            "rs_days_since_high": rs_days_since_high,
            "sma20": sma20, "sma50": sma50, "sma200": sma200,
            "atr20": atr20, "ext20": ext20, "ext50": ext50, "ext_atr": ext_atr,
            "weekly_rsi": rsi_w, "weekly_close": wk_close, "ema21w": ema21w,
            "pivot": bool(pivot.get("found")),
            "pivot_date": pivot.get("date"),
            "pivot_move": pivot.get("move"),
            "pivot_vol_mult": pivot.get("vol_mult"),
            "sma200_rising": sma200 > sma200_prev,
            "adv_cr": adv_cr,
            "revenue_growth": m.get("revenue_growth"),
            "earnings_growth": m.get("earnings_growth"),
            "roe": m.get("roe"),
            "debt_to_equity": m.get("debt_to_equity"),
            "op_cashflow": m.get("op_cashflow"),
            "net_income": m.get("net_income"),
            "pe": m.get("pe"),
        })

    return pd.DataFrame(rows).set_index("ticker")


def quality_flags(df: pd.DataFrame) -> pd.Series:
    """Count of the five fundamental checks each name passes.

    Missing data counts as a fail, not a pass — a name with no reported
    numbers should not sneak through on silence.
    """
    checks = pd.DataFrame(index=df.index)
    checks["sales"] = df["revenue_growth"].fillna(-1) > 0.10
    checks["profit"] = df["earnings_growth"].fillna(-1) > df["revenue_growth"].fillna(0)
    checks["roe"] = df["roe"].fillna(-1) > 0.15
    checks["leverage"] = df["debt_to_equity"].fillna(999) < 100  # yf reports as %
    ocf_ratio = df["op_cashflow"].fillna(0) / df["net_income"].replace(0, np.nan)
    checks["cashflow"] = ocf_ratio.fillna(-1) > 0.6
    return checks.sum(axis=1)


def apply_gates(df: pd.DataFrame) -> pd.DataFrame:
    """Attach every gate as a boolean column plus a combined `eligible`."""
    df = df.copy()
    df["g_mcap"] = ((df["market_cap_cr"] >= config.MIN_MARKET_CAP_CR)
                    & (df["market_cap_cr"] <= config.MAX_MARKET_CAP_CR))
    df["g_liquidity"] = df["adv_cr"] >= config.MIN_ADV_CR
    df["g_price"] = df["price"] >= config.MIN_PRICE
    df["g_above_200"] = df["price"] > df["sma200"]
    df["g_above_50"] = df["price"] > df["sma50"]
    df["g_golden"] = df["sma50"] > df["sma200"]
    df["g_slope"] = df["sma200_rising"]
    df["g_near_high"] = df["proximity"] >= (1 - config.MAX_DIST_FROM_52W_HIGH)
    df["quality_score"] = quality_flags(df)
    df["g_quality"] = df["quality_score"] >= 3

    gate_cols = [c for c in df.columns if c.startswith("g_")]
    df["eligible"] = df[gate_cols].all(axis=1)
    df["gates_failed"] = df[gate_cols].apply(
        lambda r: ", ".join(c[2:] for c in gate_cols if not r[c]), axis=1)

    # Entry-only conditions. A name must clear these to be BOUGHT; a name
    # already held is judged by the exit rules instead, so a winner that
    # runs away from its 20-day average is not thrown out for succeeding.
    df["e_rsi"] = ((df["weekly_rsi"].fillna(0) >= config.WEEKLY_RSI_MIN)
                   & (df["weekly_rsi"].fillna(999) <= config.WEEKLY_RSI_MAX))
    df["e_ext20"] = df["ext20"].fillna(9) <= config.MAX_EXT_20DMA
    df["e_ext50"] = df["ext50"].fillna(9) <= config.MAX_EXT_50DMA
    df["e_ext_atr"] = df["ext_atr"].fillna(99) <= config.MAX_EXT_ATR
    df["e_rs_high"] = (df["rs_days_since_high"].fillna(9999)
                       <= config.RS_HIGH_RECENT_DAYS)
    entry_cols = [c for c in df.columns if c.startswith("e_")]
    df["entry_ok"] = df[entry_cols].all(axis=1) & df["eligible"]
    df["entry_blocked_by"] = df[entry_cols].apply(
        lambda r: ", ".join({"e_rsi": "weekly RSI below 65",
                             "e_ext20": "extended from the 20-day",
                             "e_ext50": "extended from the 50-day",
                             "e_ext_atr": "extended in ATR terms",
                             "e_rs_high": "no fresh 50-day relative strength high"}[c]
                            for c in entry_cols if not r[c]), axis=1)
    return df


def catalyst_scores(df: pd.DataFrame, tagged: dict, themes: dict) -> pd.DataFrame:
    """Attach the catalyst inputs that now outrank raw momentum.

    tagged: {symbol: {"note": str, "date": "YYYY-MM-DD"}} from catalysts.csv
    themes: {keyword: weight} matched against sector and industry text
    """
    df = df.copy()
    today = pd.Timestamp.today()

    notes, bonus = [], []
    for t, r in df.iterrows():
        b, parts = 0.0, []
        tag = tagged.get(r["symbol"])
        if tag:
            age = (today - pd.Timestamp(tag["date"])).days if tag.get("date") else 0
            if age <= config.CATALYST_MAX_AGE_DAYS:
                b += config.CATALYST_BONUS
                parts.append(tag.get("note", "Tagged catalyst"))
        if r.get("pivot"):
            b += config.PIVOT_BONUS
            parts.append(f"Volume pivot {r.get('pivot_date')} "
                         f"({(r.get('pivot_move') or 0) * 100:.0f}% on "
                         f"{(r.get('pivot_vol_mult') or 0):.1f}x volume)")
        text = f"{r.get('sector', '')} {r.get('industry', '')}".lower()
        hits = [k for k in themes if k.lower() in text]
        if hits:
            b += config.THEME_BONUS * max(themes[k] for k in hits)
            parts.append(f"Sunrise theme: {hits[0]}")
        bonus.append(b)
        notes.append(" | ".join(parts))

    df["catalyst_bonus"] = bonus
    df["catalyst_note"] = notes
    return df


def sub_scores(df: pd.DataFrame, sectors: pd.DataFrame) -> pd.DataFrame:
    """Three readable 0-100 scores that sit alongside the composite.

    They are percentile ranks within the eligible pool, so 70 means the name
    beats 70% of its peers on that measure. They explain the composite rather
    than feed it — the composite is already built from the raw inputs.
    """
    df = df.copy()
    pool = df[df["eligible"]] if df["eligible"].any() else df

    def pctile(col: pd.Series) -> pd.Series:
        v = col.reindex(pool.index).astype(float)
        if v.notna().sum() < 3:
            return pd.Series(np.nan, index=pool.index)
        return v.rank(pct=True, na_option="keep") * 100

    # Sector score: where this name's sector sits in the sector ranking.
    n_sec = max(len(sectors), 1)
    rank_map = sectors["rank"].to_dict()
    sector_score = pool["sector"].map(
        lambda s: (100 * (n_sec - rank_map[s] + 1) / n_sec) if s in rank_map else np.nan)

    # Earnings score: profit growth and return on equity together.
    earn = pd.concat([pctile(pool["earnings_growth"]), pctile(pool["roe"])],
                     axis=1).mean(axis=1, skipna=True)

    # Growth score: top line, with the momentum of the business itself.
    growth = pd.concat([pctile(pool["revenue_growth"]), pctile(pool["r6m"])],
                       axis=1).mean(axis=1, skipna=True)

    for name, series in (("sector_score", sector_score),
                         ("earnings_score", earn),
                         ("growth_score", growth)):
        df[name] = series.round(0)
    return df


def new_listings(close: pd.DataFrame, volume: pd.DataFrame,
                 meta: pd.DataFrame) -> list[dict]:
    """Mainboard listings from the last six months holding above the high of
    their first week of trading.

    These never reach the main screen — a 12-month lookback does not exist —
    so they are surfaced as their own list to watch, not to buy blind.
    """
    out = []
    for t in close.columns:
        px = close[t].dropna()
        if not (config.IPO_MIN_DAYS <= len(px) <= config.IPO_MAX_AGE_DAYS):
            continue
        m = meta.loc[t] if t in meta.index else {}
        mcap = float(m.get("market_cap_cr") or 0)
        if not (config.MIN_MARKET_CAP_CR <= mcap <= config.MAX_MARKET_CAP_CR):
            continue

        first_week = px.head(config.IPO_FIRST_WEEK_SESSIONS)
        week_high = float(first_week.max())
        last = float(px.iloc[-1])
        if week_high <= 0 or last < week_high:
            continue

        vol = volume[t].reindex(px.index).fillna(0) if t in volume else None
        adv = float((px.tail(20) * vol.tail(20)).mean() / 1e7) if vol is not None else 0.0
        if adv < config.MIN_ADV_CR:
            continue

        out.append({
            "symbol": t.replace(".NS", ""),
            "name": str(m.get("name", t.replace(".NS", "")))[:38],
            "sector": m.get("sector", "Unclassified"),
            "price": last,
            "listed_date": px.index[0].strftime("%d %b %Y"),
            "sessions": len(px),
            "week_high": week_high,
            "above_week_high": last / week_high - 1,
            "since_listing": last / float(px.iloc[0]) - 1,
            "market_cap_cr": mcap,
            "adv_cr": adv,
        })
    out.sort(key=lambda x: x["above_week_high"], reverse=True)
    return out


def sector_table(df: pd.DataFrame) -> pd.DataFrame:
    """Sector strength: median 6m return and breadth above the 200-DMA."""
    g = df.groupby("sector")
    tbl = pd.DataFrame({
        "members": g.size(),
        "median_r6m": g["r6m"].median(),
        "breadth": g.apply(lambda x: float((x["price"] > x["sma200"]).mean()),
                           include_groups=False),
    })
    tbl = tbl[tbl["members"] >= config.MIN_SECTOR_MEMBERS]
    tbl["score"] = _z(tbl["median_r6m"]) + _z(tbl["breadth"])
    tbl = tbl.sort_values("score", ascending=False)
    tbl["rank"] = range(1, len(tbl) + 1)
    return tbl


def composite(df: pd.DataFrame, sectors: pd.DataFrame) -> pd.DataFrame:
    """Blend everything into a single ranked score."""
    df = df.copy()
    pool = df[df["eligible"]].copy()
    if pool.empty:
        df["composite"] = np.nan
        df["rank"] = np.nan
        return df

    mom = _z(pool["risk_adj_mom"])
    qual = (config.W_CONSISTENCY * _z(pool["consistency"])
            + config.W_ACCELERATION * _z(pool["acceleration"])
            + config.W_PROXIMITY * _z(pool["proximity"])
            + config.W_REL_STRENGTH * _z(pool["rs_near_high"]))

    score = config.W_MOMENTUM_BLOCK * mom + config.W_QUALITY_BLOCK * qual

    top3 = set(sectors[sectors["rank"] <= 3].index)
    strong = set(sectors[(sectors["rank"] <= 3)
                         & (sectors["breadth"] >= config.SECTOR_BONUS_BREADTH)].index)
    bonus = pool["sector"].map(lambda s: config.SECTOR_BONUS if s in strong else 0.0)
    # Catalysts and sunrise themes are added on top of the momentum score
    # rather than mixed into it, so a genuine trigger can lift a name several
    # ranks without a merely volatile chart doing the same.
    cat = pool["catalyst_bonus"] if "catalyst_bonus" in pool else 0.0
    score = score + bonus + cat

    pool["composite"] = score
    pool["sector_bonus"] = bonus
    pool["sector_top3"] = pool["sector"].isin(top3)

    allowed = set(sectors[sectors["rank"] <= config.TOP_SECTORS].index)
    pool["g_sector"] = pool["sector"].isin(allowed)

    pool = pool.sort_values("composite", ascending=False)
    pool["rank"] = range(1, len(pool) + 1)

    for col in ["composite", "rank", "sector_bonus", "sector_top3", "g_sector"]:
        df[col] = pool[col]
    df["g_sector"] = df["g_sector"].fillna(False)
    return df
