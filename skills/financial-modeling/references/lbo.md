# LBO — leveraged buyout

A returns-model: purchase price, financing, debt paydown, exit. Every number must
trace to a source (comp, term sheet, management case) — LBO outputs are dominated by
assumptions, so state them loudly.

## Sourcing the purchase price

```
Purchase price (EV) = offer per share × FDSO + debt assumed − cash acquired
Uses  = purchase price × (1 + fee %) + financing fees + OID
Sources = term loan + revolver draw + notes/bonds + sponsor equity + rollover equity + management rollover
```

- Use fully diluted shares (options via treasury-stock method), not basic.
- Fees: advisory + financing are separate lines; they hit the uses side and (per
  policy) are either capitalized or expensed — pick one and say which.
- **Check: sources = uses, exactly, every version of the model.**

## Opening balance sheet

Rebuild the target's balance sheet on the transaction date:

- Write-ups: step-ups in assets, new intangibles (customer relationships, brand,
  technology), inventory step-up — each with an amortization life.
- Deferred tax liability on the write-ups (asset step-ups create DTLs).
- **Goodwill** = purchase price − fair value of net identifiable assets (a plug only
  if the asset-side items are stated first; never plug the asset side instead).
- New debt at fair value, financing fees as a discount if capitalized.
- Equity = sponsor check + rollover; retained earnings reset to zero on the
  transaction-date column if the model presents post-close standalone.

## Debt schedule

One block per tranche, same rows every time:

```
Opening balance
+ Draws (revolver only, from the cash shortfall line)
− Mandatory amortization (% of original face, per tranche)
− Cash sweep (% of excess cash flow, per tranche, per waterfall)
= Closing balance
Interest = rate × opening balance   (or average — see circularity below)
```

- **Interest on opening balances** is the no-circularity convention. If you use
  average debt, declare the circular switch and how the user should enable iterative
  calculation in Excel.
- Revolver: draw exactly the shortfall so cash never goes negative; also cap repayment
  to available cash after mandatory amortization.
- Cash sweep waterfall: revolver first, then term loans in seniority order; state it.
- PIK tranches accrue rather than pay — model the accrual as a separate row so the
  interest expense in the P&L and the balance can diverge correctly.
- **Check: per tranche, opening − amort − sweep + draw = closing; and cash ≥ 0 every
  period.** A negative cash balance is a model error, not a finding.

## Exit and returns

```
Exit EV        = exit multiple × exit-year EBITDA
Exit equity    = exit EV − net debt at exit − remaining preferred/fees
MOIC           = exit equity / sponsor equity invested
IRR            = XIRR of (entry equity outflow, exit equity inflow)   [use cash-flow dates]
```

- Exit multiple: the same comp set as entry, stated as a range; a base case that
  assumes multiple expansion must say so.
- Management promote / option pool dilutes the sponsor's proceeds — model it if the
  term sheet has one, otherwise note its absence.
- Also report **entry metrics**: EV/EBITDA, total leverage (debt/EBITDA), interest
  coverage in year 1, and FCF conversion — a model with a great IRR and no coverage
  in year 1 is a red flag, not a result.

## Sensitivities

- Entry multiple × exit multiple → IRR.
- Exit multiple × leverage → MOIC.
- (If debt is the story) exit multiple × cash-sweep % → YE net leverage.
- Same rules as the DCF: per-cell formulas built from their headers, base case in the
  center, center equals the headline number.

## Checks

- Sources = uses; and again after the sensitivity inputs are switched.
- Debt roll-forward ties per tranche; total debt = Σ tranches.
- Cash never negative; revolver = 0 unless the shortfall line is positive.
- Exit equity = exit EV − exit net debt (ties to the debt schedule's final column).
- MOIC and IRR are consistent: `MOIC = (1 + IRR)^years` for a single in/out pair.
- Goodwill + net identifiable assets = purchase price.

## Errors seen repeatedly

1. Interest calculated on closing (post-sweep) debt — circular, and the numbers still
   look plausible until Excel complains.
2. Cash sweep ignoring the minimum cash balance, sweeping money the business needed.
3. Fees double-counted: deducted from equity and also included in the uses side.
4. Exit year EBITDA taken pre-add-backs while the entry multiple was post-add-backs.
5. Amortization schedule as % of *outstanding* balance (compounds to zero) instead of
   % of original face.
6. Returns computed on total sources instead of sponsor equity only.
7. Sensitivity grids with entry/exit axes swapped relative to their labels.
