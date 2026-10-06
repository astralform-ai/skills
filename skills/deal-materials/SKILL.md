---
name: deal-materials
description: "Draft and assemble M&A process documents as deliverable files — confidential information memorandum (CIM), anonymous blind teaser, process letter and bid instructions (IOI round, final bid round, management meeting invite), buyer universe / buyer list, deal tracker and weekly deal review, management presentation outline, and data room / datapack structure. Use when the user asks to draft a CIM or offering memorandum, write a teaser or one-pager for a process, prepare IOI or final-bid instructions, build or tier a buyer list, track live deals, milestones or pipelines, outline a management presentation, or organize a data room. Trigger on 'sell-side materials', 'info memo', 'Project [code name]', 'who would buy this', 'bid procedures', 'deal status', 'weekly deal review', 'buyer universe'. Produces .docx, .md, .xlsx and .csv; every document is staged for human sign-off — nothing is sent, hosted, or published."
display_name: Deal Materials
version: "1.0.0"
author: Astralform
---

# Deal Materials

Write the process documents that sit around a transaction — the memorandum, the teaser,
the letters, the buyer list, the tracker. Deliver them as files the deal team can edit.

## What runs where

| Surface | How you reach it | What it does |
|---|---|---|
| `runtime_run_code` | tool call | runs Python in the sandbox — where every file is built |
| `runtime.fs.*`, `runtime.proc.*`, `runtime.web.*` | inside that code (`import runtime`) | sandbox files, processes, HTTP |
| `export_file` | tool call | publishes a `/workspace/outputs/` file to the user |
| `web_read` | tool call | reads a filing, a website, or a public document |

`python-docx` 1.1.2, `openpyxl` 3.1.5, `jinja2`, `lxml`, `pandas` are baked in the runner
image — no install. Write deliverables with `runtime.fs.write_file`, never `open()` into
`/workspace/outputs/`:

```python
import io, runtime
from docx import Document

doc = Document()
# ... every section built from the fact sheet ...
buf = io.BytesIO(); doc.save(buf)
runtime.fs.write_file("/workspace/outputs/project-atlas-cim.docx", buf.getvalue())
```

Then call `export_file(path="/workspace/outputs/project-atlas-cim.docx",
name="Project Atlas - CIM.docx")`. Keep the builder script under `/workspace/` so a
redline is an edit-and-rerun, not a rewrite.

There is **no Word or Excel engine in the sandbox**: nothing here evaluates a formula,
pagination, or a rendered layout. Figures you quote in chat are Python numbers that you
computed yourself; the document's own table of contents and page numbers are filled in
when the user opens the file.

## Boundaries — state these to the user

- **Numbers come from somewhere else.** They come from the user's data room, from a model
  built with the **`financial-modeling`** skill, or from a sourced filing. This skill
  assembles and writes documents; it never invents a projection, a multiple, or a margin.
- **Decks go to `ppt-generation`.** A styled slide deck, with imagery and a theme, is that
  skill's job. The buyer list, deal tracker, and datapack tables are this skill's job, in
  `.xlsx` / `.csv`.
- **Public data comes from `yfinance`** (comps, market caps) and **`web_read`** (filings).
  PDF extraction is the **`pdf`** skill. Export mechanics are the **`export`** skill.
- **Everything is staged for human sign-off.** You produce drafts. You do not send, host,
  or publish anything, and you do not generate a public link — `export_file` returns a link
  authenticated as the user, not a URL that can be forwarded or embedded. Say so once, and
  never describe a draft as distribution-ready: legal, the client, and management sign off
  before a document leaves the room.

## The one rule: the fact sheet comes first

**Never type a number into prose.** A CIM that says "$42.1M revenue" in the executive
summary, "$42.3M" in the financial overview, and "$42.1M" in the appendix is worse than an
incomplete one — it destroys credibility in the first diligence call.

1. **Gather.** Data room files and attachments, the user's own inputs, public filings via
   `web_read`. Read what you were given before asking for anything.
2. **Build the fact sheet** at `/workspace/facts.json` — every figure once, with its unit,
   period, and source:

```json
{
  "currency": "USD", "units": "thousands",
  "facts": [
    {"id": "rev_fy24", "label": "Net revenue FY2024", "value": 42100,
     "unit": "USD thousands", "period": "FY2024", "source": "audited FS p.14", "basis": "actual"},
    {"id": "rev_fy25", "label": "Net revenue FY2025", "value": 47300,
     "unit": "USD thousands", "period": "FY2025", "source": "management budget",
     "basis": "management case"}
  ]
}
```

3. **Lock it.** Print the sheet back to the user in one short block, flag every conflict
   (two sources, two numbers) and every gap, and get agreement before writing prose.
4. **Write from the sheet.** Documents are generated from `facts.json` with a `jinja2`
   template or f-strings — a figure appears exactly once in your code, so it cannot drift.
5. **Re-check.** Run `{baseDir}/scripts/check_deal_doc.py` (below) before exporting.

Every projection carries its basis label. `actual`, `management case`, `sponsor case`,
`pro forma` are not decoration: a reader must be able to tell what happened from what is
hoped for, and no projection may be described as committed, guaranteed, or achieved.

