"""Data acquisition: universe list, price history, per-name metadata.

Everything is cached to disk so a re-run costs nothing if the day's data
is already present.
"""
from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state")
CACHE = os.path.join(STATE, "cache")
os.makedirs(CACHE, exist_ok=True)

NSE_EQUITY_LIST = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME_LIST = "https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
}


# --------------------------------------------------------------- universe
def load_universe() -> pd.DataFrame:
    """Return a frame with columns: symbol, name, yf_ticker.

    Tries NSE's official equity list, falls back to universe.csv in the repo
    root. Keeping a committed fallback means the pipeline never dies because
    NSE changed a header or blocked the runner.
    """
    fallback = os.path.join(ROOT, "universe.csv")
    df = None
    try:
        r = requests.get(NSE_EQUITY_LIST, headers=_HEADERS, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip() for c in df.columns]
        df = df[df["SERIES"].str.strip().isin(config.ALLOWED_SERIES)]
        df = pd.DataFrame({
            "symbol": df["SYMBOL"].str.strip(),
            "name": df["NAME OF COMPANY"].str.strip(),
        })
        df.to_csv(fallback, index=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  NSE list unavailable ({exc}); using committed universe.csv")
        if not os.path.exists(fallback):
            raise SystemExit(
                "No universe available. Download EQUITY_L.csv from NSE and "
                "save it as universe.csv in the repo root."
            ) from exc
        df = pd.read_csv(fallback)

    df = df.drop_duplicates("symbol").reset_index(drop=True)

    if config.EXCLUDE_SME:
        before = len(df)
        df = df[~df["symbol"].isin(_sme_symbols())]
        if before != len(df):
            print(f"  removed {before - len(df)} SME symbols")

    df["yf_ticker"] = df["symbol"] + ".NS"
    return df.reset_index(drop=True)


def _sme_symbols() -> set[str]:
    """Symbols to keep out: NSE Emerge, plus anything in exclude.csv.

    The EQ series filter already removes the SME board, so this is a belt-and
    -braces second pass. exclude.csv is where you park anything else you never
    want the screen to surface — a name with a governance history, say.
    """
    out: set[str] = set()
    try:
        r = requests.get(NSE_SME_LIST, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        sme = pd.read_csv(io.StringIO(r.text))
        sme.columns = [c.strip() for c in sme.columns]
        out |= set(sme["SYMBOL"].astype(str).str.strip())
    except Exception as exc:  # noqa: BLE001
        print(f"  SME list unavailable ({exc}); relying on the EQ series filter")

    path = os.path.join(ROOT, "exclude.csv")
    if os.path.exists(path):
        ex = pd.read_csv(path)
        out |= set(ex["symbol"].astype(str).str.strip().str.upper())
    return out


# ----------------------------------------------------------------- prices
def fetch_prices(tickers: list[str], period: str = "2y") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download adjusted closes and volumes. Returns (close, volume) frames."""
    import yfinance as yf

    closes, volumes = [], []
    total = len(tickers)
    failed_batches = 0
    for i in range(0, total, config.BATCH_SIZE):
        batch = tickers[i:i + config.BATCH_SIZE]
        raw = None
        for attempt in range(config.FETCH_RETRIES):
            try:
                raw = yf.download(
                    batch, period=period, interval="1d",
                    auto_adjust=True, progress=False, threads=True,
                    group_by="column",
                )
                if raw is not None and not raw.empty:
                    break
            except Exception as exc:  # noqa: BLE001
                if attempt == config.FETCH_RETRIES - 1:
                    print(f"  batch at {i} failed after "
                          f"{config.FETCH_RETRIES} tries: {exc}")
                    raw = None
                else:
                    time.sleep(3 * (attempt + 1))  # back off, then retry
        if raw is None or raw.empty:
            failed_batches += 1
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            closes.append(raw["Close"])
            volumes.append(raw["Volume"])
        else:  # single ticker in the batch
            closes.append(raw[["Close"]].rename(columns={"Close": batch[0]}))
            volumes.append(raw[["Volume"]].rename(columns={"Volume": batch[0]}))
        print(f"  prices {min(i + config.BATCH_SIZE, total)}/{total}")

    if not closes:
        raise SystemExit(
            "No price data came back at all. Either the runner has no network "
            "access or Yahoo is rate limiting. Re-run the workflow in an hour; "
            "nothing is broken.")

    close = pd.concat(closes, axis=1).sort_index()
    volume = pd.concat(volumes, axis=1).sort_index()
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]

    # Drop columns that came back all-empty so they never reach the scorer.
    close = close.dropna(axis=1, how="all")
    volume = volume.reindex(columns=close.columns)

    got, want = len(close.columns), total
    print(f"  usable price history for {got} of {want} names")
    if failed_batches:
        print(f"  {failed_batches} batch(es) failed and were skipped")
    if got < want * 0.5:
        print("  WARNING: over half the universe is missing. Treat today's "
              "dashboard as unreliable and re-run later.")
    return close, volume


# --------------------------------------------------------------- metadata
def _atomic_json(path: str, obj) -> None:
    """Write via a temp file and rename, so an interrupted run cannot leave a
    truncated cache that breaks every future run."""
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def _cache_path(name: str) -> str:
    return os.path.join(CACHE, name)


def _cache_fresh(path: str, days: int) -> bool:
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < days * 86400


def fetch_meta(tickers: list[str]) -> pd.DataFrame:
    """Market cap, sector, and the fundamentals used by the quality gate.

    Cached for META_CACHE_DAYS since none of it moves daily.
    """
    import yfinance as yf

    path = _cache_path("meta.json")
    cached: dict = {}
    if os.path.exists(path):
        try:
            with open(path) as fh:
                cached = json.load(fh)
        except Exception:  # noqa: BLE001
            print("  metadata cache unreadable; rebuilding it")
            cached = {}

    fresh = _cache_fresh(path, config.META_CACHE_DAYS)
    missing = [t for t in tickers if t not in cached]
    stale = [] if fresh else [t for t in tickers if t not in missing]
    # Never-seen names first, then the refresh queue. Capped per run.
    queue = missing + stale
    to_pull = queue[:config.META_MAX_PER_RUN]
    if len(queue) > len(to_pull):
        print(f"  {len(queue)} to fetch, doing {len(to_pull)} this run "
              f"({len(queue) - len(to_pull)} carried to the next run)")

    for n, t in enumerate(to_pull, 1):
        if n % config.META_PAUSE_EVERY == 0:
            time.sleep(config.META_PAUSE_SECONDS)
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
            cached[t] = {
                "market_cap_cr": (info.get("marketCap") or 0) / 1e7,
                "sector": info.get("sector") or "Unclassified",
                "industry": info.get("industry") or "Unclassified",
                "name": info.get("shortName") or t.replace(".NS", ""),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "op_cashflow": info.get("operatingCashflow"),
                "net_income": info.get("netIncomeToCommon"),
                "pe": info.get("trailingPE"),
            }
        except Exception:  # noqa: BLE001
            # Record the failure so the name is not retried forever, but keep
            # market cap at zero so it cannot pass the size gate on bad data.
            prev = cached.get(t, {})
            cached[t] = {**prev, "market_cap_cr": prev.get("market_cap_cr", 0),
                         "sector": prev.get("sector", "Unclassified"),
                         "name": prev.get("name", t.replace(".NS", "")),
                         "fetch_failed": True}
        if n % 50 == 0:
            print(f"  meta {n}/{len(to_pull)}")
            _atomic_json(path, cached)  # incremental, so a timeout loses little

    _atomic_json(path, cached)

    rows = []
    for t in tickers:
        d = cached.get(t, {})
        rows.append({"ticker": t, **d})
    df = pd.DataFrame(rows).set_index("ticker")
    # How many names the system has never successfully looked up. Until this
    # reaches zero the universe is incomplete, and the opening book must wait.
    df.attrs["pending"] = len(queue) - len(to_pull)
    df.attrs["known"] = sum(1 for t in tickers if t in cached)
    return df


def fetch_benchmark(period: str = "2y") -> pd.Series:
    """Nifty 500, with a tradable ETF as the fallback. Index history on Yahoo
    is patchier than stock history, and the regime switch is too important to
    let a missing index silently disable it."""
    import yfinance as yf
    for sym in (config.BENCHMARK, config.BENCHMARK_FALLBACK):
        try:
            raw = yf.download(sym, period=period, interval="1d",
                              auto_adjust=True, progress=False)
            if raw is None or raw.empty:
                continue
            col = raw["Close"]
            s = col.iloc[:, 0] if isinstance(col, pd.DataFrame) else col
            s = s.dropna()
            if len(s) > 220:
                if sym != config.BENCHMARK:
                    print(f"  benchmark: using fallback {sym}")
                return s
        except Exception:  # noqa: BLE001
            continue
    print("  WARNING: no benchmark history. Regime switch will read unknown.")
    return pd.Series(dtype=float)


def fetch_rs_benchmark(period: str = "2y") -> pd.Series:
    """Nifty MidSmallcap 400 if Yahoo carries it, otherwise an empty series
    and the caller builds a proxy from the universe."""
    import yfinance as yf
    for sym in config.RS_BENCHMARK_CANDIDATES:
        try:
            raw = yf.download(sym, period=period, interval="1d",
                              auto_adjust=True, progress=False)
            if raw is None or raw.empty:
                continue
            col = raw["Close"]
            s = (col.iloc[:, 0] if isinstance(col, pd.DataFrame) else col).dropna()
            if len(s) > 300:
                print(f"  relative strength measured against {sym}")
                return s
        except Exception:  # noqa: BLE001
            continue
    return pd.Series(dtype=float)


def build_midsmall_proxy(close: pd.DataFrame) -> pd.Series:
    """Equal-weighted index of the screening universe.

    Every name here already sits inside the mid-and-small cap band, so their
    average return is a fair stand-in for the Nifty MidSmallcap 400 — and it
    is derived from data already in hand, so it cannot fail to load.
    """
    rets = close.pct_change()
    # Trim the extremes each day so one 20% mover cannot define the market.
    avg = rets.apply(lambda r: r.dropna().clip(r.quantile(0.02), r.quantile(0.98)).mean(),
                     axis=1)
    return (1 + avg.fillna(0)).cumprod() * 100


def fetch_vix() -> float | None:
    import yfinance as yf
    try:
        raw = yf.download(config.VIX, period="1mo", interval="1d",
                          auto_adjust=True, progress=False)
        col = raw["Close"]
        s = col.iloc[:, 0] if isinstance(col, pd.DataFrame) else col
        return float(s.dropna().iloc[-1])
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ state
DEFAULT_STATE = {"holdings": {}, "last_rebalance": None, "history": [],
                 "buyable": []}


def load_state() -> dict:
    """A corrupt state file must not stop the run. Fall back to empty and say so."""
    path = os.path.join(STATE, "holdings.json")
    if not os.path.exists(path):
        return dict(DEFAULT_STATE)
    try:
        with open(path) as fh:
            state = json.load(fh)
        if not isinstance(state, dict):
            raise ValueError("state is not an object")
        return {**DEFAULT_STATE, **state}
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: state file unreadable ({exc}). Starting from empty.")
        return dict(DEFAULT_STATE)


def save_state(state: dict) -> None:
    path = os.path.join(STATE, "holdings.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, path)


def today_ist() -> datetime:
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


# ------------------------------------------------- catalysts and themes
def load_catalysts() -> dict:
    """catalysts.csv — the names you have a reason to prioritise.

    Columns: symbol, note, date. Nothing else is required. This file is the
    highest-weighted input in the whole system, because an order win or a
    capacity announcement is information the price has not fully digested.
    """
    path = os.path.join(ROOT, "catalysts.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    out = {}
    for _, r in df.iterrows():
        sym = str(r.get("symbol", "")).strip().upper()
        if not sym:
            continue
        out[sym] = {"note": str(r.get("note", "Catalyst")).strip(),
                    "date": str(r.get("date", "")).strip() or None}
    return out


def load_themes() -> dict:
    """themes.csv — sunrise sectors, matched against sector and industry text.

    Columns: keyword, weight. Weight 1.0 is a full bonus, 0.5 a half.
    """
    path = os.path.join(ROOT, "themes.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return {str(r["keyword"]).strip(): float(r.get("weight", 1.0))
            for _, r in df.iterrows() if str(r.get("keyword", "")).strip()}
