---
name: yfinance
description: "Stock market and financial data from Yahoo Finance via the yfinance Python library. Use whenever a user mentions a ticker symbol (AAPL, TSLA, ^GSPC, BTC-USD), asks about a stock/ETF/index/crypto price, wants historical OHLCV data or a price chart, asks about market cap, P/E, dividends, or valuation, wants financial statements (income statement, balance sheet, cash flow), earnings dates or estimates, analyst ratings or price targets, options chains and implied volatility, institutional or insider holdings, ETF holdings, or wants to screen/search for stocks by sector, market cap, or other criteria. Also trigger on phrases like 'how is X trading', 'pull up the financials for X', 'what's the stock price of X', 'compare these tickers', 'is X overvalued', or any request to backtest or analyze market data."
display_name: Yahoo Finance
version: "1.0.0"
author: Astralform
---

# Yahoo Finance (yfinance)

Fetch market data from Yahoo Finance — prices, fundamentals, options, analyst coverage, holdings, and screeners — using the `yfinance` Python library. No API key required.

## When to Use

- User names a ticker and wants a price, quote, or chart
- User wants historical OHLCV data for analysis, backtesting, or plotting
- User asks for fundamentals — financials, margins, valuation multiples, dividends
- User wants earnings dates, analyst estimates, price targets, or upgrades/downgrades
- User asks about options — chains, expirations, implied volatility, open interest
- User wants holders data — institutional, insider, mutual fund, or ETF holdings
- User wants to discover tickers — search by name, screen by sector/market cap, browse a sector
- User compares multiple securities

Covers equities, ETFs, mutual funds, indices (`^GSPC`), futures (`ES=F`), FX (`EURUSD=X`), and crypto (`BTC-USD`).

## Setup

```bash
pip install yfinance
```

Verified against **yfinance 1.5.2**. Requires pandas; `curl_cffi` (a hard dependency) handles Yahoo's bot protection.

**One extra install is needed for `earnings_dates`:**

```bash
pip install lxml
```

`Ticker.earnings_dates` scrapes an HTML table via `pandas.read_html`, which needs `lxml`. yfinance does **not** declare `lxml` as a dependency, so this raises `ImportError: Import lxml failed` on a clean install. Everything else works without it.

## Core Object

```python
import yfinance as yf

t = yf.Ticker("AAPL")
```

Data is cached on the instance — the first `t.info` hits the network, subsequent accesses are free. **Reuse the same `Ticker` object** instead of re-constructing it; building a new one refetches and burns rate-limit budget.

## Historical Prices

Two entry points, with **different defaults** — this is the most common source of bugs.

```python
# Single ticker, full control
df = t.history(period="1y", interval="1d")

# Many tickers at once
df = yf.download(["AAPL", "MSFT"], period="1y", progress=False)
```

| | `Ticker.history()` | `yf.download()` |
|---|---|---|
| `auto_adjust` | `True` | `True` |
| `actions` (Dividends/Splits cols) | `True` | `False` |
| Column shape | flat | **MultiIndex, even for one ticker** |
| Default period | `1mo` | `1mo` |

### Column shape

With `auto_adjust=True` (the default) there is **no `Adj Close` column** — `Close` is already split- and dividend-adjusted:

```
['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
```

Pass `auto_adjust=False` to get raw `Close` plus a separate `Adj Close`.

### The `yf.download` MultiIndex trap

`yf.download` returns a MultiIndex `['Price', 'Ticker']` **even for a single ticker**, so `df["Close"]` yields a DataFrame, not a Series:

```python
yf.download("AAPL", period="5d")            # columns: ('Close','AAPL'), ('High','AAPL'), ...
yf.download("AAPL", period="5d", multi_level_index=False)   # columns: Close, High, Low, Open, Volume
```

Use `multi_level_index=False` for one ticker. For many tickers, `df["Close"]["AAPL"]` works by default; pass `group_by="ticker"` to flip the levels to `('AAPL','Close')`.

### Index

A tz-aware `DatetimeIndex` named `Date`, in the **exchange's** timezone (e.g. `America/New_York`). Comparing it against a naive `datetime` raises. `yf.download()` accepts `ignore_tz=True` to drop the timezone; `history()` has no such parameter — localize your own timestamps or call `df.index.tz_localize(None)`.

