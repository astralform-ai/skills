# Note skeletons

Structure to fill, not prose to copy. Each heading is required unless marked optional. Rules
that apply to every skeleton:

- Open with the as-of date and the source documents actually read (with dates).
- Every table carries a `Source:` line directly below it, naming the document and its date.
- Every number carries a period; every estimate carries an `E`; every actual carries an `A`.
- Monetary units and currency are declared once per table and never silently change.
- Bracket anything you could not source as `<not disclosed>` and keep it visible.

---

## 1. Earnings note (post-print; 2–8 pages)

Use the short form for a quick reaction, the long form when the print is material.

**Header block** (required, first screen)
- `[COMPANY] ([TICKER]) — [QUARTER] [FY] earnings note`, date.
- Rating (maintain / raise / lower) and current rating; price with price-date; price target
  old → new with the % change; % upside/downside to the current price.
- One-line thesis: rating, the claim, the mechanism.
- Verdict line: `BEAT / INLINE / MISS` on the basis named (adjusted EPS, revenue).

**Results vs consensus vs our estimate** (required, table)
- Columns: `Actual`, `Consensus (source, as-of)`, `Our est.`, `Δ vs cons. ($ and %)`, `YoY`,
  and where the company guides: `Prior guide`, `New guide`.
- Rows: revenue; gross margin; operating margin or EBIT; adjusted EPS; GAAP EPS; the two or
  three sector KPIs that decide the print (see the KPI map in
  `{baseDir}/references/sourcing-and-figures.md`).
- Below the table: the basis of each EPS (GAAP / adjusted, with add-backs), stated once.

**What drove the variance** (required, one subsection per material deviation)
- The attributed driver, then its classification: price / volume / mix / FX / one-timer /
  tax / buyback / timing.
- The evidence: the line in the filing or the management quote that supports the attribution.
- The *un*xplained residual, if any, labelled as a hypothesis rather than a finding.

**Segment and KPI detail** (required when the company reports segments)
- Segment revenue and margin, actual vs prior year vs our estimate; segment mix shift; and
  the reconciliation that segments sum to the consolidated total (state the rounding).
- Sector KPI table with the period and the comparison base.

**Guidance** (required; state "no guidance given" if that is the fact)
- Prior guide → new guide → our estimate, per line, with the implied change in the second
  half / rest of year. What the new guide assumes that we do not.

**Estimate changes** (required, table)
- Rows: revenue, growth, gross margin, EBITDA/EBIT, margin, adjusted EPS, and any KPI the
  thesis rests on. Columns: `Old`, `New`, `Δ`, `Reason`. One line per change; "no change" is
  a valid reason when the print was clean.

**Thesis impact** (required)
- Which pillar of the thesis the print tested, and whether it strengthened, weakened or
  neutralised it. If nothing in the print touched the thesis, say that.
- Rating and price target: what they are, and the bridge from the old target to the new one
  (method, multiple, metric) or the statement that the target is unchanged and why.

**Risks to the call** (required)
- The falsifiable statements that would make this note wrong, each with the metric and the
  level that would trigger a change. Not a generic risk list.

**Sources** (required)
- Every document read: release, 8-K, 10-Q/10-K (with filing date and EDGAR link), transcript
  (with date), deck/supplemental, prior-quarter materials, consensus source with its vintage.

---

## 2. Initiation (first coverage; 20–50 pages)

**Page 1 — investment summary** (required; the page that must stand alone)
- Rating, price + price-date, price target + % upside, and the valuation method behind the
  target in one line *with a pointer to the model* (not the model).
- One-line thesis; three to five supporting bullets, each with a number.
- Snapshot table: market cap, EV, net debt/EBITDA, NTM P/E and EV/EBITDA, revenue growth,
  margin, FCF yield — each with the as-of date and the peer median beside it.
- Key risks in brief; the next catalyst with its date.

**Investment thesis** (required)
- The claim and why the market is mispricing it: what is in the price, what we think is not,
  and the evidence. Three to five pillars; each pillar names the metric that proves it and
  the quarter in which it becomes observable.

**Risks** (required)
- Six to twelve risks across company, industry, financial and governance categories. Each is
  a falsifiable statement with a metric, a level and a time window.
- The strongest bear case stated in its own words, then our answer.

**Company 101** (required)
- What it sells, to whom, how it charges, and the revenue model by segment with the last
  reported figures and source.
- History that explains today's structure (2–3 pages max; no chronology for its own sake).
- Management and ownership: who runs it, tenure, compensation shape, insider ownership and
  recent transactions (proxy), and the public float picture.
- Customers, distribution, concentration and contract structure (10-K Item 1 / segment note).

**Industry and competitive position** (required)
- Market size and growth with the source and the methodology; separate a headline TAM from
  the realistically addressable revenue, and say which one you are using.
- Value chain and where profit accrues; barriers to entry; the structure question (fragmented
  vs consolidated) with top-5 share.
- Competitor table: revenue, growth, margin, share, differentiator — one line each for the
  5–10 that matter, with the period and the source.
- Who is gaining and losing share, and the evidence.

**Financial analysis** (required)
- Historical: 3–5 years of revenue, margins, cash conversion, ROIC, leverage, with the
  periods stated and the source (10-K). Call out any accounting choice that materially
  changes comparability.
