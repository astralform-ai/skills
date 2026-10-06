---
name: pe-deal-review
description: "Run a private-equity deal through screening, diligence, unit economics, returns and an IC memo. Use when triaging inbound deal flow (CIM, teaser, broker deck), screening a target against the fund's thesis, building a diligence checklist or data-room review plan, prepping diligence meetings, analyzing unit economics or revenue quality (cohorts, NRR/GRR, CAC/LTV, payback, ARR bridge), computing MOIC/IRR/XIRR with a debt schedule for a leveraged deal, drafting an investment committee memo or deal write-up, building a value-creation plan or 100-day plan, or monitoring portfolio company KPIs and covenant headroom. Triggers on 'screen this deal', 'review this CIM', 'should we look at this', 'due diligence checklist', 'diligence questions', 'IC memo', 'deal write-up', 'unit economics', 'cohort analysis', 'LTV/CAC', 'returns analysis', 'what's the IRR', 'MOIC', 'value creation plan', '100-day plan', 'how is the portco performing', 'covenant check'."
display_name: PE Deal Review
version: "1.0.0"
author: Astralform
---

# PE Deal Review

Take a private-equity deal from first look to a written committee recommendation:
screen it against a stated thesis, organize diligence by workstream, test the unit
economics and the returns math, and deliver the memo, the plan, or the monitoring
pack. Every number comes from Python you ran or evidence you cited — this skill
never asserts a figure it did not compute or source.

## What runs where

| Surface | How you reach it | What it does |
|---|---|---|
| `runtime_run_code` | tool call | runs Python in the sandbox — where the analysis happens |
| `runtime.fs.write_file` / `runtime.fs.read_file` | inside that code (`import runtime`) | sandbox files; never `open()` into `/workspace/outputs/` |
| `runtime.proc.exec(cmd, timeout=…)` | inside that code | runs a shell command; returns `{ok, exit_code, stdout, stderr}` and never raises — check `exit_code` on every call |
| `export_file` | tool call | publishes a `/workspace/outputs/` file to the user |

`{baseDir}/scripts/returns.py` is deployed into the sandbox with the skill. It is
stdlib-only, so it runs on the baked `python3` with no install:

```python
import json, runtime
runtime.fs.write_file("/workspace/deal.json", json.dumps(spec))
r = runtime.proc.exec("python3 {baseDir}/scripts/returns.py /workspace/deal.json --json", timeout=120)
if r["exit_code"] != 0:
    raise RuntimeError(r["stderr"])          # exit 2 = bad input, 1 = a check failed
result = json.loads(r["stdout"])
```

stdout streams live, so do not print `r["stdout"]` again — read `result`. Write
memo/checklist deliverables with `runtime.fs.write_file` (bytes for `.docx`) and
hand them over with the `export_file` tool.

## Boundaries

- **LBO workbooks are not built here.** A full 3-statement LBO model with sources &
  uses, purchase accounting and live formulas is `financial-modeling`'s job — load
  it when the IC wants a spreadsheet to drive. This skill sizes the deal, computes
  returns from explicit assumptions, and frames the decision in writing.
- **Market data** comes from `yfinance` when a listed comparable is needed; **PDFs**
  in the data room are read with the `pdf` skill; **styled decks** are
  `ppt-generation`; **file delivery** is the `export` skill.
- **Outputs are staged for the investment committee, not decisions.** Never present
  a screen, memo, or return as a recommendation from the firm, an approval, or
  investment advice. The human committee decides; you prepare the paper.

## The review, in order

0. **Fix the mandate.** Ask for the fund's thesis and criteria before the first
   screen — size band, sector, geography, structure, EBITDA range, control/rollover
   expectation. Write them down once and reuse them; a per-deal standard is how a
   deal sneaks past the mandate. If the user has no thesis, derive tests from what
   they said they like, and label them as yours.
1. **Screen** (Section 1).
2. **Diligence** (Section 2, full checklist in
   `{baseDir}/references/screening-and-diligence.md`).
