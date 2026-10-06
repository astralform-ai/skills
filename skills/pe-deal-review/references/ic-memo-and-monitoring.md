# IC memo, value creation, portfolio monitoring

## IC memo — skeleton and content rules

The memo's job is to let a partner who did not work the deal make a decision and
then defend it. Order matters: recommendation first, evidence second, reservations
last but explicit.

| Section | Content | Rule |
|---|---|---|
| 1. Recommendation | Deal, size, structure, base-case MOIC/IRR, requested decision | One paragraph. State the number and the ask; never bury the recommendation |
| 2. Executive summary | What the company does, why now, the three reasons to proceed | Half a page, no adjectives that are not evidenced |
| 3. Investment thesis | 3–5 pillars, each tied to a diligence test and its result | A pillar with no test result is an aspiration — mark it open |
| 4. Company and market | Products, customers, GTM, competition, market size/growth | Cite sources; flag seller-provided data as such |
| 5. Financial analysis | 3–5 years of revenue/EBITDA/margin/FCF, QoE adjustments, working capital, capex | Every adjustment named and quantified; tie to the QoE report |
| 6. Deal terms and structure | EV and multiple, sources & uses, leverage, key legal terms | Sources = uses; state the entry leverage and year-1 coverage |
| 7. Returns | Base / upside / downside with MOIC and IRR, dated cash flows, sensitivity | Quote the calculator's output; state the conventions used |
| 8. Risks | Ranked, each with likelihood, severity, mitigant, and owner | No risk without a mitigant; no mitigant without an owner |
| 9. Diligence status | Complete / in progress / open per workstream, with what closes each | An item with no evidence is open |
| 10. Recommendation and conditions | Proceed / conditional proceed / pass, plus conditions precedent | Conditions must be verifiable before close |

Risk table format — the mitigant column is what makes it useful:

| # | Risk | Likelihood | Severity | Mitigant | Owner |
|---|---|---|---|---|---|
| 1 | Top-2 customer renewal | Medium | High | Renewal at 18 months signed pre-close as a condition | Deal lead |

Returns summary — one table, three scenarios, and a note of which assumption drives
the spread:

| Metric | Downside | Base | Upside |
|---|---|---|---|
| Entry multiple | | | |
| Exit multiple | | | |
| EBITDA CAGR | | | |
| Exit EBITDA | | | |
| Net debt at exit | | | |
| MOIC | | | |
| IRR | | | |

Conditions precedent are the IC's teeth: put each into the memo as a statement that
can be tested before funds move (contract signed, key hire employed, QoE item
resolved, carve-out completed).

Build the memo as a `.docx` with python-docx (baked in the image), or Markdown when
the reader wants to comment inline:

```python
import io, runtime
from docx import Document

doc = Document()
doc.add_heading("Investment Committee Memorandum — Project Titan", level=0)
doc.add_heading("1. Recommendation", level=1)
doc.add_paragraph("Proceed, subject to the conditions in section 10.")
# ... one add_heading per section, tables via doc.add_table ...
buf = io.BytesIO(); doc.save(buf)
runtime.fs.write_file("/workspace/outputs/titan-ic-memo.docx", buf.getvalue())
```

Then call the `export_file` tool with `path=` and `name=`. Tables in the memo must
tie to the calculator's output — recompute, never retype a number from memory.

## Value creation plan — the EBITDA bridge

The plan is an EBITDA bridge with owners, not a list of ideas. Every line has a
dollar figure, a start date, an investment, a confidence level, and one accountable
person.

| Lever | Y1 | Y2 | Y3 | Y4 | Y5 | Owner | Confidence |
|---|---|---|---|---|---|---|---|
| Base EBITDA (entry run-rate) | | | | | | | |
| Pricing / mix | | | | | | CRO | |
| Volume / new logos | | | | | | CRO | |
| Cross-sell / upsell | | | | | | CRO | |
| Add-on M&A | | | | | | Deal lead | |
| COGS / procurement | | | | | | COO | |
| Opex / shared services | | | | | | CFO | |
| Technology investment | | | | | | CTO | |
| **Pro-forma EBITDA** | | | | | | | |

Lever set: revenue (price, volume, cross-sell, new markets, sales effectiveness,
add-ons), margin (procurement, overhead, automation, scale), and strategic/multiple
(recurring-revenue mix, platform building, management upgrades). Multiple expansion
is an output, never a plan line — it is bought with the growth and quality the other
levers create.

**100-day plan**, by phase: days 1–30 stabilise and assess (management retention and
comp, quick wins, functional deep-dive, customer communication, KPI reporting live);
days 31–60 plan and initiate (strategy communicated, top 3–5 initiatives launched,
add-on pipeline started, critical hires); days 61–100 execute and measure (first
quick-win results, first board pack on operating metrics, adjust the plan).

Reality check before the plan is signed: most value creation takes 12–24 months to
show in the financials, so a plan whose value is entirely in years 4–5 is a plan for
the next owner. Quick wins earn credibility; do not fund growth by starving the
business of the cost base it needs to deliver.

## Portfolio monitoring — the KPI packet

Ingest the monthly/quarterly package and produce one page: an executive paragraph,
a KPI table against budget and prior period, flags, covenant status, and questions
for management.

| KPI | Actual | Budget | Var % | Prior period | Trend | Flag |
|---|---|---|---|---|---|---|
| Revenue | | | | | | |
| EBITDA | | | | | | |
| EBITDA margin | | | | | | |
| Net debt / LTM EBITDA | | | | | | |
| Interest coverage | | | | | | |
| Capex | | | | | | |
| Free cash flow | | | | | | |
| Operational KPIs (sector) | | | | | | |

Flag bands, applied consistently: **green** within 5% of plan; **amber** 5–15% below
plan, or a trend that will breach a covenant within two quarters; **red** more than
15% below plan, a covenant breach or imminent breach, or a key hire or customer
lost. Red goes to the deal lead immediately, with a recommended action — not in the
next scheduled pack.

Covenant headroom is a level, not a trend:

```
Leverage headroom   = covenant level − (net debt ÷ LTM EBITDA)
Coverage headroom   = (EBITDA ÷ cash interest) − covenant minimum
```

Use LTM EBITDA including permitted add-backs, and state the add-backs — a covenant
computed on a more generous EBITDA than the one you report is a false comfort.

Compare performance to the **underwriting case**, not only to budget: management
budgets are negotiated and drift; the model the IC approved is the promise being
tracked. Where the two diverge, say which one the KPI is being measured against.