## Document set

| Deliverable | Format | Reference | Sign-off before it moves |
|---|---|---|---|
| CIM / information memorandum | `.docx` (plus a `.xlsx` financial appendix) | `{baseDir}/references/documents.md` | client, management, legal |
| Anonymous teaser / blind profile | `.docx`, one page | `{baseDir}/references/documents.md` | client, legal |
| Process letter / bid instructions | `.docx` | `{baseDir}/references/documents.md` | client, legal |
| Management presentation outline | `.md` or `.docx` | `{baseDir}/references/documents.md` | management |
| Buyer list / buyer universe | `.xlsx` (+ `.csv` for the CRM import) | `{baseDir}/references/buyer-list-and-tracker.md` | client (exclusions!) |
| Deal tracker / pipeline review | `.xlsx` (+ `.md` summary) | `{baseDir}/references/buyer-list-and-tracker.md` | deal team |
| Datapack / data room index | `.xlsx` index (+ `.csv` per tab) | `{baseDir}/references/documents.md` | deal team |

Deliver `.docx`: it is the working copy the client marks up and sends back. There is no
document converter in the sandbox, so do not promise a PDF output — if the user needs one,
say the `.docx` is what you can produce and they convert it.

## Building the documents

Detail and full snippets live in `{baseDir}/references/authoring.md`; the conventions that
decide whether the file looks professional are:

- **Styles, never inline formatting.** Set `Normal`, `Heading 1`, `Heading 2`, `Table Grid`,
  `Quote`, and use `doc.add_heading(..., level=n)` so the table of contents and the outline
  pane work. A run-level bold-and-28pt title is what makes a generated document look
  generated.
- **Financial tables carry their units and periods in the header row** — `$M unless noted`,
  `FY2023A`, `FY2025E`. A column of bare numbers is unusable.
- **State the currency once.** `$` lives in the units header, not on every figure.
  Negatives in parentheses, never a trailing minus sign.
- **Header and footer on every page**: deal code name, document type, `Private and
  Confidential`, and a `PAGE` field. python-docx writes the field; Word fills it.
- **No orphan headings.** A heading is followed by content, not by another heading.
  `check_deal_doc.py` fails the file when it finds one.
- **Masked content is marked, not blanked.** A redacted customer is `Customer A (Fortune
  500 industrial)`, never an empty cell or a run of `XXXX`.

```python
doc.add_heading("III. Investment Highlights", level=1)
doc.add_paragraph(
    "Net revenue grew at a 22% CAGR from FY2022 to FY2024, reaching "
    f"${money_m(facts['rev_fy24'] / 1000)}M, while gross margin expanded 410 bps."
)  # money_m() and facts[...] are the locked sheet read once — the figure exists once
```

## Structural check before delivery

```bash
python {baseDir}/scripts/check_deal_doc.py /workspace/outputs/project-atlas-cim.docx \
    --facts /workspace/facts.json --name "Atlas Holdings"
```

It reads the `.docx` (or a `.md`) and reports: headings that jump a level or sit empty,
placeholder text (`TBD`, `XXX`, `[insert`, `{{`), numeric tables whose header row states no
unit, numbers in prose that do not trace back to the fact sheet, and — with `--name` /
`--forbid` — identity leaks in blind materials. Non-zero exit on any error. Fix what it
reports; it is a structure check, not a proof that the document is correct.

## Failure modes seen repeatedly

| Symptom | Cause | Fix |
|---|---|---|
| The same metric differs between two sections | a number typed twice, once per section | every figure from `facts.json`; `check_deal_doc.py --facts` catches the drift |
| Teaser identifies the company | a brand name, a city, a distinctive employee count, a logo, or a URL | run the anonymity check; use region not city, range not exact headcount, and no customer names |
| A projection reads as a promise | `will achieve`, `committed`, `guaranteed` next to a forecast | label the basis (`management case`) and use `is projected to` / `management forecasts` |
| "Indicative" used where the user meant committed | the process letter copied last round's language | ask which round this is and whether the price is binding before writing a word of it |
| Buyer list with no rationale column | names collected, fit never argued | every row carries a one-line fit rationale and a contact path, or it does not belong on the list |
| CIM contradicts the model it was built from | model revised after the memo was written | rebuild the document from the revised fact sheet; never patch prose in place |
| Tracker stale, milestones slipping silently | tracker updated only when someone asks | due dates plus a Status column; the weekly view leads with overdue items |
| Word shows a repair prompt | merged cells written off the anchor, or a raw control character in a run | merge after writing the top-left cell; strip control characters from sourced text |
| Numbers off by 1000× | units row not carried through | declare units once in the fact sheet and print them in every table header |

## Delivery

- Name files for the deal and the document: `project-atlas-cim-v3.docx`,
  `project-atlas-buyer-list.xlsx`, `project-atlas-deal-tracker.xlsx`.
- Version the draft in the file name; never overwrite a version the client has already seen.
- In the reply state: what the document is, which figures are actuals versus management
  case, which sources were used, every gap you could not fill, and that it is a draft
  awaiting sign-off. Do not describe a draft as ready to distribute.
