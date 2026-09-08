"""Full regression across every path the live system can take."""
import json, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screener import scoring, portfolio, data, render, config
from screener.synthetic import make_synthetic

fails = []
def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("  " + str(extra) if extra else ""))
    if not cond: fails.append(name)

close, volume, meta, bench, vix = make_synthetic()
proxy = data.build_midsmall_proxy(close)
check("proxy builds", len(proxy) == len(close) and proxy.iloc[-1] > 0)

m = scoring.compute_metrics(close, volume, meta, bench, proxy)
check("metrics computed", len(m) > 100, f"{len(m)} names")
check("no NaN in core cols", not m[["price","r12m","ann_vol","sma200","ema21w"]].isna().any().any())

m = scoring.catalyst_scores(m, {"SYN170": {"note": "Order win", "date": "2026-08-20"}}, {"power": 1.0})
check("catalyst applied", m.loc["SYN170.NS","catalyst_bonus"] >= config.CATALYST_BONUS)
check("theme applied", m[m.sector=="Power"]["catalyst_bonus"].min() >= config.THEME_BONUS)

g = scoring.apply_gates(m)
check("mcap band enforced",
      bool(((g[g.g_mcap].market_cap_cr >= config.MIN_MARKET_CAP_CR) &
            (g[g.g_mcap].market_cap_cr <= config.MAX_MARKET_CAP_CR)).all()))
check("RS gate at 15 days",
      bool((g[g.e_rs_high].rs_days_since_high <= 15).all()),
      f"{int(g.e_rs_high.sum())} pass")
check("entry_ok implies eligible", bool((~g.entry_ok | g.eligible).all()))
check("blocked reasons populated", bool((g[~g.entry_ok & g.eligible].entry_blocked_by != "").all()))

sec = scoring.sector_table(g[g.g_mcap & g.g_liquidity])
check("sector breadth in range", bool(((sec.breadth >= 0) & (sec.breadth <= 1)).all()))
sc = scoring.composite(g, sec)
check("ranks unique", sc.dropna(subset=["rank"])["rank"].is_unique)

reg = portfolio.market_regime(bench, 13.0)
check("regime risk-on", reg["state"] == "risk-on")
check("regime unknown handles empty", portfolio.market_regime(pd.Series(dtype=float), None)["state"] == "unknown")
falling = bench * pd.Series(range(len(bench),0,-1), index=bench.index) / len(bench)
check("regime defensive on stress", portfolio.market_regime(falling, 31.0)["state"] == "defensive")

t0 = portfolio.build_target(sc, {}, reg, True)
check("opening book built", len(t0) > 0, f"{len(t0)} names")
check("sector cap honoured", int(t0.sector.value_counts().max()) <= config.MAX_PER_SECTOR)
check("weights sum sane", abs(t0.weight.sum() - (1-config.CASH_BUFFER)*reg["invested"]) < 1e-6)
check("all buys pass entry rules", bool(sc.loc[t0.index, "entry_ok"].all()))

pool = sc[sc.eligible & sc.g_sector].sort_values("composite", ascending=False)
h = {t: {"entry_price": float(sc.loc[t,"price"])*1.4} for t in pool.index[:10]}
t1 = portfolio.build_target(sc, h, reg, False)
check("non-rebalance holds only", set(t1.action.unique()) <= {"hold"})
al, ex = portfolio.check_exits(t1, h, close)
check("stops fire", len(ex) > 0, f"{len(ex)} exits")
check("exit reasons present", all(a.get("kind") and a.get("detail") for a in al))
rf = portfolio.refill(sc, list(t1.drop(index=ex).index), len(ex))
check("refill capped", len(rf) <= config.MAX_REFILLS_PER_RUN, f"{len(rf)}")
check("refills pass entry rules", bool(sc.loc[rf, "entry_ok"].all()) if rf else True)

check("empty universe safe", len(portfolio.build_target(sc.head(0), {}, reg, True)) == 0)

st = data.load_state()
check("state loads", isinstance(st, dict) and "holdings" in st)
open("/tmp/bad.json","w").write("{corrupt")
import shutil; shutil.copy("/tmp/bad.json", os.path.join(data.STATE,"holdings.json"))
check("corrupt state recovers", data.load_state()["holdings"] == {})
open(os.path.join(data.STATE,"holdings.json"),"w").write(
    '{"holdings":{},"last_rebalance":null,"history":[],"buyable":[]}')

for label, mut in [("normal", {}), ("warming", {"warming": True, "pending": 900}),
                   ("no book", {"book": [], "sells": [], "new_signals": [], "candidates": []})]:
    d = json.load(open("docs/data.json")); d.update(mut)
    p = render.render(d, f"/tmp/r_{label}/index.html")
    html = open(p).read()
    check(f"render {label}", len(html) > 15000 and "__" not in html.split("<script>")[0])

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
