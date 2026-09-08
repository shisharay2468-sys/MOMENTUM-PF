# Momentum book

A self-updating momentum screen for NSE equities above ₹1,000 cr, and a
dashboard that tells you what to do about it.

It runs itself every weekday evening, rebuilds every score, and republishes a
single page. You open the page, read the top block, and decide. The system
never places a trade.

---

## What it does each run

1. Pulls the NSE equity list, keeps main-board EQ series only between ₹1,000 cr
   and ₹60,000 cr. SME listings are dropped twice over — once by the series
   filter, once against NSE Emerge's own list.
2. Downloads two years of adjusted daily prices.
3. Reads `catalysts.csv` and `themes.csv`, and scans for episodic pivots.
4. Computes a risk-adjusted momentum score for every name — a 12/6/3-month
   return blend with the most recent month skipped, divided by annualised
   volatility, then combined with trend consistency, acceleration, proximity to
   the 52-week high, and relative strength against the Nifty 500.
5. Applies hard gates: above the 200-DMA, 50-DMA above the 200-DMA, the 200-DMA
   rising, within 25% of the 52-week high, ₹5 cr daily turnover, and at least
   three of five fundamental checks.
6. Applies the entry criteria to anything it might buy: weekly RSI above 65,
   within 12% of the 20-day average, 25% of the 50-day, and 4 ATRs.
7. Ranks sectors by median 6-month return and breadth, and only allows picks
   from the top eight, capped at four names per sector.
8. Checks the market regime and decides how much capital should be deployed.
9. Checks every holding against the exit rules and sells what has broken.
10. Rebuilds the target book — but only trades it on a quarterly rebalance, using
   a buffer so a name is held until it falls outside rank 35.
11. Writes `docs/index.html`.

## Entry and exit rules

**A name is bought only if all of these hold:**

| Rule | Setting | Why |
|---|---|---|
| Weekly RSI above 65 | `WEEKLY_RSI_MIN` | Confirms the trend on the timeframe that matters, not a daily blip |
| Within 12% of the 20-day average | `MAX_EXT_20DMA` | Stops you buying a vertical bar |
| Within 25% of the 50-day average | `MAX_EXT_50DMA` | Same test on a slower clock |
| Within 4 ATRs of the 20-day average | `MAX_EXT_ATR` | The percentage caps alone are unfair to high-volatility names; this normalises them |
| A 50-day relative strength high in the last 15 days | `RS_HIGH_LOOKBACK`, `RS_HIGH_RECENT_DAYS` | The ratio of the stock to the mid-and-smallcap market must be breaking out, not merely rising. A stock can gain 40% and still be losing to its peer group |

Being extended never sells a position you already hold. It only blocks a
fresh entry. A winner that runs is supposed to run.

**A name is sold the same day any of these fire:**

| Rule | Setting |
|---|---|
| 10% below your entry price | `INITIAL_STOP` |
| Weekly close below the 21-week EMA | `EXIT_BELOW_21WEMA` |
| Close below the 200-day average | `EXIT_BELOW_SMA200` |

Exits do not wait for the quarter. When one fires, the system refills the seat
from the top of the buyable list, up to three names per run.

### What relative strength is measured against

The Nifty MidSmallcap 400, if Yahoo carries it. If not, the system builds an
equal-weighted index from the screening universe itself — every name in it
already sits in the ₹1,000–60,000 cr band, so their trimmed average return is
a fair stand-in, and it can never fail to load. The dashboard log says which
one was used.

## Catalysts — the highest-weighted input

Two files sit in the repo root and outrank everything else in the score.

**`catalysts.csv`** is yours to maintain. Columns: `symbol`, `note`, `date`.
Add a row whenever a company announces something the price has not digested —
an order win, a capacity commissioning, a margin inflection, a large contract.
Worth +1.2 to the composite, which typically moves a name 10 to 20 ranks. A row
expires after 120 days.

```csv
symbol,note,date
KAYNES,Rs 1400 cr order book addition,2026-08-20
```

**`exclude.csv`** is a permanent blocklist. Columns: `symbol`, `reason`. Anything
listed never appears in the screen, whatever it scores.

**`themes.csv`** is your sunrise-sector list. Columns: `keyword`, `weight`.
Keywords are matched against each company's sector and industry text. The
shipped list leans toward power, electrical equipment, defence, and electronics
manufacturing; edit it as your view changes.

The system also detects catalysts by itself. An **episodic pivot** — a single
day of 7%+ movement on three times normal volume, which the stock has since
held — is what an order announcement looks like on a chart. That is worth +0.8
and is shown on the dashboard with the date and the volume multiple. It catches
most real announcements and occasionally mislabels a block deal, which is why
your hand-tagged file is weighted higher.

