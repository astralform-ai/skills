# Merger / accretion-dilution model

Two companies, one purchase price allocation, and a pro forma EPS. The output that
matters is accretion/dilution in year 1 and 2, plus the breakeven synergies that flip
the sign.

## Structure

1. Standalone forecasts for acquirer and target (same years, same assumptions' basis).
2. Purchase price and consideration mix (cash / stock / debt), with the acquirer's
   share price on the announcement-date basis.
3. Sources & uses — same discipline as the LBO reference: `Sources = Uses`, exactly.
4. Purchase price allocation (PPA) and the pro forma opening balance sheet.
5. Pro forma adjustments, then pro forma EPS by year.
6. Accretion/dilution vs the acquirer's standalone EPS, plus breakeven analysis.
7. Sensitivities: price × synergies, cash/stock mix × synergies.

## Purchase price and consideration

```
Purchase price = offer per target share × target FDSO
Cash consideration  = price × cash %          → funded by cash on hand + new debt
Stock consideration = price × stock %         → new acquirer shares = stock consideration / acquirer share price
```

New shares change the denominator — EPS accretion/dilution is a per-share question,
so the share count must be recomputed for every scenario.

## Purchase price allocation

- Identify write-ups: PP&E step-up, inventory step-up, identifiable intangibles
  (customer relationships, brand, technology, backlog) each with a life.
- DTL = tax rate × write-ups (asset step-ups without a tax basis create deferred tax).
- Goodwill = purchase price − fair value of net identifiable assets acquired.
- Transaction fees: expensed (and excluded from pro forma operating EPS by convention —
  say which treatment you used).

## Pro forma adjustments (each a separate, labeled row/column)

| Adjustment | Sign |
|---|---|
| Target EBIT (or EBITDA − D&A) | + |
| Synergies, net of cost to achieve | + |
| Incremental D&A on write-ups | − |
| Amortization of new intangibles | − |
| Interest on new acquisition debt | − |
| Interest income forgone on cash used | − |
| Incremental DTL release (if any) | ± |
| Deal fees expensed | − (period only) |

Tax-effect the adjustments at the marginal rate; a pre-tax adjustment that never
reaches the tax line changes EPS by more than the deal's economics.

## Accretion / dilution

```
Pro forma EPS = (acquirer NI + target NI ± after-tax adjustments) / (acquirer shares + new shares)
Accretion/(dilution) % = Pro forma EPS / acquirer standalone EPS − 1
```

- Report year 1 and year 2 — year 1 is often dilutive purely from fees and deal timing.
- Breakeven synergies: solve for the synergy number that makes pro forma EPS equal
  standalone EPS. In the workbook, that is the `Goal Seek`-able cell; state the value
  you computed in Python.
- Contribution analysis: what each company contributes to revenue/EBIT vs what its
  holders own of the combined entity — a mismatch is the argument for/against the deal,
  not a footnote.

## Checks

| Check | Test |
|---|---|
| Sources = uses | exact equality |
| Goodwill ties | `PPA!goodwill = purchase price − FV net assets` |
| Share count ties | `FDSO_combined = FDSO_acquirer + new shares` |
| EPS math ties | pro forma NI / combined shares = pro forma EPS, each period |
| Tax adjustments | every pre-tax adjustment has a tax line |
| Bridge | standalone EPS + Σ adjustments per share = pro forma EPS (± rounding) |

## Errors seen repeatedly

1. New shares computed from the *target's* share price or a stale acquirer price.
2. Synergies expensed in year 1 at the full run-rate, with no phasing or cost to achieve.
3. Write-up amortization hitting the P&L but the DTL never released.
4. Accretion stated off adjusted EPS for the acquirer and GAAP EPS for pro forma.
5. Cash used for the deal earning interest anyway (double-counted interest income).
6. Breakeven computed on a fixed share count, which the deal itself changes.
7. Fees forgotten in the uses side while the PPA still balances by coincidence.
