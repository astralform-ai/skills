# Reconciliation — matching, tolerances, breaks

Detail for step 3 of the parent skill. The CLI enforces all of it; this is what to do
when the CLI's classification is wrong for the case in front of you, and what the
workpaper columns mean when you write the commentary.

## Matching order

Match in this order and stop at the first success. Doing them in one pass produces
misclassification, because a fuzzy rule masks a break an exact rule would have found.

1. **Exact composite key.** Every key column normalized the same way on both sides
   (upper case, collapsed whitespace, no leading zeros lost). This is the only rule that
   can *prove* two rows are the same row.
2. **Exact key, tolerance on the amounts.** Absolute first, then relative if the caller
   set one. Report which one admitted the row — a row admitted by a 1% relative tolerance
   is not the same evidence as one admitted by $0.01.
3. **Key with a date difference inside the date tolerance.** This is the timing bucket.
   Posting date, not trade date, is the default comparison; if the sources carry both,
   compare posting date and record the trade date alongside.
4. **Aggregation over a repeated key.** Group and sum before matching, and record the
   line counts. Two rows that sum to one is not the same as one row that equals one —
   write the counts into the note.
5. **Fuzzy on the identifiers, last.** Trailing check digits, an exchange suffix, an
   internal vs vendor security id, a slightly different account code. A fuzzy match is a
   *suggested pair*, so bucket it as `mapping`/`data_quality` and let a human confirm —
   never silently promote it to `matched`.

Never fuzzy-match on amounts alone. Two unrelated transactions of the same size are the
most common false pair in a fund's flow, and a false pair closes a break that is real.

## Tolerance policy

Set the tolerance from the firm's policy, not from the size of the breaks you found.
Record all of them in `Params`:

| Tolerance | Default | What it absorbs | What it must not absorb |
|---|---|---|---|
| Absolute amount | 0.01 | rounding on accrued or translated amounts | a missing fee, a mispriced trade |
| Relative amount | off | a small rounding band on a very large balance | anything you cannot explain line by line |
| Quantity | 0 | nothing | a lot or factor difference |
| FX rate | 1e-6 | rate rounding at the stored precision | a different rate date or source |
| Fee | off (0) | recurring fee/accrual deltas posted one side only | a fee that should have been posted twice |
| Date | 0 days | a same-day cut-off difference | a T+2 vs trade-date posting (that is a timing break) |

Rules that keep a tolerance from hiding something:

- **Both tolerances are stated in the reply**, in the same units as the amounts.
- **A relative tolerance never replaces an absolute one on a small line.** 0.5% of
  $200,000 is $1,000 — bigger than most real fee breaks.
- **Widen only with a reason, and re-run the whole recon.** Changing a tolerance for one
  break and leaving the rest is how a recon goes soft.
- **Every tolerance change is visible in `Params`.** A reviewer must be able to see that
  the run used 0.01 and not the policy's 0.05.

## Break taxonomy — hypothesis, not conclusion

A bucket is where the break landed; a cause is what probably produced it. Say the cause
as a hypothesis in the commentary until the source document confirms it.

| Cause | Test that distinguishes it | What it usually is |
|---|---|---|
| `timing` | amounts agree, dates differ; the item clears next period | trade vs settle date, a late feed, a cut-off at 15:00 vs end of day |
| `fx` | local amounts agree, base amounts do not; the rates differ | a different rate source, or the same source at a different rate date |
| `fee` | small, recurring, same direction, one side or one line only | management fee, admin fee, custodian charge, expense accrual |
| `mapping` | one left-only and one right-only key whose amounts offset | a reclass posted to a different account code, or a mapping table version |
| `duplicate` | same amount and sign on both sides, or a key posted twice on one side | a re-run of a batch, a partially replayed feed |
| `sign` | same magnitude, opposite sign | one system stores liabilities positive |
| `missing` | amount present on one side only, nothing offsets it | a genuinely unposted transaction |
| `data_quality` | the amount or date will not parse | a text marker, a formatted blank, a merged cell |
| `real` | amounts differ, none of the above applies | an actual difference in the recorded amount — the item to escalate |

Sequence the tests in exactly this order: sign, quantity, fx, fee, real. A sign break
tested as a fee break will look like a small fee if the amounts are small, and an FX
break measured on the base amount will look like a real amount break of exactly the
translation difference.

## Offsetting breaks are two breaks

A reclass shows up in a key-level recon as one left-only row and one right-only row with
opposite amounts. Detection is `left_amount + right_amount ≈ 0`. Two rules follow:

- **They are reported separately, always.** The mapping row keeps its own key, its own
  amount, and its own cause; the workpaper never shows a single netted zero.
- **The summary carries a netting flag.** Gross break delta (sum of |delta|) and net delta
  (sum of delta) are both printed. If the net is small relative to the gross, the reconcil
  has been fooled by offsetting entries until every pair is resolved.

The same test with a `+` instead of a `−` finds duplicate postings (same amount, same
sign, both sides). Those are labelled `duplicate_candidate` and left for the resolver: a
duplicate is suppressed only after the source feed proves the batch was replayed.

## Workpaper columns

| Column | Meaning |
|---|---|
| `key` | the composite key, joined with `|`, normalized |
| `bucket` | matched / timing / fx / amount_break / quantity_break / sign_break / left_only / right_only / error |
| `cause` | the hypothesis above |
| `left_amount`, `right_amount` | the amount as aggregated for that key; blank when the key is absent |
| `delta` | `right_amount − left_amount` — the definition is in `Params` |
| `abs_delta`, `rel_delta` | size of the break, absolute and as a share of the larger side |
| `left_rows`, `right_rows` | source lines behind the key; a mismatch means aggregation happened |
| `left_date`, `right_date`, `date_days` | posting dates and their gap |
| `note` | the one-line reason, including offsets and counterpart keys |

## Writing the commentary from the workpaper

- Column totals come from the `Summary` sheet, not from re-adding the `Workpaper` by hand.
- The top five breaks by `abs_delta` are named individually, with key, bucket, and cause.
- Break counts by bucket are stated even when the amounts are small — a count of 300
  timing breaks matters to the operations queue even at $12 each.
- Anything in `error` is a data problem, not an accounting one: repair the extract and
  re-run before you write any commentary about the period.
- The period is not "clean". Say "reconciled subject to the breaks listed", or state the
  residual exactly. A workpaper that claims a clean close over an unexplained item is
  worse than a late one.

## Running it on a schedule

`--fail-on-breaks` makes the run exit 1 when anything is unresolved, so a routine can
stop and alert instead of publishing a workpaper. Keep the parameters in the routine's
command line, not in someone's memory: the same tolerances must apply to every run, or
period-over-period comparisons of the break count mean nothing.
