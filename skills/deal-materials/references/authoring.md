# Authoring the files

The mechanics that make a generated `.docx` or `.md` look like it was produced by a deal
team, and the helper patterns that keep figures consistent.

## python-docx

**Styles, never inline runs.** Set the document's defaults once, then use the built-in style
names. `add_heading(text, level=n)` maps to `Heading n`, which is what builds the navigation
pane and any outline Word exports. A title assembled from a bold 28pt run gives you a
document with no structure.

```python
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()
for section in doc.sections:
    section.top_margin = section.bottom_margin = Inches(0.9)
    section.left_margin = section.right_margin = Inches(1.0)

normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(8)

doc.add_heading("Project Atlas — Confidential Information Memorandum", level=0)
p = doc.add_paragraph("Private and Confidential — prepared for discussion purposes only.")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
```

**Header and footer on every page** — deal code name on the left, document type on the right,
page number as a field. python-docx writes the field instruction; Word resolves it on open,
so the footer reads correctly in the file the user receives and is not a number you typed.

```python
def page_field(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    sep = OxmlElement("w:fldChar"); sep.set(qn("w:fldCharType"), "separate")
    result = OxmlElement("w:t"); result.text = "1"      # cached until Word recalculates
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, sep, result, end):
        run._r.append(el)

for section in doc.sections:
    section.header.paragraphs[0].text = "Project Atlas — Confidential Information Memorandum"
    footer = section.footer.paragraphs[0]
    footer.text = "Private and Confidential    |    "
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    page_field(footer)
```

**Financial tables.** Units and periods live in the header row; the header row repeats on a
page break; column widths are set explicitly so a table does not wrap into unreadability.

```python
def financial_table(doc, header, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, header):
        cell.text = str(text)
        for run in cell.paragraphs[0].runs:
            run.bold = True
    trPr = table.rows[0]._tr.get_or_add_trPr()
    header_flag = OxmlElement("w:tblHeader"); header_flag.set(qn("w:val"), "true")
    trPr.append(header_flag)
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = str(value)
            if isinstance(value, str) and (value.startswith("$") or value.startswith("(")):
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if widths:
        for row in table.rows:
            for cell, width in zip(row.cells, widths):
                cell.width = Inches(width)
    return table

financial_table(
    doc,
    ["$M unless noted", "FY2023A", "FY2024A", "FY2025E", "CAGR"],
    [["Net revenue", "34.5", "42.1", "47.3", "17.1%"],
     ["Gross profit", "13.1", "17.4", "20.1", "23.9%"],
     ["Adjusted EBITDA", "6.9", "9.8", "12.0", "31.9%"],
     ["EBITDA margin", "20.0%", "23.3%", "25.4%", "—"]],
    widths=[2.4, 1.0, 1.0, 1.0, 1.0],
)
```

Unit rules: state `$M unless noted` (or `$000s`) in the top-left cell and never repeat the
currency symbol on individual figures; negatives in parentheses; percentages with one
decimal; multiples with an `x` suffix; `A` for actual, `E` for estimate, `P` for pro forma in
every period header. Left-align labels, right-align numbers, indent sub-items with two
spaces.

**Merging.** A merged cell must already hold its text before the merge; merging over empty
cells is what makes Word offer to repair the file.

```python
table = doc.add_table(rows=2, cols=3)
table.cell(0, 2).text = "Guidance"      # write first
table.cell(0, 0).merge(table.cell(0, 2))
```

**No orphan headings.** Wrap the pattern so it cannot happen:

```python
def section(doc, heading, body, level=1):
    if not body or not body.strip():
        raise ValueError(f"refusing to write orphan heading: {heading}")
    doc.add_heading(heading, level=level)
    return doc.add_paragraph(body)
```

**Strip what the source gave you.** Sourced text carries control characters, non-breaking
hyphens, and zero-width joiners that survive into the file and occasionally trigger a repair
prompt:

```python
import re, unicodedata
def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b-\u200f\u2028\u2029]", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()
```

**Clear the file properties.** The default core properties carry the sandbox user and title;
in a blind process that is a leak, and in any process it is sloppy:

```python
props = doc.core_properties
props.author = "Astralform"
props.last_modified_by = "Astralform"
props.title = "Project Atlas — Confidential Information Memorandum"
props.comments = ""
```

## Figures come from the fact sheet, not from the prose

Read the locked sheet once and format through helpers, so the same metric cannot be written
two ways in one document:

```python
import json
facts = {f["id"]: f["value"] for f in json.load(open("/workspace/facts.json"))["facts"]}

def money_m(v, decimals=1):          # v is already in the fact sheet's unit
    s = f"{abs(v):,.{decimals}f}"
    return f"({s})" if v < 0 else s

def pct(x, decimals=1): return f"{x * 100:.{decimals}f}%"
def mult(x, decimals=1): return f"{x:.{decimals}f}x"
```

Prose states the number and its basis; the appendix states the detail. A sentence that
carries a forward-looking figure says which case it is:

- `Net revenue grew at a 17% CAGR from FY2022 to FY2024 to $42.1M.` — actual.
- `Management forecasts net revenue of $47.3M in FY2025 (management case).` — labeled.
- Never: `the business will reach`, `revenue is expected to be committed at`, `guaranteed`.
  Preferred: `is projected to`, `management forecasts`, `the management case assumes`.

**Every number you quote in chat is computed in Python**, from the same fact sheet, in the
same run that built the document. There is no renderer in the sandbox and no formula engine:
nothing here reads back a total the user's Word or Excel will show, so never report a figure
you did not compute.

## Markdown deliverables

A management presentation outline or a weekly deal review does not need Word styles. Write
`.md` — a heading per section, a table where a table is the right shape, plain `-` bullets —
and keep the same discipline as the `.docx`: figures from the fact sheet, units in table
headers, no placeholder left in the file.

```python
runtime.fs.write_file("/workspace/outputs/project-atlas-weekly-review.md", md)
```

## Naming and versioning

`project-<codename>-<document>[-v<n>].<ext>` — lower-case, hyphens, no spaces, no target name
in a blind process:

```
project-atlas-teaser.docx
project-atlas-cim-v3.docx
project-atlas-buyer-list.xlsx
project-atlas-deal-tracker.xlsx
project-atlas-financial-appendix.xlsx
```

Increment `v<n>` on a revision that has been seen by anyone outside the deal team; never
overwrite a version the client has already circulated. Pass the same name to `export_file`'s
`name=` — that is the display name the user sees, so it can be the readable form
(`Project Atlas - CIM v3.docx`).
