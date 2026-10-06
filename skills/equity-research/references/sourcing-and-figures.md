# Sourcing, bases and figures

How to get a figure that is defensible, how to state it, and what to do when it is not
there. Read this before the first number in any note.

## Retrieval order

Primary beats secondary, always. Work down this list and stop at the first source that has
the figure:

| Rank | Source | Where |
|---|---|---|
| 1 | The filing itself | SEC EDGAR — 10-K, 10-Q, 8-K (+ exhibits), DEF 14A |
| 2 | The company's own release / deck / transcript | the 8-K exhibit, or the IR site |
| 3 | A regulator or industry body | FDIC/FFIEC, EIA, ACEA, ISM, trade association data |
| 4 | A public aggregator or data vendor | cite it as such, with its own as-of date |

If you cite rank 3 or 4 for a figure that exists at rank 1, you have left evidence on the
table and, when the aggregator is wrong, you will have no defence. Say where the number came
from in the note's `Source:` line.

## Mining EDGAR

`web_search` first to resolve the ticker and find the current quarter's filing, then
`web_read` the document. The machine endpoints, when you need many figures at once and want
the raw JSON rather than a rendered page:

| Need | URL |
|---|---|
| Ticker → CIK map | `https://www.sec.gov/files/company_tickers.json` |
| Every filing by a company | `https://data.sec.gov/submissions/CIK##########.json` |
| All tagged facts (largest, slowest) | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` |
| One tagged line item over time | `https://data.sec.gov/api/xbrl/companyconcept/CIK##########/us-gaap/Revenues.json` |
| One item for all filers in a period | `https://data.sec.gov/api/xbrl/frames/us-gaap/Revenues/USD/CY2025Q2.json` |
| Full-text search across filings | `https://www.sec.gov/edgar/search/#/q=%22...%22` |
| Browsable filing list for one company | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<cik>&type=10-Q&count=40` |

- CIK is zero-padded to ten digits in the `data.sec.gov` paths (`CIK0000320193`).
- The SEC requires a descriptive `User-Agent` identifying the requester; requests without
  one are refused, and the fair-access limit is about 10 requests per second. Never loop a
  tight fetch over a large filing set.
- Path: fetch with the tools, write the payload into `/workspace/data/`, then let the script
  parse and compute over that file. A number must be traceable to a document you actually
  read, not to a fetch that returned something you never looked at.

### Which filing holds which figure

| Figure | Filing | Where inside |
|---|---|---|
| Quarterly revenue, margins, EPS, segments | 10-Q | financial statements + MD&A |
| Annual detail, 3-year trend, risk factors, business description | 10-K | Items 1, 7, 8 |
| The results announcement, and the deck/transcript attachments | 8-K | Item 2.02; exhibits 99.x |
| Material agreements, acquisitions, management change | 8-K | Items 1.01, 2.01, 5.02 |
| Executive pay, insider ownership, related-party transactions | DEF 14A | CD&A, ownership tables |
| Offerings and prospectus detail | S-1 / 424B | use of proceeds |
| Large / activist holders | SC 13D, 13G, 13F | ownership |
| Insider transactions | Form 4 | transaction code and date |
| Guidance | release and transcript | forward-looking statements + call Q&A |
| Prior guidance | the *previous* quarter's release/transcript | the base for the guide comparison |

**8-K Item 2.02 is the fastest route to the release**, but the 10-Q is the authority on the
numbers: the release is unaudited, curated and may present a metric the filing explains
differently. When they disagree, the filing's version is the one you report and the
disagreement is itself a finding.

## The figure's four attributes

A number is only usable with all four. Write them into the source line or the cell, not into
a footnote you might drop.

1. **Value** — the figure as reported, unrounded until you compute.
2. **Period** — `Q2 FY26` (Sept–Nov 2025), `FY25`, `LTM to 2026-06-30`, `as of 2026-09-30`.
3. **Basis** — GAAP or non-GAAP; reported or constant-currency; consolidated or continuing
   operations; diluted or basic; USD or local.
4. **Source** — the document, its date, the line or page.

Missing any one of the four is the defect the note gets sent back for.

## GAAP vs adjusted — get this right or nothing else matters

Report both side by side, and reconcile:

```
Non-GAAP EPS bridge, Q2 FY26 (as reported by the company)
  GAAP diluted EPS                              0.62