## Setup, once

1. Create a new GitHub repository and push these files to it.
2. In **Settings → Pages**, set the source to *Deploy from a branch*, branch
   `main`, folder `/docs`. Your dashboard will live at
   `https://<your-user>.github.io/<repo>/`.
3. In **Settings → Actions → General**, under *Workflow permissions*, select
   *Read and write permissions*. The job commits each day's output back.
4. Run it once by hand: **Actions → Momentum run → Run workflow**, with
   *Force rebalance* ticked. That builds your opening book of 20.

Metadata loads a few hundred names per run, so the universe fills over three
or four runs. Until it is complete the system will not build an opening book —
the dashboard shows an orange loading banner instead. Once it clears, run the
workflow once with force rebalance to open the book. Later runs take three to
five minutes.

## Running it locally

```bash
pip install -r requirements.txt
python -m screener.run                    # normal run
python -m screener.run --force-rebalance  # rebuild the book now
python -m screener.run --limit 300        # smaller universe, faster
python -m screener.run --offline-test     # synthetic data, no network
open docs/index.html
```

`--offline-test` runs the entire pipeline on generated data. Use it after you
change anything in `config.py` to check nothing broke.

## Tuning it

Everything lives in `screener/config.py`. The parameters most worth revisiting:

| Setting | Default | What moves if you change it |
|---|---|---|
| `MAX_MARKET_CAP_CR` | 60000 | The ceiling. Raise it to let large caps back in. |
| `MIN_ADV_CR` | 5.0 | The real universe constraint. Lower it to reach smaller names, and accept worse fills. |
| `BUFFER_RANK` | 35 | Higher means less churn and staler holdings. |
| `MAX_PER_SECTOR` | 4 | Lower for diversification, higher to lean into a theme. |
| `MAX_DIST_FROM_52W_HIGH` | 0.25 | Tighter buys stronger and more extended; looser buys more pullbacks. |
| `WEEKLY_RSI_MIN` | 65 | Raising it shrinks the buyable list fast. Below 60 you start buying bases that have not broken. |
| `INITIAL_STOP` | 0.10 | The tightest rule in the system. See the note below. |
| `MAX_EXT_20DMA` | 0.12 | Loosen to 0.18 if too few names qualify in a strong tape. |
| `RS_HIGH_RECENT_DAYS` | 15 | The strictest single filter. Widen to 20 if the buyable list is regularly empty. |
| `CATALYST_BONUS` | 1.2 | How far a tagged trigger can lift a name. |
| `WEIGHTING` | equal | Switch to `inverse_vol` to cut drawdown at some cost to return. |
| `W_MOMENTUM_BLOCK` | 0.60 | Raise it to chase raw strength, lower it to favour smooth trends. |

## Reading the dashboard

- **The coloured block at the top** is the only thing that changes how much you
  deploy. Indigo means run the full book. Amber means stay invested but tighten.
  Dark red means cut to half or less.
- **What to do this run** is empty on most days. That is the system working.
- **Risk flags** do not wait for the quarter. A holding below its 200-day
  average or 25% off its high since entry is a sell now.
- **On deck** is who replaces a departing name at the next rebalance.

## Where the data comes from

Prices, market caps, sectors and fundamentals come from Yahoo Finance via
`yfinance`; the universe comes from NSE's own equity list. Both are free and
neither is guaranteed. Yahoo's Indian fundamentals are the weak link — sector
tags are sometimes coarse and growth figures occasionally stale, which is why
the fundamental test is a three-of-five count rather than a hard filter. If you
outgrow it, the paid drop-in is an Indian data vendor for
`data.fetch_meta`; nothing else in the code needs to change.

## A note on the 10% stop

This is the one setting most likely to cost you money. An Indian smallcap with
45% annualised volatility moves 10% against you on noise roughly every few
weeks. On a book of 20 such names you should expect several stops per quarter
that would have recovered.

Two ways to keep the discipline without the churn, both one line in
`config.py`:

- **Widen to volatility.** Set `INITIAL_STOP` to roughly 1.5 times the name's
  20-day ATR as a percentage of price. A 2% daily range implies a 12–15% stop.
- **Make it an opening stop only.** Run 10% for the first month, then let the
  21-week EMA carry it. This is what most trend followers actually do: the
  hard stop protects the entry, the moving average protects the trend.

The system as shipped follows your rule exactly. Watch the exit log in
`state/holdings.json` for a quarter and see how many stops were noise.

## What this does not do

It does not place orders, size positions against your actual capital, account
for taxes or slippage, or know about corporate actions, results dates, or news.
It is a ranked shortlist with a regime switch on top. The decision stays yours.