### Interval limits

Yahoo caps intraday history. Exceeding a cap returns an **empty DataFrame**, not an error (unless you enable exceptions):

| Interval | Max range | Verified |
|---|---|---|
| `1m` | ~8 days | `8d` OK, `1mo` fails |
| `2m`, `5m`, `15m`, `30m`, `90m` | 60 days | `60d` OK, `2mo` (61d) fails |
| `1h` | 730 days | `2y` OK, `3y` fails |
| `1d`, `5d`, `1wk`, `1mo`, `3mo` | `max` (full history) | `max` → 11,497 daily rows for AAPL |

Valid `period` values: `1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max`. Use `start=`/`end=` (YYYY-MM-DD) for exact windows — `end` is **exclusive**.

`prepost=True` includes pre-market and after-hours bars on intraday intervals.

## Fundamentals

All return DataFrames with **line items as rows** and **period-end dates as columns** (most recent first):

```python
t.income_stmt          # annual, ~5 periods
t.quarterly_income_stmt
t.ttm_income_stmt      # trailing twelve months
t.balance_sheet        # + quarterly_balance_sheet
t.cashflow             # + quarterly_cashflow, ttm_cashflow
```

Row labels are Yahoo's Title Case strings — `Total Revenue`, `Net Income`, `EBITDA`, `Free Cash Flow`, `Capital Expenditure`, `Total Debt`. Label sets vary by company and sector; **check membership before indexing** rather than assuming a row exists:

```python
if "Free Cash Flow" in t.cashflow.index:
    fcf = t.cashflow.loc["Free Cash Flow"]
```

Transpose for time-series work: `t.income_stmt.T`.

## Quotes and Company Info

```python
t.fast_info    # ~20 fields, one cheap call
t.info         # ~184 fields, heavier
```

`fast_info` covers exactly: `currency, dayHigh, dayLow, exchange, fiftyDayAverage, lastPrice, lastVolume, marketCap, open, previousClose, quoteType, regularMarketPreviousClose, shares, tenDayAverageVolume, threeMonthAverageVolume, timezone, twoHundredDayAverage, yearChange, yearHigh, yearLow`.

It does **not** include P/E, dividend yield, sector, or beta — those need `.info`. Prefer `fast_info` for price/volume; reach for `.info` only when you need descriptive or valuation fields.

### `dividendYield` is a percent, not a fraction

```python
yf.Ticker("T").info["dividendYield"]                  # 4.55   <- percent
yf.Ticker("T").info["trailingAnnualDividendYield"]    # 0.0455 <- fraction
```

The two fields use **different units**. Multiplying `dividendYield` by 100 for display is a 100× error. Verified across AAPL (0.32), KO (2.4), T (4.55), VZ (5.98).

## Analyst Coverage

```python
t.analyst_price_targets   # dict: {current, high, low, mean, median}
t.recommendations         # DataFrame: period, strongBuy, buy, hold, sell, strongSell
t.recommendations_summary
t.upgrades_downgrades
t.earnings_estimate       # indexed by period: 0q, +1q, 0y, +1y
t.revenue_estimate
t.eps_trend
t.eps_revisions
t.growth_estimates
t.calendar                # dict: next earnings date, dividend dates
t.earnings_dates          # needs lxml (see Setup)
```

`recommendations` rows are relative months — `0m` is current, `-1m` is one month ago.

## Options

```python
t.options                       # tuple of expiration dates, 'YYYY-MM-DD'
chain = t.option_chain(t.options[0])
chain.calls                     # DataFrame
chain.puts
chain.underlying                # dict
```

Columns: `contractSymbol, lastTradeDate, strike, lastPrice, bid, ask, change, percentChange, volume, openInterest, impliedVolatility, inTheMoney, contractSize, currency`.

`impliedVolatility` is a decimal (0.25 = 25%). Illiquid strikes carry stale `lastPrice` — prefer the bid/ask midpoint.

## Holders and Filings

```python
t.major_holders
t.institutional_holders
t.mutualfund_holders
t.insider_transactions
t.insider_roster_holders
t.insider_purchases
t.sec_filings
t.get_shares_full(start="2024-01-01")
t.sustainability          # ESG scores
```

