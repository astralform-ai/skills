---
name: equity-research
description: "Research a public company and write the analyst product: earnings notes, initiation memos, model-update write-ups, sector overviews, morning notes, earnings previews, catalyst calendars, thesis trackers — plus the sourced figures behind them. Use when the user asks to write up quarterly results ('Q3 beat or miss', 'earnings update for NKE', 'analysis of last night's print'), initiate coverage ('write an initiation on AAPL', 'first take on this company'), revise estimates after new guidance ('plug the quarter into my numbers'), refresh a thesis ('is my thesis still intact', 'add this data point'), build a catalyst or earnings calendar, preview a print ('what to watch'), run a sector or industry overview, or mine filings for figures ('pull segment revenue out of the 10-K', 'what did they guide to'). Delivers markdown or .docx notes and matplotlib charts. Valuation workbooks belong to financial-modeling; this skill writes the analysis around them."
display_name: Equity Research
version: "1.0.0"
author: Astralform
---

# Equity Research

Produce the written research artifact — earnings note, initiation, sector overview, morning
note, update memo — where **every number carries a period and a source**, and hand the
spreadsheet work over instead of half-doing it here.

## What this skill owns, and what it hands off

| Ask | Owner |
|---|---|
| Write the note / memo / one-pager / landscape; extract and reconcile the figures | **this skill** |
| DCF, LBO, 3-statement, comps, merger model; anything that must live in Excel | `financial-modeling` |
| Price, market cap, multiples, estimates, revisions, ownership, options-implied move | `yfinance` |
| Text and tables out of a PDF (transcript, deck, old annual report) | `pdf` |
| A styled slide deck with imagery | `ppt-generation` |
| Delivering the finished file and its link | `export` |

Do not re-derive what a call to `yfinance` answers, and do not build a spreadsheet here. In
an initiation, the valuation section is a **summary of a model, with a pointer to it** — not a
model. If the user wants the model, say so and route it to `financial-modeling`.

## What runs where

| Surface | How | Does |
|---|---|---|
| `web_search`, `web_read` | tool call | find and read the release, filing, transcript, IR page |
| `runtime_run_code` | tool call | run Python in the sandbox: reconcile, compute, build files |
| `runtime.fs.write_file` | inside that code (`import runtime`) | write deliverables to `/workspace/outputs/` |
| `export_file` | tool call | publish a `/workspace/outputs/` file to the user |

Baked and ready: `pandas`, `numpy`, `matplotlib`, `python-docx` 1.1.2, `openpyxl`, `jinja2`,
`requests`/`httpx`. Nothing to install. Two consequences that shape every workflow:

- **Retrieval happens with the tools, not inside the script.** Fetch the filing or transcript
  with `web_read`, write the bytes into `/workspace/data/<name>.html` (or `.txt`) with
  `runtime.fs.write_file`, then have the script parse, reconcile and compute over that file.
  `runtime.fs` / `runtime.proc` are available inside code when a step needs the filesystem.
- **No spreadsheet or Word engine exists here.** `openpyxl`/`python-docx` *write* files;
  nothing in the sandbox evaluates a formula or lays out a page. Every number you state — in
  chat, in the note, in a table — is computed in Python. Never quote a result you did not
  compute. Structural checks only (a table's columns sum, old→new deltas tie) — those you can
  and must run.

Deliverables:

```python
import io, runtime
from docx import Document

doc = Document()
doc.add_heading("NKE Q2 FY26 Earnings Update", level=1)
# ... body, tables, embedded charts ...
buf = io.BytesIO(); doc.save(buf)
runtime.fs.write_file("/workspace/outputs/NKE-Q2-FY26-earnings-update.docx", buf.getvalue())
```

Then call `export_file(path="/workspace/outputs/NKE-Q2-FY26-earnings-update.docx",
name="NKE Q2 FY26 Earnings Update.docx")`. Charts are PNGs written the same way
(`import matplotlib; matplotlib.use("Agg")`), and a `.docx` can embed them from bytes.
Never `open()` into `/workspace/outputs/` and never shell-redirect into it — those files
exist to `cat` and are undeliverable. Write markdown inline; use `.docx` when the user wants
a document to circulate.

## Data discipline — the five rules

1. **Stamp the as-of.** Every note carries a date and every price a price-date. "Price:
   $94.20 (as of 2026-10-03 close)". A number without a date is not usable and ages silently.
2. **Every figure carries a period AND a source**: "Q2 FY26 revenue $12.4B, +6% YoY (10-Q
   filed 2026-09-30)". Not "revenue grew strongly". Not "$12.4B" alone. Not "Q2 revenue"
   alone. The source names the document or dataset; the period names the quarter or year.
