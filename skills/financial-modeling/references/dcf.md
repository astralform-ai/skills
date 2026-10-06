# DCF — discounted cash flow

Structure, formula patterns, and the errors that recur. Read with the parent skill's
conventions; the workbook keeps every derived cell as a formula.

## Inputs to settle before building

Ask for, and record in `Inputs`, each one:

| Input | Note |
|---|---|
| Base year revenue and the forecast horizon | 5–10 years; state the fiscal-year end |
| Growth, by year | Either an explicit ladder or one driver (volume × price) — never both |
| Margins by year | EBIT margin, or build from COGS/opex lines; say which |
| Tax rate | Marginal, and whether it changes over the horizon |
| D&A, CapEx, ΔNWC | As % of revenue or explicit rows; must be consistent with the 3-statement if one exists |
| Net debt, minorities, associates, cash | From the latest balance sheet, with an as-of date |
| Share count | Diluted, treasury-stock method; state which |
| WACC inputs | Risk-free, ERP, beta (+source), size/other premia, cost of debt, structure |
| Terminal method | Gordon growth or exit multiple — pick one as the base case, cite the other as a cross-check |

## Free cash flow (unlevered)

```
FCF = EBIT × (1 − tax) + D&A − CapEx − ΔNWC
```

- Discount **unlevered** FCF at **after-tax** WACC. Never put interest expense in
  FCF; never discount pre-tax cash flows.
- ΔNWC is an increase in working capital = cash outflow. Keep the sign visible in a
  dedicated row; sign errors here are the most common silent breakage.
- Mid-year convention: discount period `t − 0.5` when cash flows arrive evenly.
  State the convention; mixing conventions between TV and explicit periods is wrong.
- If any row is negative in a period (CapEx > D&A), keep it negative — a `MAX(0, ·)`
  in a cash-flow row hides the case the model exists to show.

## WACC

```
WACC = E/(D+E) × (Rf + β×ERP + premia) + D/(D+E) × Kd × (1 − tax)
```

- Weights at **market** values, not book. If a target structure is stated (e.g., 30%
  debt), use it and say so — a normalization toward the target is a deliberate choice.
- Cost of debt = yield on the company's debt or a rated peer yield, not the coupon of
  one issue. For a private company, say which proxy you used.
- Beta: cite the source and window. A bottom-up peer beta (unlever/relever) is more
  defensible than one regression; if you use the latter, name the index and period.
- The rate is nominal if cash flows are nominal. Do not discount nominal cash flows at
  a real rate.

## Terminal value

Two methods — compute both, present one, cross-check with the other:

- **Gordon growth:** `TV_n = FCF_n × (1 + g) / (WACC − g)`. Discount `TV_n` by
  `(1 + WACC)^n` (or the mid-year exponent you declared). `g` must be at or below
  long-run nominal GDP growth; a `g` within a point of WACC means the multiple is
  meaningless — say so instead of printing the number.
- **Exit multiple:** `TV_n = EBITDA_n × multiple`, sourced from comps or precedents.
  Then report the **implied** `g` from the Gordon formula and the **implied** exit
  multiple from the Gordon TV. If they are far apart, flag it.

## Enterprise → equity bridge

```
Equity value = Σ PV(FCF) + PV(TV) − Net debt − minorities − preferred
               + associates/investments − debt-like items (pension deficit, leases)
Equity value per share = Equity value / diluted shares
```

Every bridge item is a labeled input row, not a lumped "other". If the company has
options, apply the treasury-stock method and show the resulting share count.

## Sensitivities

Grids are **per-cell formulas**, not Excel's Data Table feature (which openpyxl cannot
create) and never pasted Python values:

- Axes: base ∓ 2 steps, odd dimension so the base case is the center cell. Center
  cell must equal the headline output — that equality is the grid's own check.
- Each cell recomputes from its own headers: row header `$A<row>` (WACC), column
  header `<col>$<header>` (g or multiple). Rebuild the sum-of-PV and TV inside the
  cell formula, referencing the model's FCF row and inputs so the grid moves with the
  model.
- Two grids: WACC × terminal growth, and WACC × exit multiple.
- Every axis pair must be economically sane: `WACC > g` in every column, and no cell
  computing a negative terminal multiple.

## Checks (add to the `Checks` sheet)

- Σ PV(FCF) + PV(TV) − bridge = equity value (formula identity, TRUE)
- Center cell of each sensitivity = headline value
- Implied exit multiple vs comps multiple within a stated tolerance — flag, don't hide
- No FCF row cell is blank in a forecast period
- WACC recomputes from its own build rows

## Errors seen repeatedly

1. Discounting TV at `(1+WACC)^n` when mid-year convention was used for explicit FCF.
2. Terminal growth ≥ WACC, or terminal growth copying the last explicit-year growth.
3. Tax applied to net income instead of EBIT in the FCF bridge, then again downstream.
4. CapEx/ΔNWC as hardcoded per-year numbers that never touch the revenue assumption.
5. WACC built from book-value weights while the capital structure narrative says market.
6. Units drift: revenue in millions, WACC in percent, share count in thousands.
7. Sensitivity grid formulas pointing at the base case, producing 25 identical cells.