## ETFs and Mutual Funds

```python
fd = yf.Ticker("SPY").funds_data
fd.description
fd.top_holdings           # DataFrame indexed by Symbol: Name, Holding Percent
fd.sector_weightings
fd.asset_classes
fd.fund_overview
```

`Holding Percent` is a fraction (0.075 = 7.5%). Returns nothing meaningful for individual stocks.

## Corporate Actions

```python
t.dividends       # Series
t.splits
t.actions         # both, combined
t.capital_gains   # funds only
```

## Discovery

### Search and lookup

```python
yf.Search("Apple", max_results=5).quotes      # [{symbol, shortname, ...}]
yf.Search("Apple").news
yf.Lookup("AAPL").get_stock(count=5)          # DataFrame indexed by symbol
```

Use these to resolve a company name to a ticker — do not guess symbols.

### Sectors and industries

```python
tech = yf.Sector("technology")
tech.top_companies      # DataFrame: name, rating, market weight
tech.top_etfs           # dict {symbol: name}
tech.industries         # DataFrame: name, symbol, market weight
yf.Industry("semiconductors").top_performing_companies
```

Sector keys are lowercase slugs: `technology`, `healthcare`, `financial-services`, `consumer-cyclical`, `energy`, `industrials`, `utilities`, `real-estate`, `basic-materials`, `communication-services`, `consumer-defensive`.

### Screening

```python
# Predefined
yf.screen("day_gainers", count=10)
```

Available: `aggressive_small_caps, bond_etfs, conservative_foreign_funds, day_gainers, day_losers, growth_technology_stocks, high_yield_bond, most_actives, most_shorted_stocks, portfolio_anchors, small_cap_gainers, solid_large_growth_funds, solid_midcap_growth_funds, technology_etfs, top_etfs_us, top_mutual_funds, top_performing_etfs, undervalued_growth_stocks, undervalued_large_caps`.

```python
# Custom query — always pass sortField; scope region to what was asked for
q = yf.EquityQuery("and", [
    yf.EquityQuery("eq", ["region", "us"]),
    yf.EquityQuery("gt", ["intradaymarketcap", 100_000_000_000]),
    yf.EquityQuery("eq", ["sector", "Technology"]),
])
res = yf.screen(q, count=25, sortField="intradaymarketcap", sortAsc=False)
[r["symbol"] for r in res["quotes"]]
```

**`sortField` is not optional.** With no sort, Yahoo returns an arbitrary (reverse-alphabetical) slice, not the most relevant matches — the same query unsorted leads with `ZYRX.JK`, `ZS.MX`, `ZPLT.NE`. This is the single biggest cause of nonsense screener output.

**Scope `region` to the geography the request actually implies** — do not hardcode `us`:

| Request | `region` |
|---|---|
| US-oriented ("US large caps", "S&P names") | `us` |
| A named market ("Japanese banks") | that region |
| Genuinely global ("largest chipmakers anywhere") | omit it, then dedup — see below |

Measured on the same tech + `>$100B` query:

| Query | Matches | Leading results |
|---|---|---|
| no region, no sort | 1248 | `ZYRX.JK`, `ZS.MX`, `ZPLT.NE` |
| no region, sorted | 1248 | `AAPLCO.CL`, `NVDACO.CL`, `AAPL.BA` |
| region `us`, sorted | 55 | `AAPL`, `NVDA`, `MSFT`, `TSM`, `AVGO` |

Unscoped screens are **dominated by cross-listings** — `AAPL`, `AAPL.BA`, `AAPL.MX`, and `AAPLCO.CL` are all Apple, which is why the count is 1248 rather than 55. On a global screen, dedup by company (suffix-strip the symbol, or group on `shortName`) instead of reaching for `region` to do it.

Note `region: us` means "listed on a US market", not "US company" — it still returns `TSM`, `SONY`, `SAP`, and `ASML`.

`yf.screen()` returns a dict with `start, count, total, quotes`. Discover filterable fields from an instance:

```python
q.valid_fields    # groups: eq_fields, price, trading, short_interest, valuation,
                  # profitability, leverage, liquidity, income_statement, balance_sheet, cash_flow, esg
q.valid_values    # allowed values for enum fields like sector, region
```

### Market status