3. **Never mix GAAP with adjusted.** Report the company's GAAP figure and its non-GAAP figure
   side by side, with the add-backs listed, and compare like with like: adjusted actual
   against adjusted consensus, GAAP against GAAP. Say which basis every EPS is on. A "beat"
   measured on a different basis than the estimate is not a beat. See
   `{baseDir}/references/sourcing-and-figures.md`.
4. **Consensus has a vintage.** Use the pre-print consensus, and say whose and as-of when.
   Never use a post-earnings estimate to score an earnings beat — the estimate already
   absorbed the result.
5. **A missing figure is stated, never filled.** If the segment split is not broken out, or
   consensus is unavailable, write "not disclosed" / "no consensus available" and say what
   you would need. No silent estimates, no interpolation presented as data, no projecting a
   metric from a ratio and reporting it as the company's.

Sales-vs-consensus without a numbers check is the most common defect in generated research.
Reconcile before writing: `check_note.py` (`{baseDir}/scripts/check_note.py`) is the first
pass — unsourced and unperiodised numbers, tables with no source line, placeholders, a
missing as-of date. Findings are yours to fix or to consciously dismiss; run it on every
draft.

## Workflow — earnings analysis (post-print note)

Full detail, including the variance-driver taxonomy: `{baseDir}/references/workflows.md`.

