# Three-statement model

Income statement, balance sheet, cash flow — driver-based, tied together, with credit
metrics and scenarios. Build in this order: drivers → IS → BS → CF → checks. A model
built output-first will not tie.

## Drivers before statements

Revenue:

- Segment or product lines, each with volume × price or growth × base — never one
  aggregate growth rate on a multi-segment business unless the segments are immaterial.
- Seasonality only if the model is quarterly; annual models should not carry quarterly
  noise it cannot use.

Costs:

- COGS as driver (% of revenue per segment) or gross margin per segment; pick one.
- Opex: split fixed vs variable. Fixed costs that grow with revenue are a common defect;
  so are variable costs that don't.
- Headcount, if it is the true driver: headcount × cost per head, with hiring plan.

Working capital:

- DSO / DIO / DPO in days, converted to balances: `AR = DSO/365 × revenue` (use 360
  only if the business does — state the convention).
- Model the *balance*, not the flow, then take the change. Negative days are a claim,
  not a default.

Capex & D&A:

- Capex as % of revenue or explicit maintenance + growth split; depreciation from a
  rolling PP&E schedule (`Opening + Capex − D&A = Closing`), so D&A follows capex with
  a lag instead of a flat percentage.

Debt & interest:

- Tranche schedule as in the LBO reference; interest on opening balances.

Tax: on EBT with any DTAs/NOLs carried explicitly.

## Statements

**Income statement**: revenue − COGS = gross profit; − opex = EBIT; ± interest = EBT;
− tax = net income. Margins as formulas off the lines above, never typed.

**Balance sheet**: every line is either an input balance rolled forward or a formula
tied to a schedule. Equity = share capital + APIC + retained earnings (rolling:
`prior RE + NI − dividends ± buybacks`).

**Cash flow (indirect)**: start NI, add back D&A and other non-cash, subtract ΔNWC,
subtract capex; then financing (debt draws/repayments, dividends, equity) and investing
as needed. Closing cash = opening + net change, and closing cash ties to
`BS!cash` every period.

## Linkages that must hold (put these on `Checks`)

| Linkage | Test |
|---|---|
| Balance sheet balances | `Assets − Liabilities − Equity = 0` each period |
| Cash ties | `CF closing cash = BS cash` each period |
| RE rolls | `prior RE + NI − dividends = closing RE` |
| CF starts from NI | period 1 CF opening = IS net income, same period |
| PP&E rolls | `opening + capex − disposals − D&A = closing` |
| Debt rolls | per tranche, as in the debt schedule |
| NWC change ties | `ΔNWC on CF = Δ(balance-sheet NWC)` |

A single master check (`=SUM(ABS(...))` over the above) plus individual TRUE/FALSE rows
per check. One number the user can look at, and the detail when it goes false.

## Sign conventions — declare once, apply everywhere

| Item | Convention |
|---|---|
| Capex | positive number, subtracted in CF and added to PP&E |
| ΔNWC increase | negative on CF |
| Debt draw / repay | positive / negative in financing |
| D&A | positive on CF, positive expense on IS |
| Balance-sheet debt | positive regardless of asset/liability side |

Mixed conventions inside one schedule is the most common cause of "the model was
balancing yesterday".

## Circularity

Interest on average debt, or a cash sweep feeding interest, makes the model circular.
Options, in order of preference:

1. Avoid it — interest on opening balances (declare this).
2. If it must be circular, state that the user has to enable iterative calculation in
   Excel (File → Options → Formulas), and put the toggle in `Notes`.

Never "fix" a circular reference by pasting a value over the offending formula.

## Scenarios

- One `Scenario` input cell (Base / Upside / Downside) and `CHOOSE`/`INDEX` on a
  scenario block — never three parallel copies of the model.
- Scenario axes: revenue growth, margin, and (for a credit case) the stress variable
  that matters — a covenant breach scenario, not a cosmetic one.
- The scenario switch must not be the only difference between the cases; state which
  drivers move and by how much.

## Credit metrics and covenants

Include, when the user's question is credit: net debt/EBITDA, interest coverage
(EBITDA/interest, EBIT/interest), FCF conversion, and covenant levels with a
headroom row. Test covenants in the downside scenario, not the base — a covenant
test that only passes in the base case is decoration.

## Errors seen repeatedly

1. Balance sheet plugged with a "balancing" line. The plug hides the error forever.
2. D&A as a flat percentage of revenue while capex has its own schedule.
3. ΔNWC computed from P&L flows rather than balance-sheet deltas.
4. Deferred revenue treated as a cash inflow every period without a release schedule.
5. Dividends in the CF but not in the RE roll.
6. One scenario's hardcoded drivers leaking into another via a shared assumption row.
7. Check rows that are themselves hardcoded TRUE — the model's checks must be formulas.
