# Buyer list and deal tracker

Two `.xlsx` deliverables that stay alive through the process. Both are exported as a single
workbook with a tab per view, plus a `.csv` of the flat table when the user needs to load it
into a CRM.

## Buyer list / buyer universe

Thirty to forty well-argued names beat two hundred collected ones. A name with no fit
rationale and no contact path is not a row — it is a note. If the seller has asked for
exclusions, apply them before the list is shown to anyone.

One row per buyer, one sheet for strategics, one for financial sponsors, one contact map for
Tier 1. Columns, in this order:

| Column | Content | Notes |
|---|---|---|
| Tier | `1` / `2` / `3` | 1 = contact first wave (5–10), 2 = second wave (10–15), 3 = broaden if needed |
| Buyer | legal name | the acquirer, and for a sponsor add-on, the platform's name |
| Type | one of the fixed vocabulary below | drive the filter with it |
| Sector / focus | what they do, one phrase | |
| Size | revenue or AUM / fund size | band it if the exact figure is unknown |
| Strategic fit | **one sentence of rationale** | the column that justifies the row |
| Fit score | High / Medium / Low | the sort key within a tier |
| Capacity | can they write the cheque — balance sheet, leverage headroom, fund size | note if the last deal was large |
| M&A history | Active / Moderate / None, with the most recent relevant deal | buyers mid-integration may be tapped out |
| Antitrust flag | Yes / No / Watch | direct competitors in a concentrated market |
| Relationship | Existing / Warm / Cold / None | who at the firm, if anyone |
| Contact path | named person, title, and how to reach them or who introduces | never just "corp dev" |
| Outreach date | date the teaser or letter went out | blank until sent |
| NDA date | execution date | blank until signed |
| Status | fixed vocabulary below | the live field |
| Next action | the specific next step and its owner | |
| Notes | feedback, constraints, what they said and when | |

**Buyer type vocabulary** — pick one per row and keep it fixed, because it drives the filter
and the summary counts: `Direct competitor`, `Adjacent player`, `Vertical integrator`,
`Platform builder`, `Sponsor — platform`, `Sponsor — add-on`, `Growth equity`,
`Family office / strategic individual`, `International strategic`.

Which rationale fits which type:

- **Direct competitor** — share, scale, remove a competitor.
- **Adjacent player** — product extension, cross-sell, new geography.
- **Vertical integrator** — a customer or supplier taking control of the chain.
- **Platform builder** — a tuck-in that fills a capability gap.
- **Sponsor — platform** — fund seeking a new platform in the sector; check fund vintage and
  deployment pace, because a fund late in its investment period behaves differently.
- **Sponsor — add-on** — name the **specific portfolio company** and the synergy; an add-on
  row without a portfolio company named is an unverified guess.

**Tiering.** Tier 1 is argued on fit × capacity × likelihood, not on size. A buyer with a
perfect fit and no cash is Tier 3.

**Keeping it live.** Buyers move between tiers as feedback arrives; do not rebuild the list,
edit the rows. Record what a buyer said and when — patterns in the declines ("too small",
"wrong geography", "process too fast") change the story, the price expectations, or the
timetable, and none of that is visible from a status column alone.

## Deal tracker

One row per deal in the pipeline tab; one tab of milestones per live deal; one master action
list. Stage vocabulary, in order, so a pipeline view can be sorted and summed:

`Pre-mandate → Engaged → Marketing → IOI → Diligence → Final bids → Signing → Regulatory → Closed`

(plus `On hold` and `Dead — archived`; archive dead deals off the active view rather than
deleting them.)

**Pipeline tab columns:** deal code name, client, side (sell-side / buy-side / financing /
restructuring), our role (lead / co-advisor / fairness opinion), sector, expected enterprise
value, stage, probability of close, team (MD, VP, associate, analyst), engagement date, next
milestone and its date, and a one-line status note.

**Milestones tab** — target date, actual date, status, note, one row per milestone:

- Engagement letter signed · buyer list approved · teaser distributed · NDA executed ·
  CIM distributed · IOI deadline · IOIs received and reviewed · shortlist selected ·
  management meetings held · data room opened · final bid deadline · bids received and
  reviewed · exclusivity granted · confirmatory diligence complete · purchase agreement
  signed · regulatory approval · close.

Status vocabulary, identical in every tab: `Not started`, `On Track`, `At Risk`, `Delayed`,
`Complete`.

**Action list columns:** action, deal, owner, due date, priority (`P0` / `P1` / `P2`),
status (`Open` / `Done` / `Blocked`), and what it is blocked on. An action without an owner
and a due date does not get done — it gets discussed at the next meeting instead.

**Weekly review.** For each live deal: one-line status, what moved this week, milestones in
the next two weeks, blockers, next week's actions. Then the pipeline view: count and value by
stage, deals where a milestone date has passed without the milestone, and expected closings
this quarter. Lead the summary with the overdue items — a tracker that only reports what is
on schedule is not being read carefully.

**Dates are dates.** Write them as real dates (`datetime.date`) into the workbook, not as
strings, so sorting and filtering work. Where a date is unknown it stays blank; a guessed
date becomes a missed deadline everyone believed in.

## Building both with openpyxl

```python
import io, runtime
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

wb = Workbook()
ws = wb.active; ws.title = "Buyer list"
header = ["Tier", "Buyer", "Type", "Sector / focus", "Size", "Strategic fit", "Fit score",
          "Capacity", "M&A history", "Antitrust flag", "Relationship", "Contact path",
          "Outreach date", "NDA date", "Status", "Next action", "Notes"]
ws.append(header)
for cell in ws[1]:
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4472C4")
    cell.alignment = Alignment(vertical="center", wrap_text=True)
ws.freeze_panes = "C2"                       # keep Tier + Buyer visible
ws.auto_filter.ref = ws.dimensions
wide = {"F": 60, "Q": 50}                    # the two prose columns
for i, name in enumerate(header, start=1):   # never leave a column at default width
    col = get_column_letter(i)
    ws.column_dimensions[col].width = wide.get(col, max(18, len(name) + 4))
dv = DataValidation(type="list", formula1='"Tier 1,Tier 2,Tier 3"', allow_blank=False)
ws.add_data_validation(dv)
dv.add(f"A2:A{max(ws.max_row, 2)}")          # max(...,2): an empty list is still a valid range
buf = io.BytesIO(); wb.save(buf)
runtime.fs.write_file("/workspace/outputs/project-atlas-buyer-list.xlsx", buf.getvalue())
```

The same conventions apply to the tracker: bold frozen header row, autofilter on, real date
formats (`cell.number_format = "yyyy-mm-dd"`) for date columns, data validation on Stage,
Status, Priority, and Tier so the vocabulary cannot drift, and one width set per column.
Print a `Summary` tab first — counts by tier and by type, count and value by stage — and keep
the argument (fit rationale, contact path) in the same row as the name, never in a separate
notes document.