+ Amortisation of acquired intangibles          0.11
+ Stock-based compensation                      0.09
+ Restructuring                                 0.04
- One-time tax benefit                         (0.03)
= Non-GAAP diluted EPS                          0.83     Source: Q2 FY26 release, 2026-09-30
```

- Use the **company's own bridge**. Do not assemble your own add-back list and call the
  result "adjusted" — that is our estimate, and it must be labelled as one.
- **Compare like with like.** Adjusted actual against adjusted consensus; GAAP against GAAP.
  If the consensus basis is unknown, say so and give both.
- **Stock-based compensation is a real cost.** If the company adds it back, note it; if the
  buyback offsets the dilution, that is a share-count fact, not a reason to ignore it.
- **A recurring add-back is suspect.** An item excluded every quarter is an operating cost
  with a different name. Say so, and show how the conclusion changes if it is expensed.
- **Name every one-timer** in the quarter, with its size and its line, whether or not the
  company excluded it. A gain left in the base inflates the run-rate.
- Adjusted figures are not audited. Nothing in a non-GAAP table is tied to a signed audit.

Watch for these adjustments that change the *shape* of the result rather than its level:
capitalised software, channel inventory financing, bill-and-hold, gross-vs-net presentation,
constant-currency framing, and the FX rate chosen for "constant currency".

## Consensus

The platform has **no licensed consensus feed**. Consensus comes from one of:

| Source | Notes |
|---|---|
| The user's own export (Bloomberg/FactSet/LSEG) | best; ask for it and use its vintage |
| A public aggregator page found with `web_search` | cite the site and its own as-of date; aggregators lag and mangle bases |
| Real-time quote screens | use it as context, not as the bar for a beat |
| `yfinance` (`earnings_estimate`, `revenue_estimate`, `eps_trend`, `eps_revisions`) | a Yahoo aggregate of contributing brokers — a proxy, not the official Street number |

Rules: use the **pre-print** consensus and say when it was taken; never score a beat against
an estimate that was already updated with the news; if consensus is unavailable, write "no
consensus available" and compare against guidance and the prior-year quarter instead; note
when the consensus EPS basis (GAAP vs adjusted) is unknown; and record how many analysts
contribute, because a two-analyst "consensus" for a small cap is a different object from a
twenty-five-analyst one.

## Period conventions

- Use the company's fiscal label as the company uses it, and name the calendar period once:
  "NKE FY26 Q2 (Sept–Nov 2025)". After that, `Q2 FY26` is unambiguous.
- Retail and some industrials run 52/53-week and 4-5-4 calendars; a 53-week year is not
  comparable to a 52-week year without saying so.
- `YoY` and `QoQ` are different comparisons; label every change. Sequential comparisons in a
  seasonal business are noise — say so rather than reporting a QoQ decline as deterioration.
- `LTM`/`TTM` is four reported quarters, not the last fiscal year; state the stub.
- `NTM` is a forward blend, not a year; state the periods blended.
- Banks and utilities set their own quarter boundaries; do not assume a calendar quarter.

## Sector KPIs — the metrics that decide the print

Pick the five to eight that the sector's investor actually trades on, and put them in the
results table beside revenue and EPS. A print judged on the wrong metric is a note nobody
uses.

| Sector | KPIs |
|---|---|
| Software / SaaS | ARR, net revenue retention, cRPO/RPO, billings, remaining performance obligations, magic number, USD-based NRR assumptions |
| Internet / marketplaces | GMV, take rate, MAUs/DAU, ARPU, buyer frequency |
| Retail / consumer | same-store sales, traffic, ticket, e-commerce mix, inventory per store, promotional intensity |
| Industrials | orders, backlog, book-to-bill, price vs volume, aftermarket mix |
| Semis / hardware | bookings, utilisation, ASP, inventory days, capex intensity, lead times |
| Banks | NIM, deposit beta, loan growth, net charge-offs, provision coverage, CET1, efficiency ratio |
| Insurers | combined ratio, reserve development, book value per share, investment yield |
| Asset managers | AUM, net flows, fee rate, performance fees, run-rate cost |
| Energy | production, realised price, lifting cost, capex, reserve replacement, breakevens |
| REITs | FFO/AFFO per share, same-store NOI, occupancy, leasing spreads, weighted average cost of debt |
| Healthcare / pharma | scripts, patient volumes, price vs volume, R&D as % of sales, pipeline readout dates |
| Telco / cable | net adds, churn, ARPU, service revenue growth, capex-to-sales |
| Utilities | rate base growth, allowed ROE, load growth, capex plan, regulatory docket timing |
| Transport | volume, yield per unit, load factor, capacity, unit cost ex-fuel |

KPIs are company-specific more often than sector-specific. Read the 10-K's MD&A and the last
two transcripts: the metric management volunteers first is usually the one the stock trades on.

## Charts

matplotlib, `Agg` backend, PNG written to `/workspace/outputs/`. Every chart carries:

- a numbered caption above (`Figure 3 — Revenue by segment, last eight quarters`);
- a source line below (`Source: 10-Qs filed 2025-11-01 through 2026-09-30`);
- an axis label with the unit on both axes, and the period label on the x-axis;
- one scale per pane — if two series need different scales, two panes, not a second axis
  nobody reads;
- the same period window across charts that will be read together.

Charts that earn their place in an earnings note: quarterly revenue progression, margin
trend, segment mix, actual-vs-consensus by metric, estimate revision old-vs-new. A chart that
re-plots a table the reader just read is filler; delete it. For styled slides, hand off to
`ppt-generation`.

## When a figure is missing

Do not estimate silently, and do not project a metric from a ratio and present it as
reported. In order:

1. **Look harder** — the segment note, the MD&A, the deck, the transcript Q&A, the prior
   filing's restated comparative. Many "missing" figures are disclosed one document away.
2. **Say it is missing**, in the note, with what you would need: "segment margin not
   disclosed; the 10-Q reports it only at the consolidated level."
3. **If an estimate is genuinely useful**, label it `our estimate`, show the method in one
   line, and keep it out of any table of reported figures. Never mix it into a factual table.
4. **Never round away the ambiguity** — "~$1.2B" when the filing says `$1,187.4M` is a
   fabrication of precision in reverse; use the reported figure.