3. **Unit economics** (Section 3, formulas in
   `{baseDir}/references/unit-economics.md`).
4. **Returns** (Section 4, calculator in `{baseDir}/scripts/returns.py`).
5. **Write the memo, the plan** (Section 5,
   `{baseDir}/references/ic-memo-and-monitoring.md`).
6. **Monitor the portfolio** when the deal is owned (Section 6, same reference).

## 1. Screen against a stated thesis

Do not summarize the CIM back to the user. Extract the facts, then test them.

Facts to pull, in this order: what the company sells and to whom; revenue, EBITDA,
margin and growth with the periods stated; deal type (platform, add-on, recap,
minority, carve-out); asking price and multiple; seller motivation; whether
management rolls; customer concentration; obvious red flags. If a number is
missing or inconsistent between pages, flag it — do not silently use the friendlier
one.

Then convert the thesis into **falsifiable tests** (threshold + data source) and
apply **disqualifiers before merits**. A deal that trips a disqualifier is a hard
pass regardless of the upside; say so in one line and stop. Score the consistent
scorecard — same dimensions, same weights, every deal — and give one of exactly
three verdicts: **Pass**, **Further diligence** (with what must be seen and by
when), or **Hard pass** (with the single reason). Everything above is in the
reference, including the scorecard and the disqualifier list.

Output a one-page screening memo: verdict, criteria table (target / actual / pass),
bull case, bear case, and the questions for a first call.

## 2. Diligence

Organize by workstream — commercial, financial, legal, operational, technical
(plus sector-specific). Every checklist item carries **the question it answers** and
**the evidence that closes it**; an item marked complete with no evidence is wrong,
leave it "in review". The reference holds the full per-item tables and the sector
additions.

Red flags get a severity (deal-breaker / significant / manageable), an owner, and a
valuation-or-terms impact. Escalate a deal-breaker the same day; significant within
48 hours. Suspicion patterns worth acting on: the seller stalls on one specific
request, and the same figure appears differently in two documents.

The checklist is a deliverable: a `.md` table or `.docx` with status per item,
grouped by workstream, plus a red-flag summary. Update it as diligence moves.

## 3. Unit economics

Revenue quality before headline multiples. Ask for customer- or cohort-level data;
if only aggregates exist, derive what you can and say what is unproven.

- Build the **ARR bridge** (opening → new → expansion → contraction → churn →
  closing) and report **GRR, NDR and logo churn together** never NDR alone.
- Build the **cohort matrix** — absolute and indexed — and compare the newest vintage
  to the oldest. A newer cohort retaining worse is a red flag even while total
  revenue grows.
- Segment **CAC** (enterprise / mid-market / SMB, fully loaded S&M) before any LTV
  ratio; blended CAC subsidizes an expensive motion with a cheap one.
- State payback in months — it is the financing requirement, and it needs the
  fewest assumptions.
- Separate **accounting from cash** economics: deferred revenue, capitalized S&M,
  stock comp, working capital, capex vs opex, deferred consideration.

Benchmarks (Rule of 40, magic number, NDR/GRR, LTV:CAC, payback) and the waterfall
from revenue to contribution margin to EBITDA are in the reference. A metric outside
the band needs an explanation, not exclusion — and one distorted period never gets
annualized.

## 4. Returns

Write the assumptions into a JSON spec exactly as the script's docstring defines
them, then run it. **Do not state an IRR you did not compute here.**

Conventions the script enforces (they are what make a returns number comparable):

- Cash flows are **dated**: entry outflow at the entry date, exit inflow at the exit
  date, plus any interim distributions. IRR is XIRR over those dates.
- Interest is charged on **opening** balances (non-circular); mandatory amortization
  is a % of **original face**; the cash sweep runs after amortization, senior to
  junior, never below zero cash.
