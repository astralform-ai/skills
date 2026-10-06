# Process documents — CIM, teaser, letter, management presentation, datapack

What each document contains, what it must never contain, and the order the sections go in.

## CIM / information memorandum

Length 40–60 pages of substance; enough for a first-round bid, short enough to be read.
Every claim carries a figure or a source. "Strong growth" is a sentence about the writer;
"revenue grew at a 22% CAGR from FY2022 to FY2024" is a sentence about the business.

| Section | Contains | Must NOT contain |
|---|---|---|
| Cover + disclaimer | deal code name, date, `Private and Confidential`, prepared-for and reliance wording | the target's legal name if the process is still blind |
| Table of contents | generated from Heading styles | page numbers typed by hand |
| I. Executive summary | what the business does in three sentences, 3–5 investment highlights, headline financials, what is being sold, indicative timeline | new figures that appear nowhere else in the document |
| II. Investment highlights | 5–7 distinct, evidence-backed points — market position, recurring revenue quality, margin profile, growth levers, management, strategic value | more than 7; the same point twice; adjectives without a number |
| III. Company overview | history, products and services, business model and revenue lines, sites and footprint, org and key personnel | forward projections; live customer names pre-NDA |
| IV. Market and industry | market size with a sourced basis, growth drivers, competitive map, regulation, barriers to entry | an unsourced TAM; a market study you have not read |
| V. Customers and sales | customer count and concentration, retention and churn, contract structure, pipeline and backlog, go-to-market | named customers unless the client has approved disclosure; a repeat-rate claimed without the definition |
| VI. Operations | facilities, headcount by function, systems, supply chain, capacity | headcount detail that deanonymizes a blind teaser's target |
| VII. Financial overview | historical income statement (3–5 years), revenue by segment/geography/customer type, EBITDA bridge, balance sheet and cash flow summaries, working capital, capex | a normalized EBITDA whose adjustments are not itemized |
| VIII. Projections basis | the management case, its drivers, and the assumptions it rests on | a forecast presented without its basis label; a projection described as committed |
| IX. Growth opportunities | organic levers, add-ons, operational improvements, white space | an opportunity with no owner, no cost, and no timing |
| X. Process and appendices | timetable, contact details, detailed financial statements, product catalogue, management bios | — |

**Where the financials come from.** Histories tie to the audited or reviewed statements;
a quality-of-earnings report, if one exists, overrides management's own adjustment view.
Normalization adjustments are presented as a bridge — reported EBITDA → each adjustment,
with its rationale — never as a single "adjusted EBITDA" line. Pro forma and run-rate
figures are labeled and the period they annualize is stated.

**The appendix is an Excel workbook**, one tab per statement, same units as the body.
Publish it alongside the `.docx` and say that the two are generated from the same fact sheet.

## Anonymous teaser / blind profile

One page. Its only job is to earn the NDA: a buyer who learns everything from the teaser
has no reason to sign. Six elements, in order:

1. **Deal code name and sector descriptor** — `Project Atlas`, `Leading provider of
   specialised industrial services in the Southeast US`. No `Private and Confidential`
   footer is a substitute for actually being blind.
2. **Company description**, 2–3 sentences: what it does, how it makes money, market position.
3. **Investment highlights**, 4–6 bullets: market position, revenue quality (recurring share,
   retention, diversification), growth profile, margin profile, management, strategic value.
4. **Financial summary table**: revenue, growth (CAGR), EBITDA, EBITDA margin, one operating
   metric. Ranges, not exact figures, when the sector is concentrated enough that exact
   numbers identify the company.
5. **Transaction overview**: what is offered (100% sale, majority, growth equity), indicative
   timetable, that expressions of interest go to the advisor.
6. **Contact block**: the advisor's name, firm, email, phone. Never the target's.

**Anonymity checklist — every item, every time:**

- No company, brand, product, or portfolio name.
- No city; region only (`Southeast US`, `DACH`, `Gulf Coast`).
- No named customer, supplier, or partner.
- No logo, screenshot, photograph, or document metadata that identifies the company
  (clear `doc.core_properties.author` and `last_modified_by` — python-docx writes your
  process user into the file).
