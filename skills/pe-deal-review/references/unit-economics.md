# Unit economics and revenue quality

Unit economics answer one question: does acquiring and serving one more unit of the
business create cash, and how fast? Reported revenue does not answer it — a
contract signed in December and billed in March is not the same asset as a cash-paid
subscription.

Ask for customer-level or cohort-level data first. Aggregate metrics hide exactly
the problems diligence exists to find: a rising blended margin can sit on top of a
decaying newer cohort.

## Start with the revenue bridge

Classify every dollar before computing anything:

| Class | Treatment |
|---|---|
| Recurring, contracted | The asset. Value on ARR/retention, not a multiple of last year's revenue |
| Recurring, non-contracted | Discount it — churn behaviour is unproven |
| Usage-based | Value on consumption trend and expansion, not a contracted backlog |
| Professional services / implementation | Separate line, lower multiple, often a delivery-cost centre |
| One-time / perpetual licences | Not recurring; do not annualize |

**ARR bridge** — the only credible way to show where growth comes from:

```
Opening ARR
+ New (new logos)
+ Expansion (upsell / cross-sell / price)
− Contraction (downgrades)
− Churn (logo lost, dollars lost)
= Closing ARR
```

Report gross and net retention separately. Net revenue retention above 100% can
coexist with brutal churn if expansion is strong: always show GRR, NDR, and logo
churn together, or none at all.

## Cohorts, not blends

A blended metric is a weighted average of every vintage ever sold; it improves
mechanically as a business grows and can hide a newer, worse product. Build the
cohort matrix for as many vintages as exist:

| Cohort | Year 0 | Year 1 | Year 2 | Year 3 | Year 4 |
|---|---|---|---|---|---|
| | $ | $ | $ | $ | |

Show it twice: absolute dollars, and indexed (Year 0 = 100) so you can see whether
newer cohorts retain as well as older ones. A newer cohort retaining materially
worse than the oldest vintage is a red flag even when total revenue is growing.

## The customer math

```
CAC (per segment)   = fully loaded S&M in period ÷ new customers in period
Gross margin        = (revenue − hosting − delivery − support) ÷ revenue
LTV (simple)        = ARPU × gross margin ÷ monthly churn rate
Contribution margin = revenue − all variable cost to acquire AND serve the customer
CAC payback (mo)    = CAC ÷ (ARPU × gross margin)
```

Rules that make these numbers mean something:

- **Segment the CAC.** Blended CAC lets a cheap SMB motion subsidize an expensive
  enterprise motion in the reporting, which is how a business buys growth it cannot
  afford. Compute enterprise / mid-market / SMB separately and reconcile to the
  P&L's total S&M.
- **Fully load S&M**: salaries, commissions, tooling, marketing spend. A CAC built
  on ad spend alone is a marketing CAC, not a customer CAC.
- **Use cash churn in the LTV denominator**, or use gross margin and churn on the
  same definition — mixing gross and net destroys the ratio.
- **Payback is the most robust metric** because it needs the fewest assumptions.
  It also states the financing requirement: a 24-month payback means 24 months of
  cash out before the customer repays their acquisition cost.

## Contribution margin, then accounting vs cash

Build the waterfall explicitly and keep fixed cost out of it:

```
Revenue
− cost of service (hosting, delivery, support)
= Gross profit
− customer acquisition (fully loaded)
= Contribution margin          ← the unit decision lives here
− fixed R&D, G&A
= EBITDA
```

Contribution margin decides whether to spend more on growth; EBITDA decides whether
the business can service its debt. A business with strong contribution margin and
negative EBITDA is an investment decision; the reverse is a business that grows
itself into a hole.

Accounting and cash economics diverge in predictable places — reconcile each:

| Item | Accounting treatment | Cash reality |
|---|---|---|
| Deferred revenue | Recognized over the term | Cash arrives up front; a cash tailwind in a growing business |
| Capitalized software / S&M | Amortized | Cash spent now; capitalization flatters EBITDA |
| Stock-based comp | Non-cash expense | Dilution or cash once the sponsor buys shares |
| Working capital | Accrual movement | Defers or consumes cash; the fastest lever on near-term FCF |
| Capex vs opex | Depreciation vs expense | Cash is cash either way; classify for comparability, not for the answer |
| Deferred consideration | Note to the accounts | Real cash obligation, treat as debt-like |

**Never annualize a period distorted by one of these.** A quarter with a large
annual prepayment is not run-rate revenue.

## Benchmarks

Use these as a sanity band, not a target. A deal outside the band needs an
explanation, not an exclusion.

| Metric | Best-in-class | Good | Concerning |
|---|---|---|---|
| Net revenue retention | > 120% | > 110% | < 100% |
| Gross retention | > 95% | > 90% | < 85% |
| LTV : CAC | > 5x | > 3x | < 2x |
| CAC payback | < 12 months | < 18 months | > 24 months |
| Rule of 40 (growth + EBITDA margin) | > 40 | 25–40 | < 25 |
| Magic number (net new ARR ÷ prior S&M) | > 0.75 | 0.5–0.75 | < 0.5 |

## Red flags in unit economics

- Blended metrics reported with no cohort or segment view.
- NDR above 100% with gross churn above 15% — expansion is masking a leaky bucket.
- CAC that excludes commissions or tooling; a "payback" under 6 months is usually
  a missing cost, not an efficient machine.
- Revenue quality that improves when a specific quarter is excluded.
- Professional services revenue counted toward recurring revenue to lift the ARR
  multiple.
- Retention measured on logo count while the dollar churn is the real problem.
