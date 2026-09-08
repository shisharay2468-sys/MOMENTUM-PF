"""All tunable parameters for the momentum system.

Edit this file to change the system's behaviour. Nothing else needs touching.
"""

# ---------------------------------------------------------------- universe
MIN_MARKET_CAP_CR = 1000.0      # rupees crore
MAX_MARKET_CAP_CR = 60000.0     # above this the momentum edge thins out and
                                # position sizes stop moving the needle
MIN_ADV_CR = 5.0                # 20-day average daily traded value, rupees crore
MIN_PRICE = 20.0                # rupees
MIN_HISTORY_DAYS = 300          # need a full 12m lookback plus buffer

# Main-board only. SME listings (NSE Emerge, BSE SME) have lot-size trading,
# thin books and 5% bands — momentum rules do not survive contact with them.
EXCLUDE_SME = True
ALLOWED_SERIES = ("EQ",)        # excludes SM, ST (SME), BE, BZ (trade-to-trade)

# ------------------------------------------------------------ momentum mix
# Weights inside the raw return blend. Must sum to 1.
W_R12_1 = 0.40                  # 12-month return, skipping the most recent month
W_R6 = 0.35
W_R3 = 0.25

# Composite: risk-adjusted momentum vs. trend-quality block
W_MOMENTUM_BLOCK = 0.60
W_QUALITY_BLOCK = 0.40

# Inside the trend-quality block
W_CONSISTENCY = 0.40            # share of positive months
W_ACCELERATION = 0.20           # 3m annualised beating 12m
W_PROXIMITY = 0.20              # closeness to 52-week high
W_REL_STRENGTH = 0.20           # RS line vs benchmark near its own high

# --------------------------------------------------------- entry criteria
# These apply ONLY to new buys. Existing holdings are never forced out for
# failing them — that is what the exit rules are for.
WEEKLY_RSI_MIN = 65.0           # 14-period RSI on weekly closes
WEEKLY_RSI_MAX = 80.0           # above this the move is overheated, not strong
MAX_EXT_20DMA = 0.12            # price no more than 12% above its 20-day avg
MAX_EXT_50DMA = 0.25            # and no more than 25% above its 50-day avg
MAX_EXT_ATR = 4.0              # and no more than 4 ATRs above the 20-day avg

# Relative strength against the mid-and-smallcap market. The ratio line must
# have made a fresh high recently — a stock can be rising and still be losing
# to its own peer group, and that is exactly what you do not want to own.
RS_HIGH_LOOKBACK = 50           # sessions the RS line must have topped
RS_HIGH_RECENT_DAYS = 15        # and it must have done so this recently

# ----------------------------------------------------------- new listings
# Recent IPOs cannot pass the main screen — they have no 12-month history —
# so they are tracked separately. The test is whether the stock holds above
# the high of its first week of trading, which is the cleanest read on
# whether the listing found real demand or just a pop.
IPO_MAX_AGE_DAYS = 180          # listed within the last six months
IPO_MIN_DAYS = 15               # but with enough trading to judge
IPO_FIRST_WEEK_SESSIONS = 5

# ------------------------------------------------------------- catalysts
# A catalyst is the highest-priority input. Two sources feed it:
#   1. catalysts.csv — names you tag by hand (order wins, capacity, results)
#   2. an automatic episodic-pivot scan on price and volume
CATALYST_BONUS = 1.2            # z-score added for a hand-tagged catalyst
PIVOT_BONUS = 0.8               # z-score added for a detected episodic pivot
THEME_BONUS = 0.8               # z-score added for a sunrise-theme industry
CATALYST_MAX_AGE_DAYS = 120     # a tagged catalyst goes stale after this

# Episodic-pivot detection: a day of exceptional volume and range that the
# stock has since held onto. This is what an order-book announcement looks
# like on a chart.
PIVOT_LOOKBACK = 60             # sessions to scan
PIVOT_VOLUME_MULT = 3.0         # volume vs the 50-day average
PIVOT_MOVE = 0.07               # single-day move
PIVOT_MUST_HOLD = 0.92         # still holding 92% of the pivot day close

# ------------------------------------------------------------- trend gates
MAX_DIST_FROM_52W_HIGH = 0.25   # must trade within 25% of the 52-week high
SMA200_SLOPE_LOOKBACK = 20      # 200-DMA must be higher than N sessions ago

# ------------------------------------------------------------------ sector
TOP_SECTORS = 8                 # only pick from the N strongest sectors
MAX_PER_SECTOR = 4
SECTOR_BONUS = 0.5              # z-score bonus for a top-3 sector with breadth
SECTOR_BONUS_BREADTH = 0.70     # share of sector above its 200-DMA
MIN_SECTOR_MEMBERS = 3          # sectors thinner than this are not ranked

# --------------------------------------------------------------- portfolio
PORTFOLIO_SIZE = 20
BUFFER_RANK = 35                # hold an existing name until it falls past this
MAX_TURNOVER = 8                # max replacements per quarterly rebalance
WEIGHTING = "equal"             # "equal" or "inverse_vol"
MIN_WEIGHT = 0.03
MAX_WEIGHT = 0.08
CASH_BUFFER = 0.05

# ------------------------------------------------------------- risk / exits
# Exits are checked every day and act immediately. They do not wait for the
# quarterly rebalance.
EXIT_BELOW_21WEMA = True        # weekly close below the 21-week EMA
INITIAL_STOP = 0.10             # 10% below entry price
EXIT_BELOW_SMA200 = True        # backstop for anything the above two miss
TRAILING_STOP = 0.0             # 0 disables; 0.25 = exit 25% off the high

# Refill vacancies as they happen rather than waiting for the quarter. With
# a 10% stop the book would otherwise bleed positions between rebalances.
REFILL_ON_EXIT = True
MAX_REFILLS_PER_RUN = 3

# ------------------------------------------------------------------ regime
BENCHMARK = "^CRSLDX"           # Nifty 500
BENCHMARK_FALLBACK = "NIFTYBEES.NS"   # used if the index has no history

# Relative strength is measured against the mid-and-smallcap market, not the
# broad index, because that is the pool these names actually compete in.
# Tried in order; if none has usable history the system builds an equal-weight
# proxy from the screening universe itself, which can never be unavailable.
RS_BENCHMARK_CANDIDATES = ("^NIFTYMIDSML400", "NIFTYMID150.NS", "^NSEMDCP50")
VIX = "^INDIAVIX"
VIX_PANIC = 25.0

# ---------------------------------------------------------------- fetching
BATCH_SIZE = 60                 # tickers per yfinance download call
META_CACHE_DAYS = 7             # re-pull sector / fundamentals weekly

# Metadata is one request per company, so a cold start would take hours and
# invite rate limiting. Instead each run pulls a slice and caches it. The
# system converges over the first three or four runs rather than failing on
# the first, and every run in between still produces a usable dashboard.
META_MAX_PER_RUN = 600
META_PAUSE_EVERY = 50           # short pause after this many, to stay polite
META_PAUSE_SECONDS = 1.5
FETCH_RETRIES = 3

# Quarterly results are a second request per company, so they are pulled only
# for the names that actually reach the dashboard rather than the whole
# market. That keeps the cost to about a hundred requests a run.
QUARTERLY_MAX = 100
QUARTERLY_CACHE_DAYS = 7
