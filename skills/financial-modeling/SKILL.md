---
name: financial-modeling
description: "Build or audit an Excel financial model and deliver it as a working .xlsx — 3-statement, DCF, LBO, merger/accretion-dilution, comps and valuation. Use when the user asks to build, model, forecast, or value a company; run a DCF, LBO, merger model, or comps; build a 3-statement model; run scenarios, sensitivities, or stress cases; or to audit, review, check, or debug an existing spreadsheet model ('why doesn't it balance', 'find the hardcodes'). Also trigger on 'build me a model', 'valuation', 'WACC', 'terminal value', 'sources and uses', 'IRR/MOIC', 'accretion dilution'."
display_name: Financial Modeling
version: "1.0.0"
author: Astralform
---

# Financial Modeling

Build the model as a Python script, save the workbook with `openpyxl`, validate it,
and deliver a `.xlsx` the user can open and drive from its own inputs.

## What runs where

| Surface | How you reach it | What it does |
|---|---|---|
| `runtime_run_code` | tool call | runs Python in the sandbox — where the model is built |
| `runtime.fs.*`, `runtime.proc.*` | inside that code (`import runtime`) | sandbox files and processes |
| `export_file` | tool call | publishes a `/workspace/outputs/` file to the user |

`openpyxl` 3.1.5 and pandas are baked into the image — no install. Write deliverables
through `runtime.fs.write_file`, never `open()` into `/workspace/outputs/`:

```python
import io, runtime
from openpyxl import Workbook

wb = Workbook()
# ... build every cell ...
buf = io.BytesIO(); wb.save(buf)
runtime.fs.write_file("/workspace/outputs/titan-dcf.xlsx", buf.getvalue())
```

Then call `export_file(path="/workspace/outputs/titan-dcf.xlsx", name="Titan DCF.xlsx")`.

Keep the builder script itself under `/workspace/model.py` (or a `build/` dir) so a
correction is an edit-and-rerun, not a rebuild from scratch. Regenerate the workbook
from the script every time — never patch the delivered file in place.

## The one rule: formulas, not numbers

Every derived cell — margin, growth rate, multiple, subtotal, check — is an Excel
formula that references input cells. **The only literal numbers in the workbook are
inputs**, and every input carries a cell comment naming its source and period.

```python
ws["C7"] = 1_250_000_000          # input → blue font, comment = source
ws["F7"] = "=E7/C7"               # derived → black formula, never a pre-computed float
```

A hardcoded margin is a silent bug: the workbook stops responding when an input
changes. This is the single most common defect in generated models, and the validator
(`{baseDir}/scripts/validate_model.py`) exists to catch it — run it before delivery.

## The recalc gap — read before you report any number

The sandbox has **no Excel engine**. openpyxl writes formulas the user's Excel will
evaluate; nothing here can read back what they compute. Two consequences:

1. **Numbers you state in chat or in a memo are Python numbers.** Mirror the model
   arithmetic in pandas/numpy inside the same script and report those. Never invent a
   result "the workbook will show" that you did not actually compute.
2. **Checks live in the workbook as formulas** so they evaluate on the user's machine
   (see Checks below), while your own verification is structural: formulas present,
   no stray hardcodes, no error literals, references valid.

Say this once, plainly, if the user asks about exact outputs: the workbook recomputes
when opened; the values quoted in chat come from the same arithmetic run in Python.

## Architecture

One sheet per job, in this order — anything else makes the model hard to audit:

| Sheet | Holds |
|---|---|
| `Inputs` | every assumption and raw figure, one row each, with source comments |
| `Calc` / statement sheets | formulas only (`IS`, `BS`, `CF`, `Debt`, `Schedules`) |
| `Valuation` | DCF / comps / LBO output blocks, WACC build, sensitivities |
| `Checks` | formulas that print TRUE/FALSE for every structural invariant |
| `Notes` | methodology, period definitions, data sources, open questions |

Conventions that make a model readable and auditable:

- **Color code.** Blue font = hardcoded input, black = formula, green = link to
  another sheet or workbook. Fill colors stay in blues/greys: dark blue + white bold
  for section headers, pale blue for column headers, light grey for statistics rows.
- **Anchor what must not move.** `$C$7` for a single source cell, `C$5` for a row of
  period headers, `$C7` for a column of labels — so copying a formula across or down
  cannot silently re-point it.
- **Named ranges** for anything a memo, deck, or second sheet references — a named
  `BaseRevenue` survives row insertion; a cell address does not.
- **One source of truth per figure.** If revenue lives in `Inputs!C7`, every other
  sheet references it. The same number typed twice is the classic reconciliation bug.
