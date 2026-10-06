# Comps — comparable companies and precedent transactions

Relative valuation on live data. The workbook is a small table with strict hygiene,
not a big model — but every multiple must recompute from the table's own inputs.

## Building the universe

- Define the screen first and write it in `Notes`: sector, size band, geography,
  business model. A comp set chosen after seeing the multiples is a story, not a comp.
- 5–10 companies is the useful range; fewer is anecdote, more is noise.
- Precedent transactions: announce date, deal size, acquirer/target, and the
  announced transaction EV/EBITDA — do not mix LTM and forward multiples across the
  same statistics block without labeling.

## Data per company

| Column | Source rule |
|---|---|
| Share price, FDSO, market cap | spot price for trading comps, with an as-of date in the header |
| Net debt (+ minorities + preferred − associates/investments) | latest reported balance sheet |
| EV | `= market cap + net debt` — a formula, never a quoted number |
| LTM revenue / EBITDA / EBIT / net income | last four reported quarters, or the last fiscal year, stated |
| Forward metrics | consensus or your own estimate — say which, and from where |

Data sources on this platform, in order: an attached file or the user's data → a
configured data connector → the `yfinance` skill for listed companies (fundamentals
and prices, no key needed) → `web_read` on filings and IR pages. Every input keeps a
cell comment naming the source and the as-of date.

**Calendarization:** companies with different fiscal year ends must be aligned to the
same LTM window before multiples are compared. A December- and a June-year-end company
put side by side without alignment is a defect, not a simplification.

## Table structure

Two blocks, same company order in both:

1. **Operating metrics** — company, revenue, growth, gross profit/margin, EBITDA/margin.
2. **Valuation** — market cap, EV, EV/revenue, EV/EBITDA, P/E.

Rules:

- Percentages to 1 decimal, multiples to 1 decimal (`12.3x`), currency with no decimals
  and a thousands separator.
- Multiples are formulas referencing the block above: if revenue is in `C7`, then
  EV/revenue is `=<EV>!D7/C7`. Never type a multiple.
- Statistics block under each block, with a blank row for separation: max, 75th
  percentile, median, 25th percentile, min — `=MAX(...)`, `=QUARTILE(...,3)`,
  `=MEDIAN(...)`, `=QUARTILE(...,1)`, `=MIN(...)`.
- Statistics only on comparable ratios (margins, growth, multiples) — **never** on
  absolute size (revenue, EBITDA, market cap), where they say nothing.
- Negative or n.m. multiples (`EV/EBITDA` with negative EBITDA) stay visible as `n.m.`
  and are excluded from the statistics range explicitly — do not let them compute a
  nonsense number that silently drags the median.

## Applying the multiples

```
Target EV    = target metric × selected multiple   (median or 25th–75th range)
Target equity = target EV − target net debt        (same bridge as the DCF reference)
```

- Justify the selected multiple by one line, not by taste: growth-adjusted, margin-adjusted,
  or at the median with the range shown.
- The output is a **range**, not a point. If the range is implausibly wide, the comp set
  or the target's comparability is the finding — report that.

## Checks

- `EV = market cap + net debt` per company (formula identity)
- Every multiple recomputes from its own block's inputs
- No statistics cell references a blank or `n.m.` cell
- Company order identical between blocks (a formula-based check: name cells equal)
- As-of dates present for price and balance-sheet data

## Errors seen repeatedly

1. Market cap from one date and net debt from a different period (mismatched as-of).
2. Forward multiples computed from LTM share counts and reported as "forward EV/EBITDA".
3. Statistics over a range that includes a header cell or a blank, skewing MIN/MAX.
4. A quoted multiple entered as a number "because the source had it" — with no formula
   tying it to the inputs, the table cannot be audited.
5. Precedent transactions averaged into the same statistics block as trading comps —
   control premia make them a different distribution; keep them separate.
6. EV built with book value of debt where the market or face value is available, and
   the choice never stated.
