#!/usr/bin/env python3
"""Audit a draft equity-research note for data-discipline defects.

Checks a markdown note for the mistakes that send research back for a rewrite:
placeholders left in, no as-of date, tables with no ``Source:`` line, numeric
claims with no source or no period, chart captions with no source, and estimate
table headers that do not mark estimates (E) versus actuals (A).

Usage:
    python3 check_note.py NOTE.md
    python3 check_note.py NOTE.md --json
    python3 check_note.py NOTE.md --strict

Exit codes:
    0  no blocking findings
    1  blocking findings (any ERROR, or any WARN under --strict)
    2  usage or I/O error

Severity: ERROR blocks delivery (placeholder, missing as-of date, unsourced
table, malformed table). WARN is an editor's question (unsourced or
unperiodised inline number, unlabelled figure, unmarked FY column, no Sources
section in a document long enough to need one). Findings are to be fixed or
consciously dismissed; the checker is a first pass, not a gate on prose.

The top-of-note block before the first heading is document metadata (rating,
price with its price-date, price-target bridge) and is exempt from the inline
numeric-claim rules, as is a threshold clause ("if gross margin is below
41.5%" — our own trigger, not a reported figure). A table is sourced only by a
``Source:`` line in the four lines below it. Lines inside fenced code blocks are
ignored entirely.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ERROR = "ERROR"
WARN = "WARN"

# A line is "sourced" if it names a document, dataset or basis.
SOURCE_RE = re.compile(
    r"source|10-[kq]\b|8-k\b|20-f\b|def 14a|proxy|earnings release|press release"
    r"|transcript|our estimate|our forecast|company (?:data|reports|filings|disclosure|estimates)"
    r"|filed|https?://|\[\d+\]|per (?:the )?(?:company|10-|8-|release|deck|filing|model)"
    r"|investor (?:deck|presentation)|consensus|as reported|company-disclosed|guidance issued",
    re.IGNORECASE,
)

# A line "carries a period" if it names a quarter, year, month or trailing window.
PERIOD_RE = re.compile(
    r"\b(?:q[1-4]\b|\d{1,2}q\d{2}\b|fq\d\b|fy\s?\d{1,4}[EA]?\b|h[12]\b|\d{4}\b"
    r"|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?"
    r"|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r"|yoy|qoq|ytd|ltm|ttm|ntm|as of|quarter|year[- ]to[- ]date)\b",
    re.IGNORECASE,
)

# A line makes a numeric claim if it carries money, a percent, a multiple,
# basis points, a thousands-separated figure or a bn/million-scale figure.
NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:bn|billion|mm|mn|million|trillion)\b|\s?(?:k|m|b)\b)?"
    r"|\d+(?:\.\d+)?\s?%"
    r"|\b\d+(?:\.\d+)?\s?x\b"
    r"|\bbps?\b"
    r"|\b\d{1,3}(?:,\d{3})+\b"
    r"|\b\d+(?:\.\d+)?\s?(?:bn|billion|million|mm|mn)\b",
    re.IGNORECASE,
)

PLACEHOLDER_RE = re.compile(
    r"\b(?:TODO|TBD|TKTK|FIXME)\b|lorem ipsum|<insert\b|\[insert\b|\[\s*\]|<\s*[a-z][a-z _-]{2,}\s*>|\bXXX+\b",
    re.IGNORECASE,
)

DATE_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    re.IGNORECASE,
)

HEADING_RE = re.compile(r"^#{1,6}\s")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|^\s*(?:figure|fig\.?|exhibit)\s*\d", re.IGNORECASE)
# A column that is *just* a fiscal-year label must say whether it is an estimate
# or an actual; "Prior guide (Q1 FY26 release)" is a label, not a period column.
FY_ONLY_RE = re.compile(r"^[\*\s]*FY\s?\d{2,4}[\*\s]*$", re.IGNORECASE)
FY_MARK_RE = re.compile(r"\d\s?[EA]\b")
# A threshold clause ("if gross margin is below 41.5%") states our own trigger,
# not a reported figure, so it is exempt from the unsourced-claim rule.
THRESHOLD_RE = re.compile(r"\b(?:if|unless|threshold|trigger|below|above)\b", re.IGNORECASE)
SOURCES_HEADING_RE = re.compile(
    r"^#{1,6}\s*(?:sources|references|sources\s*(?:&|and)\s*references)\b", re.IGNORECASE
)


@dataclass
class Finding:
    level: str
    line: int
    rule: str
    message: str


def mask_fences(lines: list[str]) -> list[bool]:
    """True for lines that are inside (or are) a fenced code block."""
    inside = False
    mask = []
    for line in lines:
        if FENCE_RE.match(line):
            inside = not inside
            mask.append(True)
            continue
        mask.append(inside)
    return mask


def find_tables(lines: list[str], masked: list[bool]) -> list[tuple[int, int, int | None]]:
    """Return (start, end, header_index) 0-based inclusive table spans."""
    tables = []
    i = 0
    while i < len(lines):
        if masked[i] or not TABLE_ROW_RE.match(lines[i]):
            i += 1
            continue
        start = i
        while i + 1 < len(lines) and not masked[i + 1] and TABLE_ROW_RE.match(lines[i + 1]):
            i += 1
        end = i
        if end - start + 1 >= 2:
            header = None
            for k in range(start, end + 1):
                if TABLE_SEP_RE.match(lines[k]):
                    header = k - 1 if k - 1 >= start else None
                    break
            tables.append((start, end, header))
        i += 1
    return tables


def table_is_sourced(lines: list[str], start: int, end: int) -> bool:
    """A table is sourced if a Source line follows it, the convention in the skeletons."""
    window = lines[end + 1 : end + 5]
    return any(SOURCE_RE.search(line) for line in window)


def check(path: Path, min_lines: int) -> tuple[list[Finding], str | None]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    masked = mask_fences(lines)
    tables = find_tables(lines, masked)

    in_table: set[int] = set()
    for start, end, _ in tables:
        in_table.update(range(start, end + 1))

    first_heading = next(
        (i for i, line in enumerate(lines) if HEADING_RE.match(line) and not masked[i]), len(lines)
    )

    findings: list[Finding] = []

    # --- document-level: as-of stamp -------------------------------------
    as_of = None
    for i, line in enumerate(lines):
        if masked[i]:
            continue
        if re.search(r"\bas of\b", line, re.IGNORECASE):
            as_of = line.strip()
            break
        if i < 15:
            m = DATE_RE.search(line)
            if m:
                as_of = m.group(0)
    if as_of is None:
        findings.append(
            Finding(
                ERROR,
                1,
                "no-as-of-date",
                'no "as of <date>" stamp and no date in the first 15 lines; stamp the note and its prices',
            )
        )

    # --- document-level: sources section ---------------------------------
    has_sources = any(
        SOURCES_HEADING_RE.match(line) for i, line in enumerate(lines) if not masked[i]
    )
    if not has_sources and len(lines) >= min_lines:
        findings.append(
            Finding(
                WARN,
                1,
                "no-sources-section",
                'no "Sources"/"References" section; list the documents and their dates',
            )
        )

    # --- per line ---------------------------------------------------------
    for i, line in enumerate(lines):
        if masked[i]:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        lineno = i + 1

        if PLACEHOLDER_RE.search(stripped):
            ph = PLACEHOLDER_RE.search(stripped)
            findings.append(
                Finding(
                    ERROR,
                    lineno,
                    "placeholder",
                    f'placeholder "{ph.group(0)}" — finish it or cut the line',
                )
            )

        if IMAGE_RE.search(stripped):
            window = [lines[j] for j in range(i, min(len(lines), i + 3)) if not masked[j]]
            if not any(SOURCE_RE.search(w) for w in window):
                findings.append(
                    Finding(
                        WARN,
                        lineno,
                        "figure-no-source",
                        "chart/figure with no Source line in the next two lines",
                    )
                )

        if i in in_table:
            continue

        if stripped.startswith(">") or HEADING_RE.match(stripped):
            continue

        num = NUMBER_RE.search(stripped)
        if not num:
            continue
        num_token = num.group(0).strip().rstrip(",.;:")
        if i < first_heading:
            continue  # header block: rating / price / price-target bridge
        sourced = bool(SOURCE_RE.search(stripped))
        periodised = bool(PERIOD_RE.search(stripped))
        threshold = bool(THRESHOLD_RE.search(stripped))
        if not sourced and not periodised and not threshold:
            findings.append(
                Finding(
                    WARN,
                    lineno,
                    "unsourced-claim",
                    f'number "{num_token}" with no source marker and no period',
                )
            )
        elif sourced and not periodised:
            findings.append(
                Finding(
                    WARN,
                    lineno,
                    "no-period",
                    f'number "{num_token}" is sourced but carries no period (quarter/year/trailing window)',
                )
            )

    # --- tables -----------------------------------------------------------
    for start, end, header in tables:
        rows = end - start + 1
        if not table_is_sourced(lines, start, end):
            findings.append(
                Finding(
                    ERROR,
                    start + 1,
                    "table-no-source",
                    f'table of {rows} rows has no "Source:" line in the four lines below it',
                )
            )
        if header is not None:
            cells = [c.strip() for c in lines[header].strip().strip("|").split("|")]
            for cell in cells:
                bare = cell.strip("* ")
                if FY_ONLY_RE.match(bare) and not FY_MARK_RE.search(bare):
                    findings.append(
                        Finding(
                            WARN,
                            header + 1,
                            "unmarked-fy",
                            f'column "{bare}" names a fiscal year without an E/A marker',
                        )
                    )

    findings.sort(key=lambda f: (f.line, f.level != ERROR))
    return findings, as_of


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit a draft equity-research note for data-discipline defects.",
    )
    parser.add_argument("note", help="path to the markdown note to check")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as blocking")
    parser.add_argument(
        "--min-lines",
        type=int,
        default=40,
        help="only require a Sources section at or above this length (default 40)",
    )
    args = parser.parse_args(argv)

    path = Path(args.note)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2
    try:
        findings, as_of = check(path, args.min_lines)
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 2

    errors = sum(1 for f in findings if f.level == ERROR)
    warnings = sum(1 for f in findings if f.level == WARN)
    blocking = errors if not args.strict else errors + warnings

    if args.json:
        print(
            json.dumps(
                {
                    "file": str(path),
                    "as_of": as_of,
                    "errors": errors,
                    "warnings": warnings,
                    "blocking": blocking,
                    "findings": [asdict(f) for f in findings],
                },
                indent=2,
            )
        )
    else:
        print(f"{path}")
        print(f"  as-of stamp: {as_of or 'NONE'}")
        print(f"  {errors} error(s), {warnings} warning(s)\n")
        for f in findings:
            print(f"  {f.level:<5} line {f.line:>4}  {f.rule:<17} {f.message}")
        if not findings:
            print("  clean")
        elif blocking:
            print(f"\n  BLOCKED: {blocking} blocking finding(s)")
        else:
            print("\n  pass (warnings only; --strict would block)")

    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