- **Never overwrite an input cell with a formula**, and never leave a subtotal or a
  statistic as a literal — a literal is invisible to the model's own logic.
- **Blank vs 0.** Leave genuinely unknown periods blank; a 0 is a claim.

## Build loop

1. **Fix the question.** Ask what the model is for — valuation, financing, covenant
   test — and which periods, currency, and units. State your assumptions back in one
   short block and get agreement before building. A model that answers the wrong
   question is worse than no model.
2. **Sketch the structure** — sheets, row plan (what is a row, in what order), where
   inputs end and formulas begin. Write this plan into the builder script as
   constants so the layout is one edit away from being re-flowed.
3. **Build in dependency order**: inputs → schedules → statements → valuation →
   sensitivities → checks. Do not jump to the output block first.
4. **Validate** with the script below; fix what it reports.
5. **Deliver**: export the workbook, and in the reply state what is in it, the key
   inputs and their sources, the Python-computed headline outputs, and what you had
   to assume. Do not deliver a model whose inputs you cannot source.

## Checks that must exist

A model without a `Checks` sheet is a draft. Write these as Excel formulas so they
are live for the user, and mirror the same test in Python for your own verification:

- Balance sheet balances each period: `Assets - Liabilities - Equity = 0`
- Cash flow ties: closing cash = opening cash + net change, per period
- Retained earnings roll: prior RE + net income − dividends = closing RE
- Debt schedule ties: opening − repayment + draw = closing, per tranche
- Sources = uses (LBO / merger); purchase price = consideration + fees
- Sum-of-parts equals consolidated where both are shown
- Every forecast period has no blank in a calculation row

Report checks as TRUE/FALSE cells, not as silent zeroes. A check that cannot be
computed in the workbook (because it needs an Excel recalc) is a Python assertion
printed in chat — do not fake it with a hardcoded TRUE.

## Model recipes

Every reference below ships with this skill — open the one that matches the ask
before building (they are deployed to the sandbox under
`{baseDir}/references/` if you want to read them as files):

| Ask | Reference |
|---|---|
| 3-statement / operating model, credit metrics, covenants | `{baseDir}/references/three-statement.md` |
| DCF — WACC, terminal value, implied price, sensitivities | `{baseDir}/references/dcf.md` |
| LBO — sources & uses, debt schedule, returns | `{baseDir}/references/lbo.md` |
| Merger / accretion-dilution, purchase accounting | `{baseDir}/references/merger.md` |
| Trading comps, precedent transactions, statistics blocks | `{baseDir}/references/comps.md` |

## Auditing an existing model

The same script runs in reverse. Load the user's workbook (asked for into
`/workspace/` as an attachment, or built by you earlier), then:

1. Run the validator from a `runtime_run_code` cell:
   `import runtime; runtime.proc.exec("python {baseDir}/scripts/validate_model.py <file.xlsx>")`
   — it prints findings with cell addresses and exits non-zero on errors.
2. Walk the checks list above against the file; report pass/fail with cell addresses.
3. Report **findings, not a rewrite**: every issue with sheet + cell + why it matters,
   ranked by whether it changes an output. Offer fixes; do not silently re-author
   someone's model unless asked.
4. If the workbook has no `Checks` sheet, say so — that is a finding.

Recalculation limits apply here too: openpyxl reads the last values Excel saved. If
the user's file was never opened in Excel (or saved by a non-Excel tool), cached
values may be stale or missing — validate structure, do not trust cached numbers.

## Failure modes seen in practice

| Symptom | Cause | Fix |
|---|---|---|
| Model "doesn't balance" | a subtotal typed as a literal, or a sign flipped in one period | rebuild the affected row from formulas; check sign conventions in the reference |
| Multiple unchanged when an input changes | derived cell is a hardcode | validator marks it; convert to formula |
| Sensitivity grid shows the same number in every cell | grid cells reference the base case, not their row/column headers | each cell must recompute from `$A<row>` and `<col>$<header>` |
| Circular reference warning | interest on average debt, cash sweep feeding interest | break it: interest on opening balance, or iterate — state which you chose in Notes |
| Excel opens with a repair prompt | malformed merged range or an unsupported type written by openpyxl | merge only after writing the top-left value; keep values to str/int/float/date |
| Numbers off by 1000× | units row not carried through (thousands vs millions) | units declared once in `Inputs` and named; every header states it |

## Delivery

- Name the file for the model, not the request: `titan-dcf-2026-10.xlsx`.
- Deliver the workbook; include the builder script as a second export when the user
  will want to re-run or extend the model (`model.py`).
- The reply states: what the model does, inputs and sources, Python-computed headline
  outputs, checks status, and every open assumption. Never present the model as
  investment advice — it is analysis for a human to review.
