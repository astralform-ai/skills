# Workflows

The mechanics behind the skeletons. Read the section for the format you are producing; the
data rules in `{baseDir}/references/sourcing-and-figures.md` apply to all of them.

## Earnings analysis

### Gate 0 — is this the latest print?

Do this before anything else, every time. Training-data memory of a quarter is the most
common way a note is confidently wrong.

1. Write today's date into the working notes.
2. `web_search "<company> Q<n> <year> results"` and read the company's own release.
3. `web_search "site:sec.gov <company> 10-Q"` (or browse EDGAR) and open the filing.
4. Confirm four dates agree: release date, 8-K filing date, 10-Q period-of-report date, and
   transcript date. They should sit within days of each other.
5. If the newest release is more than one quarter old, say so and check whether the company
   has reported since — a missing print is usually a search error, occasionally a delay.

Record the four dates in the Sources section. If any of them disagree, resolve it before
writing a sentence.

### 1. Collect, and log what you read

Keep a running manifest as you go, because the Sources section is built from it:

```
- release:      8-K EX-99.1, filed 2026-09-30, Q2 FY26
- filing:       10-Q, period ended 2026-08-31, filed 2026-09-30, EDGAR <link>
- transcript:   IR site, 2026-09-30, call 17:00 ET
- deck:         8-K EX-99.2
- prior guide:  Q1 FY26 release, 2026-06-25
- consensus:    <source>, taken 2026-09-29 pre-print
```

### 2. Reconcile before you analyse

Compute in Python; do not trust the release's own summary table (it is curated):

- Segment revenue summed to consolidated revenue, per period; state the rounding residual.
- Sum of the reported income-statement lines to the subtotals that appear.
- GAAP net income → adjusted net income → both EPS, against the company's bridge.
- Cash flow: operating cash flow versus net income, and the working-capital movements that
  explain the gap.
- Share count: diluted, and what moved it (buyback, issuance, dilution).
- Every number you will print, in a dataframe, with its source column. If a figure cannot be
  traced to a line in a document, it does not go in the note.

### 3. Score the print

Build one table with `Actual / Consensus / Our estimate / Δ / YoY / Guidance`. Then, for each
material gap, run the variance taxonomy:

| Driver | What it looks like | How to verify | Repeatable? |
|---|---|---|---|
| Volume | units/transactions up, price flat | segment volume disclosure, KPI table | usually yes |
| Price | realised price/ASP up, volume flat | price-vs-volume disclosure, MD&A | depends on elasticity |
| Mix | margin moves with no price/volume change | segment mix shift, gross-margin bridge | only if mix shift is structural |
| FX | revenue in constant currency differs from reported | constant-currency reconciliation in the release | no — reverses |
| One-timer | gain, settlement, insurance recovery, tax item | non-GAAP bridge, unusual-item note | no — always back out |
| Timing | a deal or launch slipped a quarter | backlog, deferred revenue, bookings | yes if it lands next period |
| Buyback / share count | EPS beats while net income misses | diluted share count, cash-flow financing | yes, until the buyback stops |
| Tax rate | EPS beat on below-the-line tax | effective tax rate vs guide | no — often reverts |
| Cost timing | margin ahead on deferred spend | operating-expense detail, headcount | watch the next quarter |
| Accounting | a policy change, a reclassification | comparatives restated, 10-Q notes | one-time by nature |

Rules for this step: every driver named in the note has a line in a filing or a quote behind
it; the residual that you cannot attribute is written as "unexplained — hypothesis:", not
smoothed away; and the classification is what tells the reader whether the beat is durable.
A beat that is 80% FX and one-timers is a miss in constant currency, and the note says so in
the verdict line.

### 4. Update estimates and the thesis

- Mechanical carry: the beat's effect on the full year if the run-rate holds, computed, not
  asserted.
- Assumption change: what you are changing beyond the carry — growth, margin, capex, tax,
  share count — and why the evidence supports it.
- Old→new table with a reason per line, and a line for what you deliberately left unchanged.
- Thesis verdict: tested / untouched / strengthened / weakened, with the pillar named.
- Rating and target: maintain, raise or lower, and the bridge (metric × multiple, or DCF
  roll-forward) or the reason the target is unchanged.
- The Street: how your new estimates compare with consensus, and why you differ. If you are
  at consensus, say that too — it tells the reader where the risk sits.

### 5. Write and deliver

Skeleton → `{baseDir}/references/note-skeletons.md` §1. Then run
`python {baseDir}/scripts/check_note.py <note.md>`; fix the findings or dismiss each one
explicitly. Then `export_file`.

## Initiation (first coverage)

Five workstreams. Each has an entry condition; do not start a workstream whose input does not
exist yet.

### 1. Company research → research doc

Entry: ticker and company name resolved. Read the latest 10-K (Items 1, 1A, 7, 8), the last
two 10-Qs, the last two proxies, and two or three transcripts. Produce: what the company
sells, to whom, how it charges; the revenue model by segment with periods and sources;
management and ownership; the industry and the competitive set; the TAM with its methodology
and the distinction between the headline number and the realistic addressable revenue; and
six to twelve falsifiable risks. Every claim carries a number or a source.

