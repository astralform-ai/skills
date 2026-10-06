# NAV tie-out and investor allocations

The fund-level NAV and the investor capital accounts are produced from the same
underlying activity but by two different routes. The tie-out is the control that the two
routes agree. **Recompute one side from the other side's components** — comparing two
prints of the same file proves nothing.

## The two levels

| Level | Produced by | What it must agree to |
|---|---|---|
| Fund NAV | fund accounting: assets − liabilities, per the NAV pack | the fund's own valuation and accrual totals |
| Investor capital accounts | fund admin / transfer agent, one per LP | their sum is fund NAV (within the rounding policy) |

If the two levels are in different files, reconcile them at the fund level first; a
per-investor tie-out on top of an untied fund total is work on a broken base.

## Recompute the investor's capital account

```
Beginning capital (prior period's ending capital, per the signed statement)
  + Contributions paid this period (capital calls, at the call date amounts)
  + Contributions receivable / payable released this period
  − Distributions (cash, and in-kind at their stated valuation date)
  + Allocated net investment income / (loss)
  + Allocated realized gain / (loss)
  + Allocated change in unrealized
  − Management fee allocation
  − Fund expense allocation
  − Carried interest / incentive allocation (only when crystallized this period)
  ± Transfers in / out (at the effective date the admin used, not the notice date)
  ± Equalization / correcting entries
= Ending capital
```

Every line carries the same tolerance as the recon (`0.01` unless policy says otherwise)
and every line cites where its input came from — the NAV pack tab, the fee run, the call
notice, the waterfall output.

## Checks that must sum

Run all of them; each catches a different class of error. Report pass/fail per check with
the residual, even when it is zero.

| # | Check | Catches |
|---|---|---|
| 1 | ending capital per investor = beginning capital + the period's activity lines | a statement that does not foot to its own components |
| 2 | sum of investor ending capitals = fund NAV (within rounding policy) | an investor omitted, included twice, or allocated to the wrong share class |
| 3 | sum of allocations = the fund's total allocatable income and expense | a fee or expense allocated to nobody, or to everybody twice |
| 4 | sum of management fee allocations = the fee actually charged by the fund | a fee rate applied to the wrong capital base |
| 5 | each investor's ownership % × fund NAV = that investor's capital account | an ownership percentage that does not match the capital account |
| 6 | commitments paid + unfunded = committed capital, per the commitment register | a call recorded against the wrong commitment or fund |
| 7 | an investor's beginning capital this period = their ending capital last period | a restated prior period, or a missing roll |
| 8 | distributions + ending capital + recallable amounts reconcile to total called | money leaving in a form that does not appear anywhere |
| 9 | NAV per share/unit × units outstanding = NAV (for share-class funds) | a unit count that missed a subscription or a transfer |
| 10 | the performance fee accrual reverses or resets exactly as the waterfall states | a crystallized fee carried into next period |

## Where capital-account ties break most often

- **Ownership percentage at the wrong date.** A transfer effective mid-period is applied
  from the 1st or from the transfer date. Two operators, two answers. Take the date from
  the admin's own record and show it in the workpaper.
- **Fee basis.** Management fee on committed capital, on invested capital, or on NAV —
  and whether the basis steps down after the investment period. A fee computed on the
  wrong basis ties at the fund level (check 4 passes for the fund) and breaks at the
  investor level.
- **In-kind distributions.** Valued at the distribution date, not the period end. The
  difference lands entirely in allocated unrealized and looks like a valuation break.
- **Equalization and correcting entries.** Real, and always worth a line of their own.
  An equalization entry folded into allocations hides the fact that new investors paid
  a different amount per unit.
- **Expenses allocated by ownership vs equally.** The fund total is right either way;
  every investor total is wrong under the other convention.
- **Rounding policy.** Allocate exact, round on presentation; do not round each investor
  and then force the total to match by adjusting one investor. Record the policy.
- **Recallable distributions.** A distribution that can be recalled is not a reduction in
  committed capital — if the register nets it, check 6 fails for every investor at once.

## Multi-period tie

- This period's ending capital must equal next period's opening capital, per investor.
  Do this check the moment the next draft exists; a break here is often a restatement
  published without notice.
- A NAV restatement invalidates every downstream workpaper for that period. Say so, and
  re-run rather than editing the previous workpaper.

## Output

A per-check pass/fail block, a per-investor table (beginning, activity lines, ending, and
the recomputed value alongside the statement value where they differ), and a flag list.
Nothing here changes a statement or a ledger — the publisher acts on the flags after
review.