- The equity check fills the gap: uses (EV + fees) − debt raised.
- The script prints the operating and per-tranche debt schedule it used, the entry
  metrics (leverage, year-1 coverage), MOIC, XIRR, the annual-compounding IRR, the
  cash-flow dates, an attribution of the equity gain (EBITDA growth / multiple /
  debt paydown / fees and distributions), and three sensitivity grids —
  entry×exit multiple, exit multiple×hold, and leverage×exit multiple.

Report the entry metrics alongside the return: a 30% IRR with 1.1x year-1 coverage
is a financing risk, not a result. A **base case that needs multiple expansion must
say so**; a "downside" that still assumes the company hits budget is a base case
wearing a label — set the downside by breaking a named driver (a customer, a price
rise, a product), not by nudging the exit multiple.

Run the sensitivity grid and quote it, rather than claiming robustness. If the debt
schedule reports a funding gap or a negative cash balance, that is an input error to
fix in the assumptions — say so; never present it as a finding.

## 5. IC memo, checklist, value-creation plan

The memo skeleton, section content rules, the risk table, the returns summary, and
the conditions-precedent list are in
`{baseDir}/references/ic-memo-and-monitoring.md`. Format: `.docx` via python-docx
(baked) for the committee, `.md` when the reader wants to comment inline. Build both
with `runtime.fs.write_file`, then export.

Rules that keep a memo credible: recommendation in the first paragraph; every thesis
pillar tied to a diligence test and its result; every risk paired with a mitigant
and an owner; every open diligence item named; every number in the tables recomputed
in Python rather than retyped.

The value-creation plan is an **EBITDA bridge with owners and dates** — revenue,
margin, and strategic levers, plus a 100-day plan. Multiple expansion is an output
of the other levers, never a plan line on its own.

## 6. Portfolio monitoring

Ingest the period's package and produce one board-ready page: an executive
paragraph, a KPI table (actual / budget / variance / prior period / trend / flag),
covenant headroom computed as a level, and questions for management. Flag bands are
green within 5% of plan, amber 5–15% below, red beyond 15% or any covenant breach —
applied consistently, and red escalated immediately with a recommended action.
Measure against the **underwriting case**, not only the budget, and say which one
the KPI is quoted against. Full packet format and the headroom formulas are in the
reference. Charts (matplotlib / plotly) go in the same output directory and ship
with the page.

## Failure modes seen repeatedly

| Symptom | Cause | Fix |
|---|---|---|
| IRR quoted with no cash-flow dates or horizon | IRR is meaningless without timing | state every cash-flow date and the hold period; quote XIRR |
| Headline IRR that assumes entry and exit at different-quality multiples | entry multiple on one comp set, exit on another | use one comp set; if the exit case expands the multiple, say so explicitly |
| Great MOIC, no coverage in year 1 | leverage sized on the return, not the ability to pay | report entry leverage and year-1 interest coverage with every return |
| "Downside" still assumes budget | scenario built by scaling the base | break a named driver (a customer, a price, a product), re-derive, and date it |
| Blended CAC hides churn | one CAC for all segments | segment the CAC, show cohorts, report GRR and NDR together |
| Diligence items "complete", nothing in the folder | status tracked without evidence | the evidence column is mandatory; no evidence means in review |
| Meter-wide screening: every deal passes | criteria changed per deal | one scorecard, same weights, verdict from exactly three words |
| Memo EBITDA bridge doesn't tie | numbers retyped from memory | recompute every table in Python from the same inputs the calculator used |
| Covenant headroom reported as "fine" | level not computed, add-backs unstated | compute headroom as a number; state the LTM EBITDA and its add-backs |

## Delivery

- Name files for the deal and the artefact: `titan-screen-2026-10.md`,
  `titan-ic-memo.docx`, `titan-returns-spec-2026-10.json`, `titan-kpi-2026-09.md`.
- Deliver the analysis **and** its assumptions: the memo or screen, plus the JSON
  spec and the schedule the calculator printed, so a partner can re-run it.
- The reply states what was analysed, the inputs and their sources, the computed
  headline numbers, what is still open or assumed, and that the output is prepared
  for the committee — not a recommendation by the firm.