### 2. Financial model

Entry: three to five years of statements extracted and reconciled (rank-1 sources). Output
is a **hand-off**: `financial-modeling` builds the workbook. Provide it the extracted
historicals with sources, the driver assumptions, and the scenario definitions. Do not build
a spreadsheet inside this skill.

### 3. Valuation

Entry: the model exists. Produce a *summary*: the methods, their weights, the implied ranges,
the weighted value, the assumption table with sources, a two-way sensitivity grid, the
football field, the price target and the bridge. Cite the model by filename. If the user
wants the workbook driven or changed, hand that back to `financial-modeling`.

### 4. Charts

Entry: the numbers from 1–3 exist. PNGs into `/workspace/outputs/`, each with the caption and
source line from `{baseDir}/references/sourcing-and-figures.md`. The initiation set: revenue
history and forecast, margin history, cash conversion, segment mix, competitive positioning
(share vs growth), valuation football field, the comp table as a chart only if it is
genuinely easier to read than the table.

### 5. Assembly

Entry: everything above. Fill the initiation skeleton (`§2`), embed the charts, and run
`check_note.py`. The valuation section states the target and its method and points at the
model; it does not reproduce it.

## Model update

Trigger → plug → revise → revalue → verdict.

- **Plug**: reported actuals against the prior estimate, line by line, with the delta; plus
  the balance-sheet and cash-flow inputs that moved (cash, debt, share count, capex, working
  capital, tax rate).
- **Separate the carry from the change.** A beat that rolls forward mechanically is not an
  assumption change, and an assumption change is not a beat. Show both.
- **Share count**: recompute diluted shares from the latest filing; a buyback or an issuance
  moves EPS without moving the business.
- **Roll the periods**: when the quarter closes a fiscal year, estimates roll into the next
  year and the NTM window moves. State the roll so the reader is not comparing different
  periods.
- **Verdict**: noise or thesis-changing, and the resulting rating/position action. If nothing
  changed, say it plainly; that is a valid output.

## Earnings preview

- Consensus table with vintage, and our estimate with its delta. Where the two agree
  everywhere, the interesting content is the second derivative: what changes if the guide
  changes.
- Rank the watch list. For each item: the metric, the level that separates bull from bear,
  and where it will be visible (release line, segment table, or call Q&A only).
- Three scenarios, each with the operating condition that produces it and the historical
  reaction of the stock to comparable prints. Use `yfinance` for the price history and the
  options-implied move; do not assert a reaction without the data.
- Pre-announce risk: whether this company has a history of guiding down before the print.

## Morning note

- Scan overnight: pre-market moves across coverage, earnings released since the close, 8-Ks
  filed, M&A, management changes, rating actions elsewhere, macro prints. `web_search` per
  name; do not rely on memory of what was scheduled.
- Time-stamp the note and say when the prices were taken — pre-market moves before the open
  may be gone by it.
- Give a view on every item you include. A summary with no take is not a note.
- Keep it under a page. If nothing material happened, "nothing material overnight; maintaining
  positioning" is the note.

## Catalyst calendar

- Build from three directions: company IR pages (dates as confirmed vs estimated),
  regulator dockets (decision dates, comment periods), and the macro calendar (central-bank
  meetings, data releases with the prior reading).
- Flag estimated dates as estimated. Earnings dates move; re-check the IR page in the week
  before.
- Impact is judged by what it can change, not by how interesting it is: a binary regulatory
  decision is H; a routine conference is L.
- Archive outcomes so the calendar becomes a record of how the stock actually responds.

## Thesis tracker

- A pillar is only a pillar if it has a metric, a level and a date. "Revenue growth >20% by
  Q3 FY26" is a pillar; "strong growth" is a sentiment.
- Log disconfirming data points with the same prominence as confirming ones, and let the
  scorecard trend move to `behind` or `disconfirmed` when it does. A tracker that only ever
  says "on track" is not tracking anything.
- Fix the falsification condition in advance and write it in the header. When it is hit, the
  position decision is mechanical.
- Review on a cadence, not only when something dramatic happens; the most expensive surprises
  are the pillars that quietly stopped progressing.

## Idea generation

- Screens with the `yfinance` skill's `yf.screen` / `EquityQuery` produce **candidates**, never
  conclusions. Always pass `sortField`, and scope `region` to the geography actually implied.
- Name the criteria before running the screen, and record the screen with its parameters in
  the output — an unreproducible screen is an anecdote.
- A thematic sweep maps the value chain, separates pure-plays from diversified exposure, and
  asks which names already price the theme in. Second-order beneficiaries are where the
  unexploited ideas are; crowdedness is a risk, so check coverage count, short interest and
  ownership before pitching.
- Each idea: one-line thesis, the mispricing and what the market is missing, the catalyst,
  the falsifier, and the three to five metrics that matter, against peers.
- A screen hit with no catalyst is a value trap until proven otherwise.