- Forward: the driver tree behind the projections, then the projections table. The projection
  logic lives in the model — cite it.
- Scenarios: bull / base / bear with the operating condition that distinguishes each.

**Valuation summary** (required; summary only)
- Method, weight, implied value range, weighted value — a table. Assumptions listed
  (growth, margin, WACC, terminal growth, multiples) with the source of each.
- Sensitivity as a two-way grid over the two assumptions that move the answer.
- Football field of the methods against the current price, and the bridge to the price
  target. **Hand anything that needs a live, editable workbook to `financial-modeling`** and
  cite the model you used.

**Financial statements appendix** (optional but expected)
- Income statement, balance sheet, cash flow, and the ratios block, in the units declared.

**Sources and disclosures** (required)
- Filings with dates and links; industry sources with dates and methodology; consensus source
  and vintage; the analyst-side disclosure statement.

---

## 3. Sector overview (5–30 pages)

- **Scope and definition.** Sector and subsector boundaries, the universe, what is in and out
  (private players? global?), and the purpose (client piece, thematic, internal).
- **Market size and growth.** TAM and the realistic addressable market, historical CAGR,
  forecast CAGR with the assumptions, segmentation by product/geography/end market. Every
  size figure carries the source, its date and its methodology.
- **Industry structure.** Fragmented vs consolidated with top-5 share; value chain map and
  where value accrues; business model types; barriers to entry (capital, regulatory,
  technical, network).
- **Trends and drivers.** Three to five secular tailwinds, then headwinds, then regulatory and
  technology disruption vectors. Each trend names the metric that measures it.
- **Competitive landscape table.** Company, revenue, growth, EBITDA margin, share, key
  differentiator, valuation snapshot (P/E, EV/EBITDA, EV/sales) — with the period and source.
  Two to three sentences of profile per company, not a re-listing of the table.
- **Valuation context.** Sector multiple today vs its own history vs the market; the
  premium/discount drivers; recent transaction multiples with dates.
- **Investment implications.** Where the risk/reward sits, how to express the theme (pure-play
  vs diversified), and the key bull-vs-bear debates with both sides argued honestly.
- **Catalysts that could change the narrative**, each dated.
- **Aging warning.** Date the piece on page one and name the data whose next release dates it.

---

## 4. Earnings preview (1 page, before the print)

- Company, quarter, earnings date and time, pre-/post-market; the prior quarter's print date.
- Consensus table: revenue, EPS (basis stated), the sector KPIs — with source and vintage, and
  our estimate beside it with the delta.
- What to watch, ranked: the three to five metrics that will decide the stock, each with the
  level that separates bull from bear.
- Scenarios: bull / base / bear with revenue, EPS, the key driver, the operational condition
  that produces it, and the historical stock reaction to comparable prints.
- The narrative items: guidance change, strategic update, capital return, M&A posture.
- Trading setup: price, recent performance, options-implied move vs the scenarios.

---

## 5. Model update (1–2 pages, after an event)

- Trigger: which print, guide, transaction or macro change, dated.
- `What changed` table: line item, prior estimate, actual/new input, delta, note.
- Balance-sheet and cash-flow inputs that moved: cash, debt, share count, capex, working
  capital — with source.
- Forward estimate revision: old vs new for the current and next year, with the per-line
  reason. Distinguish the mechanical carry of a beat from a genuine assumption change.
- Valuation impact: method, prior value, updated value, delta; the price target old → new and
  the bridge.
- Verdict: noise or thesis-changing, and the resulting action on rating and position.
- Statement of what did **not** change.

---

## 6. Morning note (≤1 page)

- Header: date, time written, coverage.
- **Top call** — the one thing that matters today, in two or three sentences, with the number
  that makes it matter.
- Overnight / pre-market: one line per name that moved, each with the figure and our take
  (not just the news).
- Today's events with times: earnings, calls, data releases, conferences.
- Trade ideas, if any: direction, name, one-sentence thesis, catalyst, and what would make it
  wrong.
- "Nothing material overnight; maintaining positioning" is a complete note — do not pad it.

---

## 7. Catalyst calendar (table)

Columns: `Date`, `Event`, `Company/Sector`, `Type` (earnings / corporate / industry / macro),
`Impact (H/M/L)`, `Our positioning`, `Notes`.
- Earnings dates with pre-/post-market and whether the date is confirmed by the IR page or
  only estimated.
- Corporate: product launches, regulatory decisions (with the decision body and date),
  lock-ups, debt maturities, investor days, management transitions.
- Industry: conferences with presenting companies, monthly data releases with the publication
  date and the prior reading.
- Macro: central-bank meetings and data releases that move the sector.
- Archive each past entry with the actual outcome, so the calendar becomes pattern evidence.

---

## 8. Thesis scorecard (running doc)

- Header: ticker, direction (long/short), date opened, current price + price-date, target,
  the falsification condition that would end the position.
- One-line thesis and the three to five pillars.
- Scorecard table: `Pillar` | `Original expectation (metric + level + date)` | `Current status`
  | `Trend` (on track / ahead / behind / disconfirmed). Trend requires the measured value.
- Update log: `Date` | `Data point (with source)` | `Pillar affected` | `Impact` | `Action` |
  `Conviction`. Disconfirming evidence is logged as prominently as confirming evidence.
- Open questions that the next data point will resolve, each with the date it resolves.