1. **Timeliness gate.** Note today's date. Find the *latest* print — `web_search
   "<company> Q<n> <year> results"`, then the 8-K/press release and the 10-Q on EDGAR.
   Confirm the release date is recent and that release, filing and transcript agree on the
   period. A note written off training-data memory of an old quarter is the failure this gate
   exists to stop.
2. **Collect and reconcile.** Earnings release → 10-Q/10-K → transcript (management's own
   words and guidance) → IR deck/supplemental → prior-quarter materials for the prior guide.
   Record document, date, and the line you read. Reconcile: does adjusted EPS tie to GAAP
   net income minus the add-backs the company lists? Does segment revenue sum to total?
3. **Score results vs consensus vs guidance.** Table: actual, consensus, variance ($ and %),
   guide. Compute the variances in Python; do not eyeball.
4. **Explain the variance.** Name the driver of each gap, then classify it — price, volume,
   mix, FX, one-timer, tax, buyback, timing shift. A driver that cannot be attributed to a
   line in the filings is a hypothesis; label it as one.
5. **Revise estimates and the thesis.** Old→new table with the change and the reason per
   line. State whether the quarter changed the thesis, the estimates, the rating, the price
   target — or none of them. "Maintain" is a decision; make it explicitly.
6. **Write, check, deliver.** One-line thesis at the top, note skeleton from
   `{baseDir}/references/note-skeletons.md`, `check_note.py`, then `export_file`.

## Workflow — initiation

Full detail: `{baseDir}/references/workflows.md`. Five workstreams, in order, each producing
one artifact:

| # | Workstream | Output |
|---|---|---|
| 1 | Business, industry, competitive position, management, TAM | research doc (markdown) |
| 2 | Financial history + projections | handed to `financial-modeling` |
| 3 | Valuation — DCF / comps / precedent, weighted to a price target | valuation **summary** that cites the model |
| 4 | Charts | PNGs in `/workspace/outputs/` |
| 5 | Assembly | the initiation note (.docx) |

Do not start 3–5 without their inputs. An initiation written before the model exists has a
valuation section that is fiction.

## The lighter formats

Each has a fixed shape in `{baseDir}/references/note-skeletons.md`; the mechanics are in
`{baseDir}/references/workflows.md`.

| Format | Trigger | Delivers | Length |
|---|---|---|---|
| Earnings preview | "what to watch", pre-print | consensus table, ranked metrics, bull/base/bear with the operational condition for each, catalyst list, implied move | 1 page |
| Model update | guidance change, post-print | what changed, old→new estimates, valuation impact, thesis verdict | 1–2 pages |
| Morning note | "morning note", daily | top call, overnight items with our take, today's events, trade ideas | ≤1 page |
| Sector overview | "sector", "industry landscape" | market size/growth with source, value chain, competitive table, valuation context, key debates | 5–30 pages |
| Catalyst calendar | "what's coming up" | dated events by company/sector with impact and positioning | table |
| Thesis tracker | "is the thesis intact" | pillar scorecard, dated update log, falsification condition | running doc |
| Idea generation | "find ideas", screens | candidates + one-pagers; a screen is a candidate list, never a conclusion | 5–10 ideas |

## Writing rules

- **One-line thesis, first.** "[TICKER] — <rating>: <the claim> because <the mechanism>."
  Everything after it is evidence.
- **Lead with the number.** "Revenue beat by $180M (1.5%)" not "strong top line".
- **Quantify every variance.** $ and %, against the named base (consensus, our estimate,
  guidance, prior year). "In line" requires the numbers that make it in line.
- **Separate fact from inference.** Filed figures are facts. Attribution, sequencing and
  forecasts are inferences — phrase them as such ("we estimate", "this implies"). "Management
  will expand margins" is a prediction dressed as a fact.
- **Risks are falsifiable statements with a trigger.** "If gross margin is below 41.5% for two
  consecutive quarters we are wrong on pricing power" — not "competition is a risk".
- **Ratings and targets carry a bridge.** PT $95 (from $92) on FY27E EPS $4.60 × 20.7x. A
  target that moves with no stated bridge is not research.
- **State the units and the currency once per table** and carry them through. `$M` in the
  header, not a silent mix.
- **Estimates are marked.** `E` on estimates, `A` on actuals, in every table and every
  mention. Fiscal-year notation is the company's: NKE "FY26" ends May 2026 — say the
  calendar period once, then use the fiscal label.
- **Cite the primary document.** A figure that exists in the 10-Q is cited to the 10-Q, not to
  an aggregator that repeated it.

## Charts

matplotlib, `Agg` backend, PNG to `/workspace/outputs/`. Rules that apply to all of them:

- Numbered caption above, `Source: <document> <date>` below. No exceptions.
- Y-axis labelled with the unit; X-axis labelled with the period. A bar chart of a currency
  series with no unit is not a chart.
- Same scale across comparable series; a dual axis only when the two series share a driver,
  and then both axes labelled.
- Quarterly progression, margin trend, segment mix, beat/miss vs consensus, estimate
  old-vs-new revision are the five that earn their place in an earnings note. Do not ship a
  chart that only restates a table.
- For a deck of styled slides, use `ppt-generation`; do not hand-build slides here.

## Note skeletons

`{baseDir}/references/note-skeletons.md` — headings and the required content of each section
for the earnings note, initiation, sector overview, preview, model update, morning note,
catalyst calendar and thesis scorecard. Fill the sections; do not paste prose.

## Failure modes seen repeatedly

| Symptom | Cause | Fix |
|---|---|---|
| "Beat" that isn't | consensus pulled after the print, or post-print estimate used | use pre-print consensus, stamp its vintage; re-score |
| Beat on a different basis | adjusted actual vs GAAP consensus (or vice versa) | report both bases; compare like with like |
| Headline number with no period | "revenue of $1.2B" — which quarter, GAAP or not | attach period, basis and source to every figure |
| Chart with no unit or source | axis built from a bare series | label unit + period, add the Source line |
| Variance asserted | "revenue came in ahead" with no $ or % | compute the gap in Python and print both |
| Thesis written as fact | forecast stated in the present tense | label forecasts as ours, with the mechanism |
| Stale quarter analysed | wrote from memory / training data instead of fetching the print | timeliness gate first; verify release+10-Q+transcript dates |
| Segment numbers don't sum | rounding presented as a discrepancy, or wrong period mixed in | reconcile to total in Python; state the rounding |
| Margin bridge double-counts | FX counted in both mix and price | one driver per line item; reconcile to the reported margin |
| Guidance compared to the wrong base | new guide vs our old estimate instead of vs prior guide | show prior guide → new guide → our estimate |
| EPS on the wrong share count | diluted vs basic, or pre-buyback shares | use the diluted count from the same filing |
| Fiscal/calendar collision | "Q4 2026" for a January-year-end company | state the calendar period once, then the fiscal label |
| One-timer treated as run-rate | a gain left in the base | back it out, show the bridge, say so |
| Sources section missing | citations only inline, or none | end every note with documents, dates, links |
| Undeliverable file | `open()` or `>` into `/workspace/outputs/` | rewrite with `runtime.fs.write_file`, export again |

## Delivery

- Filename names the artifact and date: `NKE-Q2-FY26-earnings-note-2026-10-06.docx`,
  `semis-sector-overview-2026-10.md`.
- Reply with: rating and price target (if any), the one-line thesis, the quantified results
  vs consensus vs guidance, the estimate change, and what you could not source. Then the
  export link.
- State the as-of date of the data in the reply, not only in the file.
- This is analysis for a human to review, not investment advice, and not a solicitation.
  Never present a rating or target as a recommendation to transact.