- Employee count only if it does not single the company out; otherwise a band.
- No file name containing the target's name.
- No unique combination of facts: two individually harmless facts — exact revenue, exact
  headcount, exact site count, exact founding year — together identify a company.

Run `check_deal_doc.py --blind --name "<target>" --forbid "<brand>" --forbid "<city>"` and
fix every hit before the teaser goes anywhere.

## Process letter / bid instructions

Four letter types. Establish which one before writing; the round decides the language and
the binding status of the price.

| Type | Sent | Purpose |
|---|---|---|
| Initial process letter | with the teaser | process outline, NDA and data room access, how to express interest |
| IOI instructions | with the CIM | what a first-round indication must contain |
| Final bid letter | after management meetings | binding offer requirements |
| Management meeting invite | between rounds | logistics and agenda |

**Sections, in order:** date and deal code name; addressee; who is running the process and
on whose behalf; process overview (rounds, key dates); submission requirements; submission
mechanics (where, by when, in what format); confidentiality reminder referencing the NDA and
the data room rules; evaluation criteria; contact block.

**IOI requirements** — a bid that omits any of these comes back:

- Proposed enterprise value, stated as a range, with the basis (which EBITDA, which multiple).
- Consideration form and mix: cash, stock, earnout, seller note, rollover.
- Financing sources and their certainty — cash on hand, committed debt, equity draw.
- Confirmatory diligence required and an estimate of how long it takes.
- Indicative timeline from IOI to signing to close.
- Conditions and contingencies, including regulatory.
- A short description of the buyer and its strategic rationale for this asset.

**Final-round additions:** markup of the draft purchase agreement; committed financing
letters; remaining diligence items; exclusivity terms (duration, conditions); regulatory
filing analysis and its timetable; treatment of key personnel — employment agreements,
retention, rollover — and an explicit statement of **which parts of the submission are
binding and which are not**.

**Evaluation criteria are stated, not implied.** Say how bids will be judged and in what
order: price, certainty of financing, speed to close, regulatory risk, conditionality, and
treatment of employees. An undisclosed criterion is one buyers will not optimize for and
will later say was a moving target.

**Tone.** Deadlines are firm and specific (`5:00 pm ET on 14 November`) — never "within a
few weeks". Two to three weeks between rounds is normal; a compressed timetable is a
statement about the seller's urgency, so make it deliberate.

**Track circulation.** Every letter that leaves the process is recorded in the buyer list's
outreach columns with a date. The letter is the process record.

## Management presentation outline

An outline, not the deck — the deck is `ppt-generation`'s job. Structure it as a running
order with the owner of each section and the facts each one draws on:

1. Company overview and history — CEO
2. Products, services, and the value proposition — CEO / product lead
3. Market opportunity and competitive position — CEO
4. Customers, contracts, and retention — sales lead
5. Historical financials and drivers — CFO
6. The management case and its assumptions — CFO
7. Operations, capacity, and systems — COO
8. Organization and key personnel — CEO
9. Growth plan and its funding — CEO / CFO
10. Q&A and follow-up process — advisor

Ground rules to state once: no recording, attendees limited to those on the NDA, questions
in writing afterwards through the advisor so all bidders get the same answer.

## Datapack / data room index

The index is a `.xlsx` with one row per document and these columns: folder path, document
name, type (financial, legal, commercial, operational, HR), period covered, format, whether
redacted, who supplied it, date added, version. A stack of files without an index is not a
data room — bidders ask for a list that tells them what is missing.

Standard tab structure when the deliverable is a datapack rather than just an index:

1. Executive summary — business model, highlights, financial snapshot
2. Historical income statement — revenue by segment, costs, EBITDA, adjusted EBITDA bridge
3. Balance sheet
4. Cash flow statement
5. Operating metrics — volumes, units, customers, retention, by period
6. Segment / geography performance
7. Market analysis, with sources
8. Investment highlights, each tied to a figure

Rules that make a datapack usable: every number traces to a source document and page; each
tab names its unit and currency in the header; subtotals and totals are visibly derived
(Excel formulas, written by openpyxl) rather than typed; the same figure on two tabs is one
figure; and every adjustment is itemized with its rationale. Where a source was ambiguous,
say so in a Notes row instead of choosing silently.
