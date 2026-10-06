# Roll-forwards and variance commentary

Two close-package deliverables that share one discipline: the number comes from activity
you can point at, and the explanation names the activity rather than restating the number.

## Roll-forward

One account (or account group) per schedule, one period. The structure is fixed so a
reviewer can read the same schedule every month:

```
Opening balance (per prior-period close package, or GL at prior period end)     X
  + Additions / new activity this period                                        A
  + Accruals booked this period                                                 B
  − Reversals of prior-period accruals                                         (C)
  − Payments / settlements / releases                                          (D)
  ± Reclasses between accounts                                                  E
  ± FX translation on non-base-currency balances                                F
  ± Other identified movements, one line each                                   G
= Closing balance (per GL at period-end date)                                   Y
```

**Foot check:** `X + A + B − C − D + E + F + G = Y`. Report pass/fail and the residual.

### Rules that keep the schedule useful

- **Every line cites its source**: the GL query (account + date range + journal source),
  the invoice, the schedule, the calculation. A line without a citation is a plug.
- **If it does not foot, add an "unexplained" line** with the residual and leave it
  visible. Never widen reclasses, never round the closing balance to the opening plus
  something, never add a "suspense" line that absorbs the difference between months.
- **Opening and closing come from the system** (GL balance at the two dates), not from the
  prior workpaper's closing line. When they disagree, the prior period was adjusted —
  that is a finding, not a nuisance, and it gets its own note.
- **Reclasses are two lines or none.** A reclass moves value between accounts; show the
  out of one account and the into another, with the journal reference.
- **FX translation is only for balances held in another currency.** If it appears on a
  base-currency account, the account mapping is wrong.
- **Group activity so it can be traced.** A single "additions" line of $48m is unauditable;
  group by source system or by counterparty and cite the query that produces each group.
- **Accruals reverse on schedule.** The roll-forward is the natural place to see an accrual
  that was booked and never reversed — check that each prior-period accrual appears in the
  reversals line.

### Account notes

| Account | What the lines usually are |
|---|---|
| Accrued management fee | opening accrual, this period's accrual from the fee run, payment of prior accrual, reversal |
| Accrued expenses (audit, admin, legal) | invoice received and accrued, paid prior accrual, release of an over-accrual |
| Payable for investments purchased | trade-date accrual, settlement, reversals from failed settlements |
| Receivable for investments sold | trade-date accrual, proceeds received, reversals |
| Due to/from affiliates | a movement per counterparty; if it does not net to zero across entities, say so |

## Variance commentary

### Threshold

Comment on a line when **either** holds:

- absolute variance ≥ the firm's materiality threshold, **or** ≥ the relative threshold
  (default 5%) of the line, whichever is greater — state which figure you used; or
- the line is on the always-comment list (management fee, performance fee, cash,
  subscriptions/redemptions, any line above a stated dollar floor).

Budget comparison uses the same rule. Thresholds are inputs, not judgement calls: put the
number in the reply.

### The driver

A driver is the underlying activity that produced the movement. Find it in this order and
stop when the arithmetic closes:

1. **Volume × rate.** Headcount × cost, units × price, AUM × fee rate. This closes most
   fee and expense lines completely.
2. **A named counterparty, investor, or security.** "Redemption by Investor X on 12 Mar"
   beats "redemptions were higher".
3. **A date and the item that moved on it.** A close, a call, a fee step-up, a
   subscription in transit. This is what "due to timing" means — and if you cannot name
   the date and the item, the driver is not established.
4. **A policy or accrual change.** Say which one and when it was applied.
5. **Nothing closes it** → write "driver unclear — flagged for controller", with the
   amount and any partial explanation you do have.

Write the driver as one sentence that names the activity, the amount, and the reference:

- "Management fee up $412k (11.4%): first full quarter of fee-bearing capital on Fund II
  after its 1 Mar close (workpaper row 18; fee run 2026-03-31)."
- "Legal expense down $96k (62%): the 2025 audit completed in Feb; no equivalent this
  period (invoice register 2026-03)."
- "Unrealized change −$3.1m: mark on the Aurora position moved with the sector index;
  driver is market, not fund activity (valuation pack p.4)."

Never write: "increased due to higher activity", "varies with the portfolio", "due to
timing" with no item named, or a sentence that repeats the percentage back.

### Structure of the deliverable

| Line | Current | Prior | Budget | Δ prior | Δ prior % | Δ budget | Δ budget % | Driver |
|---|---|---|---|---|---|---|---|---|

Then a short narrative (3–5 sentences) naming the two or three largest movers and any
item that needs a decision. Group the table by statement order, not by variance size, so
it reads like the financials; rank within the narrative by size.

### Close-package checks

- Budget plus every variance equals actual, per line — a commentary table that does not
  add up is a defect, and the reviewer will find it.
- Every flagged line has a driver, including the ones where the driver is "unclear".
- Every driver cites a workpaper row, document, or query.
- Lines over threshold but with no historical comparison (a new account, a first-period
  close) say so instead of showing a meaningless 100% variance.
- FX-driven moves are labelled as FX, with the rate used, so a portfolio change is not
  mistaken for a currency effect.