```python
m = yf.Market("US")
m.status     # open/closed, session times
m.summary    # index-level snapshot
```

## Multiple Tickers

```python
tk = yf.Tickers("AAPL MSFT NVDA")
tk.tickers                       # dict of Ticker objects, keyed by symbol
tk.tickers["AAPL"].info          # that ticker's company-info dict
```

For prices across many symbols, `yf.download()` is faster — it batches and threads.

## Configuration

```python
yf.set_config(retries=3)                  # retry transient network errors (default 0)
yf.set_config(proxy="http://host:port")
yf.config.debug.hide_exceptions = False   # raise instead of returning empty frames
yf.enable_debug_mode()                    # verbose logging
yf.set_tz_cache_location("/tmp/yf-cache")
```

`raise_errors=True` on `history()` is **deprecated** — use `yf.config.debug.hide_exceptions = False`.

## Error Handling

**yfinance fails silently by default.** Bad tickers do not raise:

```python
bad = yf.Ticker("NOTAREALTICKER")
bad.history(period="5d")   # empty DataFrame, shape (0, 6) — no exception
bad.info                   # dict with a single key: {'trailingPegRatio': None}
```

Always validate:

```python
df = t.history(period="1mo")
if df.empty:
    ...  # bad symbol, delisted, or interval/period exceeded
```

Exceptions in `yfinance.exceptions` (raised only when `hide_exceptions = False`, or from some paths regardless):

| Exception | Meaning |
|---|---|
| `YFRateLimitError` | Too many requests — back off |
| `YFPricesMissingError` | No price data for that symbol/range |
| `YFTickerMissingError` | Symbol not found |
| `YFInvalidPeriodError` | Bad `period` value |
| `YFTzMissingError` | No timezone for symbol (usually delisted) |
| `YFEarningsDateMissing` | No earnings dates published |

### Rate limiting

Yahoo throttles aggressively. If you hit `YFRateLimitError`:

- Reuse `Ticker` objects — property data is instance-cached
- Batch prices with one `yf.download()` instead of N `history()` calls
- Set `yf.set_config(retries=3)`
- Add `progress=False` and avoid tight loops
- Back off and retry after a pause; there is no way to raise the limit

## Presenting Results

- Quote prices with the **currency and as-of timestamp** — `info["currency"]`, and the last index value. Yahoo data is delayed (typically 15 min) and is **not** real-time.
- Round sensibly: prices to 2 decimals, percentages to 1–2, large figures as `$4.99T` / `$1.2B`.
- When comparing tickers, normalize to a common base or show percent change — raw price levels are not comparable.
- State the period and interval you actually pulled.

## Common Mistakes

- **Assuming `Adj Close` exists** — with the default `auto_adjust=True` it does not; `Close` is already adjusted. Using both double-adjusts.
- **`df["Close"]` on a `yf.download()` result for one ticker** — returns a DataFrame, not a Series, because of the forced MultiIndex. Pass `multi_level_index=False`.
- **Treating `info["dividendYield"]` as a fraction** — it is already a percent; a 100× error.
- **Trusting an empty DataFrame as "no data exists"** — it usually means a bad symbol or an exceeded interval limit. Check `.empty` and report which.
- **Requesting `1m` bars over months** — silently returns empty. Respect the interval caps.
- **Screening without `sortField`** — returns an arbitrary reverse-alphabetical slice rather than the top matches.
- **Hardcoding `region: "us"` on a screen the user meant globally** — silently drops every non-US primary listing. Scope region to what was asked; dedup cross-listings separately.
- **Calling `earnings_dates` without `lxml` installed** — raises `ImportError`.
- **Constructing a new `Ticker` per field access** — refetches every time and triggers rate limits.
- **Comparing the tz-aware index to naive datetimes** — raises; use `ignore_tz=True` or localize.
- **Assuming a financial-statement row exists** — line items vary by company; check `in df.index` first.
- Presenting Yahoo's delayed data as live quotes.

## Legal

`yfinance` is **not affiliated with, endorsed by, or vetted by Yahoo, Inc.** It is an open-source tool that uses Yahoo's publicly available APIs, intended for **personal and research use**. Do not present it as a licensed market-data feed, and do not use it for redistribution or commercial data products without reviewing Yahoo's terms of service.
