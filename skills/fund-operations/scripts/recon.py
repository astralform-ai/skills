#!/usr/bin/env python3
"""Deterministic two-file reconciliation and break classification.

Reconciles a left-side extract against a right-side extract (GL vs subledger,
fund admin vs transfer agent, custodian vs book, statement vs workpaper) at a
composite key, and writes a workpaper that names every break, classifies it, and
quantifies it. Same inputs, same parameters -> byte-identical workpaper: no
timestamps, no random sampling, deterministic sort order.

Usage:
    python recon.py LEFT RIGHT --key account,security_id --amount amount \\
        --out /workspace/recon/workpaper.xlsx --left-label GL --right-label SUBLEDGER \\
        --export GL-SUBLEDGER-2026-04.xlsx

    python recon.py gl.csv subledger.csv --key journal_line_id --amount base_amount \\
        --left-sign -1 --abs-tol 0.01 --rel-tol 0.0 \\
        --fee-tol 500 --left-date gl_post_date --right-date sub_post_date --date-tol 1 \\
        --out /workspace/recon/breaks.csv

Inputs are CSV or XLSX (one sheet; use --left-sheet/--right-sheet to pick).
Amounts may carry currency symbols, thousands separators, parentheses for
negatives, and trailing CR/DR tokens (--left-neg-token / --right-neg-token).

Column arguments (--key, --amount, ...) name columns as they exist AFTER
--left-col/--right-col renaming, so `--left-col CUSIP=security_id --key
account,security_id` is the correct pairing.

Write the workpaper to a scratch path with --out, and add --export NAME to
publish the same bytes to /workspace/outputs/NAME through runtime.fs.write_file
(never a plain file write into /workspace/outputs). Two runs on the same inputs
with the same parameters produce identical bytes; the sha256 of the workpaper is
printed so a re-run can be proven to match.

Exit codes:
    0  recon ran; the workpaper is written (breaks may exist)
    1  --fail-on-breaks was given and at least one break row exists
    2  setup error: bad arguments, missing column, unreadable input
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# A workpaper must be reproducible: no wall-clock value may enter the output.
FIXED_TIMESTAMP = datetime(2000, 1, 1, 0, 0, 0)
CORE_MODIFIED = re.compile(rb"<dcterms:modified[^>]*>[^<]*</dcterms:modified>")
FIXED_CORE_MODIFIED = b'<dcterms:modified xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:modified>'

XLSX_SUFFIXES = {".xlsx", ".xlsm"}
CSV_SUFFIXES = {".csv", ".txt", ".tsv"}
NUM_STRIP = re.compile(r"[^0-9eE+\-.]")
NULLISH = {"", "-", "--", "nan", "none", "null", "n/a", "na", "nat"}

BREAK_BUCKETS = ("timing", "fx", "amount_break", "quantity_break", "sign_break", "left_only", "right_only", "error")

WORKPAPER_COLUMNS = [
    "key", "bucket", "cause", "left_amount", "right_amount", "delta",
    "abs_delta", "rel_delta", "left_rows", "right_rows", "left_date",
    "right_date", "date_days", "note",
]


class SetupError(Exception):
    """Bad arguments or unreadable input — reported, never papered over."""


def is_null(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def to_number(value, neg_tokens: tuple[str, ...] = ()) -> float:
    """Parse a spreadsheet amount to float; NaN when it cannot be read.

    Handles thousands separators, currency symbols, unicode minus, parentheses
    for negatives, a trailing minus, and named negative tokens (e.g. CR, Dr).
    """
    if is_null(value):
        return math.nan
    if isinstance(value, bool):
        return math.nan
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if raw.lower() in NULLISH:
        return math.nan
    neg = False
    body = raw
    if body.startswith("(") and body.endswith(")"):
        neg = True
        body = body[1:-1]
    low = body.lower()
    for token in neg_tokens:
        token = token.strip().lower()
        if token and token in low:
            neg = True
            break
    body = body.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    body = body.replace(",", "")
    body = NUM_STRIP.sub("", body)
    if body.endswith("-"):
        neg = True
        body = body[:-1]
    if body in {"", "+", "-", ".", "+.", "-."}:
        return math.nan
    try:
        value_f = float(body)
    except ValueError:
        return math.nan
    return -abs(value_f) if neg else value_f


def norm_key(parts) -> str:
    out = []
    for part in parts:
        if is_null(part):
            out.append("")
        else:
            out.append(" ".join(str(part).split()).upper())
    return "|".join(out)


def parse_colmap(specs: list[str] | None, side: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for spec in specs or []:
        if "=" not in spec:
            raise SetupError(f"--{side}-col expects SRC=CANONICAL, got {spec!r}")
        src, canon = spec.split("=", 1)
        out[src.strip()] = canon.strip()
    return out


def parse_neg_tokens(specs: list[str] | None) -> tuple[str, ...]:
    out = []
    for spec in specs or []:
        out.extend(t for t in spec.split(",") if t.strip())
    return tuple(out)


def read_frame(path: Path, sheet, skiprows: int, colmap: dict[str, str], label: str) -> pd.DataFrame:
    if not path.exists():
        raise SetupError(f"{label}: no such file: {path}")
    suffix = path.suffix.lower()
    try:
        if suffix in CSV_SUFFIXES:
            df = pd.read_csv(path, skiprows=skiprows, dtype=object, sep=None if suffix == ".tsv" else ",", engine="python" if suffix == ".tsv" else "c")
        elif suffix in XLSX_SUFFIXES:
            df = pd.read_excel(path, sheet_name=sheet if sheet is not None else 0, skiprows=skiprows, dtype=object)
        else:
            raise SetupError(f"{label}: unsupported input type {suffix!r} (use .csv or .xlsx)")
    except SetupError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface the reader's own message
        raise SetupError(f"{label}: could not read {path}: {exc}") from exc
    if df.empty:
        raise SetupError(f"{label}: {path} has no data rows (skiprows={skiprows})")
    if colmap:
        missing = [src for src in colmap if src not in df.columns]
        if missing:
            raise SetupError(f"{label}: --{label.lower()}-col names not in header: {missing}; header is {list(df.columns)}")
        df = df.rename(columns=colmap)
    return df


def resolve_column(df: pd.DataFrame, side: str, canonical: str, args) -> str | None:
    name = getattr(args, f"{side}_{canonical}", None) or getattr(args, canonical, None)
    if name is None:
        return None
    if name not in df.columns:
        raise SetupError(
            f"{side}: column {name!r} (for {canonical}) is not in the file; "
            f"header is {list(df.columns)}"
        )
    return name


def side_frame(df: pd.DataFrame, side: str, args) -> pd.DataFrame:
    """Normalize one side to per-key aggregates with canonical columns."""
    key_cols = args.key
    for col in key_cols:
        if col not in df.columns:
            raise SetupError(f"{side}: key column {col!r} is not in the file; header is {list(df.columns)}")

    amt_col = resolve_column(df, side, "amount", args)
    if amt_col is None:
        raise SetupError(f"{side}: --{side}-amount/--amount is required")
    qty_col = resolve_column(df, side, "quantity", args)
    date_col = resolve_column(df, side, "date", args)
    fx_col = resolve_column(df, side, "fx_rate", args)
    local_col = resolve_column(df, side, "local_amount", args)

    neg_tokens = parse_neg_tokens(getattr(args, f"{side}_neg_token"))
    sign = getattr(args, f"{side}_sign")

    out = pd.DataFrame(index=df.index)
    out["key"] = [norm_key(row) for row in df[key_cols].itertuples(index=False, name=None)]
    out["amount"] = [to_number(v, neg_tokens) * sign for v in df[amt_col]]
    out["quantity"] = [to_number(v, neg_tokens) for v in df[qty_col]] if qty_col else math.nan
    out["fx_rate"] = [to_number(v) for v in df[fx_col]] if fx_col else math.nan
    out["local_amount"] = [to_number(v, neg_tokens) * sign for v in df[local_col]] if local_col else math.nan
    if date_col:
        parsed = pd.to_datetime(df[date_col], errors="coerce")
        out["date"] = [None if pd.isna(v) else v.date().isoformat() for v in parsed]
    else:
        out["date"] = None
    return out


def aggregate(rows: pd.DataFrame, label: str, on_duplicate: str) -> pd.DataFrame:
    """Collapse repeated keys to one row, counting source lines."""
    grouped = rows.groupby("key", sort=True, dropna=False)
    counts = grouped.size()
    if on_duplicate == "error":
        dupes = counts[counts > 1]
        if len(dupes):
            raise SetupError(
                f"{label}: {len(dupes)} key(s) appear on more than one row "
                f"(first: {dupes.index[0]!r}) and --on-duplicate error was given"
            )

    def first_non_null(series):
        for value in series:
            if not is_null(value):
                return value
        return None

    agg = pd.DataFrame({
        "key": counts.index,
        "amount": grouped["amount"].sum(min_count=1).to_numpy(),
        "quantity": grouped["quantity"].sum(min_count=1).to_numpy(),
        "local_amount": grouped["local_amount"].sum(min_count=1).to_numpy(),
        "fx_rate": grouped["fx_rate"].mean().to_numpy(),
        "n_rows": counts.to_numpy(),
        "n_null_amount": grouped["amount"].apply(lambda s: int(s.isna().sum())).to_numpy(),
        "date": grouped["date"].apply(first_non_null).to_numpy(),
        "n_dates": grouped["date"].apply(lambda s: len({d for d in s if d})).to_numpy(),
    })
    return agg.set_index("key", drop=False)


def within_tol(abs_delta: float, left: float, right: float, abs_tol: float, rel_tol: float) -> bool:
    if abs_delta <= abs_tol:
        return True
    if rel_tol > 0:
        scale = max(abs(left), abs(right))
        if scale > 0 and abs_delta / scale <= rel_tol:
            return True
    return False


def fmt(value, decimals: int) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return f"{value:,.{decimals}f}"


def date_gap(left_date, right_date) -> int | None:
    if not left_date or not right_date:
        return None
    return (pd.Timestamp(right_date) - pd.Timestamp(left_date)).days


def classify_key(key, lrow, rrow, args) -> dict:
    """One workpaper row for a key present on both sides."""
    left_amt = float(lrow["amount"])
    right_amt = float(rrow["amount"])
    # Report delta as right - left; state it, never let the reader guess.
    delta = right_amt - left_amt
    abs_delta = abs(delta)
    scale = max(abs(left_amt), abs(right_amt))
    rel_delta = abs_delta / scale if scale > 0 else 0.0
    gap = date_gap(lrow["date"], rrow["date"])
    notes: list[str] = []

    if math.isnan(left_amt) or math.isnan(right_amt):
        return row(key, "error", "data_quality", left_amt, right_amt, delta, abs_delta, rel_delta,
                   lrow, rrow, gap, "amount could not be parsed on one side")

    amount_ok = within_tol(abs_delta, left_amt, right_amt, args.abs_tol, args.rel_tol)
    qty_ok = qty_agrees(lrow, rrow, args)
    bucket = cause = ""
    if qty_ok and amount_ok:
        if gap is not None and abs(gap) > args.date_tol:
            bucket, cause = "timing", "timing"
            notes.append(f"amounts agree within tolerance; posting dates differ by {gap} day(s)")
        else:
            bucket, cause = "matched", ""
    elif not qty_ok:
        bucket, cause = "quantity_break", "quantity"
        notes.append(f"quantity differs: {lrow['quantity']} vs {rrow['quantity']}")
        if not amount_ok:
            notes.append(f"amount also differs by {fmt(abs_delta, args.decimals)}")
    else:
        negate = left_amt != 0 and right_amt != 0 and (left_amt < 0) != (right_amt < 0)
        if negate and within_tol(abs(abs(left_amt) - abs(right_amt)), abs(left_amt), abs(right_amt), args.abs_tol, args.rel_tol):
            bucket, cause = "sign_break", "sign"
            notes.append("same magnitude, opposite sign — sign conventions differ between sources")
        elif local_amounts_agree(lrow, rrow, args) and not fx_agrees(lrow, rrow, args):
            bucket, cause = "fx", "fx"
            notes.append(
                f"local amounts agree but the rate differs "
                f"({fmt(lrow['fx_rate'], 6)} vs {fmt(rrow['fx_rate'], 6)}) — FX rate or rate-date mismatch"
            )
        elif abs_delta <= args.fee_tol:
            bucket, cause = "amount_break", "fee"
            notes.append(f"small recurring delta ({fmt(abs_delta, args.decimals)}) consistent with a fee or accrual posted on one side only")
        else:
            bucket, cause = "amount_break", "real"
            notes.append(f"amount differs by {fmt(abs_delta, args.decimals)} ({rel_delta * 100:.2f}% of the larger side)")
        if gap is not None and abs(gap) > args.date_tol:
            notes.append(f"dates also differ by {gap} day(s)")

    if int(lrow["n_rows"]) != int(rrow["n_rows"]):
        if cause == "matched":
            cause = "duplicate"
        notes.append(f"line counts differ ({int(lrow['n_rows'])} vs {int(rrow['n_rows'])}); amounts compared after aggregation")
    return row(key, bucket, cause, left_amt, right_amt, delta, abs_delta, rel_delta, lrow, rrow, gap, "; ".join(notes))


def local_amounts_agree(lrow, rrow, args) -> bool:
    left = lrow["local_amount"]
    right = rrow["local_amount"]
    if is_null(left) or is_null(right):
        return False
    return within_tol(abs(float(right) - float(left)), float(left), float(right), args.abs_tol, args.rel_tol)


def qty_agrees(lrow, rrow, args) -> bool:
    """True when quantity is absent from the comparison or agrees within tolerance."""
    left = lrow["quantity"]
    right = rrow["quantity"]
    if is_null(left) or is_null(right):
        return True
    return abs(float(right) - float(left)) <= args.qty_tol


def fx_agrees(lrow, rrow, args) -> bool:
    left = lrow["fx_rate"]
    right = rrow["fx_rate"]
    if is_null(left) or is_null(right):
        return False
    return within_tol(abs(float(right) - float(left)), float(left), float(right), args.fx_tol, 0.0)


def row(key, bucket, cause, left_amt, right_amt, delta, abs_delta, rel_delta, lrow, rrow, gap, note) -> dict:
    return {
        "key": key,
        "bucket": bucket,
        "cause": cause,
        "left_amount": left_amt,
        "right_amount": right_amt,
        "delta": delta,
        "abs_delta": abs_delta,
        "rel_delta": rel_delta,
        "left_rows": int(lrow["n_rows"]) if lrow is not None else 0,
        "right_rows": int(rrow["n_rows"]) if rrow is not None else 0,
        "left_date": lrow["date"] if lrow is not None else None,
        "right_date": rrow["date"] if rrow is not None else None,
        "date_days": gap,
        "note": note,
    }


def one_sided(key, lrow, rrow, args) -> dict:
    side = "left" if rrow is None else "right"
    present = lrow if lrow is not None else rrow
    amount = float(present["amount"])
    other = args.right_label if side == "left" else args.left_label
    cause = "missing"
    note = f"present on {args.left_label if side == 'left' else args.right_label} only — not in {other}"
    if math.isnan(amount):
        bucket = "error"
        cause = "data_quality"
        note = "amount could not be parsed"
    else:
        bucket = f"{side}_only"
        if abs(amount) <= args.fee_tol:
            cause = "fee"
            note += f"; one-sided small amount ({fmt(abs(amount), args.decimals)}) — consistent with a fee or accrual on one side"
    if present["n_rows"] > 1:
        note += f"; {int(present['n_rows'])} source lines aggregated under this key"
    delta = -amount if side == "left" else amount
    return row(key, bucket, cause, amount if side == "left" else math.nan,
               amount if side == "right" else math.nan, delta, abs(delta), math.nan,
               lrow, rrow, date_gap(lrow["date"] if lrow is not None else None,
                                    rrow["date"] if rrow is not None else None), note)


def pair_offsets(work: pd.DataFrame, args) -> None:
    """Detect unmatched amounts that offset another unmatched key, or repeat one.

    A reclass posts the same amount to two different accounts, so it shows up as
    one left-only and one right-only row with opposite signs. A duplicate shows
    up as the same amount and sign on both sides. Neither is netted away — each
    is labelled and left in the workpaper for a human to resolve.
    """
    left_idx = [i for i, r in work.iterrows() if r["bucket"] == "left_only" and r["cause"] == "missing"]
    right_idx = [i for i, r in work.iterrows() if r["bucket"] == "right_only" and r["cause"] == "missing"]
    if not left_idx or not right_idx:
        return
    if len(left_idx) + len(right_idx) > args.pair_limit:
        return
    used: set[int] = set()
    right_idx = sorted(right_idx, key=lambda i: (work.at[i, "key"], work.at[i, "abs_delta"]))
    for li in sorted(left_idx, key=lambda i: work.at[i, "key"]):
        left_amt = work.at[li, "left_amount"]
        for ri in right_idx:
            if ri in used:
                continue
            right_amt = work.at[ri, "right_amount"]
            if within_tol(abs(left_amt + right_amt), left_amt, right_amt, args.abs_tol, args.rel_tol):
                work.at[li, "cause"] = "mapping"
                work.at[li, "note"] += f"; offsets {work.at[ri, 'key']} on {args.right_label} — possible reclass or mapping"
                work.at[ri, "cause"] = "mapping"
                work.at[ri, "note"] += f"; offsets {work.at[li, 'key']} on {args.left_label} — possible reclass or mapping"
                used.add(ri)
                break
            if within_tol(abs(left_amt - right_amt), left_amt, right_amt, args.abs_tol, args.rel_tol):
                work.at[li, "cause"] = "duplicate_candidate"
                work.at[li, "note"] += f"; same amount and sign as {work.at[ri, 'key']} — possible duplicate posting"
                work.at[ri, "cause"] = "duplicate_candidate"
                work.at[ri, "note"] += f"; same amount and sign as {work.at[li, 'key']} — possible duplicate posting"
                used.add(ri)
                break


def build_summary(work: pd.DataFrame, args, left_n: int, right_n: int) -> pd.DataFrame:
    rows = []
    total_keys = len(work)
    matched = int((work["bucket"] == "matched").sum())
    breaks = work[work["bucket"].isin(BREAK_BUCKETS)]
    gross = float(breaks["abs_delta"].sum())
    net = float(work["delta"].sum())
    left_total = float(work["left_amount"].sum(min_count=1))
    right_total = float(work["right_amount"].sum(min_count=1))

    for label, group in (("bucket", "bucket"), ("cause", "cause")):
        for value, chunk in sorted(work.groupby(group), key=lambda kv: kv[0]):
            if label == "cause" and chunk["bucket"].iloc[0] == "matched" and value == "":
                continue
            rows.append({
                "group": label,
                "value": value or "(matched)",
                "keys": int(len(chunk)),
                "gross_abs_delta": float(chunk["abs_delta"].sum()),
                "net_delta": float(chunk["delta"].sum()),
            })
    rows.extend([
        {"group": "total", "value": "keys on either side", "keys": total_keys, "gross_abs_delta": gross, "net_delta": net},
        {"group": "total", "value": "matched keys", "keys": matched, "gross_abs_delta": 0.0, "net_delta": 0.0},
        {"group": "total", "value": "matched % of keys", "keys": round(100.0 * matched / total_keys, 2) if total_keys else 0.0, "gross_abs_delta": 0.0, "net_delta": 0.0},
        {"group": "total", "value": "break keys", "keys": int(len(breaks)), "gross_abs_delta": gross, "net_delta": net},
        {"group": "total", "value": f"{args.left_label} total", "keys": left_n, "gross_abs_delta": 0.0, "net_delta": left_total},
        {"group": "total", "value": f"{args.right_label} total", "keys": right_n, "gross_abs_delta": 0.0, "net_delta": right_total},
        {"group": "total", "value": "net delta (right - left)", "keys": 0, "gross_abs_delta": 0.0, "net_delta": net},
        {"group": "total", "value": "gross break delta (sum of |delta|)", "keys": 0, "gross_abs_delta": gross, "net_delta": 0.0},
    ])
    offset_pairs = int(work["cause"].isin({"mapping", "duplicate_candidate"}).sum())
    offsetting = gross > 0 and (abs(net) <= args.netting_ratio * gross or offset_pairs > 0)
    if offsetting:
        why = "offsetting reclass/duplicate candidates detected" if offset_pairs else "net is small versus gross"
        text = f"offsetting breaks present ({why}) — do not report the net as agreement"
    else:
        text = "no netting flag"
    rows.append({
        "group": "flag", "value": text,
        "keys": 1 if offsetting else 0, "gross_abs_delta": gross, "net_delta": net,
    })
    summary = pd.DataFrame(rows, columns=["group", "value", "keys", "gross_abs_delta", "net_delta"])
    for col in ("gross_abs_delta", "net_delta"):
        summary[col] = [round(float(v), args.decimals) for v in summary[col]]
    return summary


def run(args) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    left_raw = read_frame(Path(args.left), args.left_sheet, args.left_skiprows, parse_colmap(args.left_col, "left"), "left")
    right_raw = read_frame(Path(args.right), args.right_sheet, args.right_skiprows, parse_colmap(args.right_col, "right"), "right")
    left = aggregate(side_frame(left_raw, "left", args), "left", args.on_duplicate)
    right = aggregate(side_frame(right_raw, "right", args), "right", args.on_duplicate)

    left_n, right_n = len(left_raw), len(right_raw)
    rows = []
    for key in sorted(set(left.index) | set(right.index)):
        lrow = left.loc[key] if key in left.index else None
        rrow = right.loc[key] if key in right.index else None
        if lrow is None:
            rows.append(one_sided(key, None, rrow, args))
        elif rrow is None:
            rows.append(one_sided(key, lrow, None, args))
        else:
            rows.append(classify_key(key, lrow, rrow, args))

    work = pd.DataFrame(rows, columns=WORKPAPER_COLUMNS)
    if not work.empty:
        work["_break"] = work["bucket"].isin(BREAK_BUCKETS).astype(int)
        work = work.sort_values(
            by=["_break", "abs_delta", "key"], ascending=[False, False, True], kind="mergesort"
        ).drop(columns=["_break"]).reset_index(drop=True)
        pair_offsets(work, args)

    summary = build_summary(work, args, left_n, right_n)
    params = pd.DataFrame([
        ("skill", "fund-operations/recon.py"),
        ("left_label", args.left_label), ("right_label", args.right_label),
        ("left_file", str(args.left)), ("right_file", str(args.right)),
        ("key_columns", ", ".join(args.key)),
        ("left_rows_read", left_n), ("right_rows_read", right_n),
        ("keys_compared", len(work)),
        ("abs_tol", args.abs_tol), ("rel_tol", args.rel_tol),
        ("qty_tol", args.qty_tol), ("fx_tol", args.fx_tol),
        ("fee_tol", args.fee_tol), ("date_tol_days", args.date_tol),
        ("left_sign", args.left_sign), ("right_sign", args.right_sign),
        ("left_neg_tokens", ",".join(parse_neg_tokens(args.left_neg_token)) or "(none)"),
        ("right_neg_tokens", ",".join(parse_neg_tokens(args.right_neg_token)) or "(none)"),
        ("on_duplicate", args.on_duplicate),
        ("aggregation", "repeated keys summed; line counts reported per row"),
        ("delta_definition", "right_amount - left_amount"),
        ("decimals_reported", args.decimals),
        ("netting_flag_ratio", args.netting_ratio),
    ], columns=["parameter", "value"])
    return params, work, summary


def build_workpaper(args, params: pd.DataFrame, work: pd.DataFrame, summary: pd.DataFrame,
                    suffix: str) -> bytes:
    """Serialize the workpaper to bytes. Deterministic for a given input + parameters.

    Amount columns stay numeric so a reviewer can sort and sum them; the readable
    version of every delta is in the row's ``note``.
    """
    pretty = work.copy()
    for col in ("left_amount", "right_amount", "delta", "abs_delta"):
        pretty[col] = [None if is_null(v) else round(float(v), args.decimals) for v in pretty[col]]
    pretty["rel_delta"] = [None if is_null(v) else round(float(v), 6) for v in pretty["rel_delta"]]
    pretty["date_days"] = [None if is_null(v) else int(v) for v in pretty["date_days"]]

    if suffix.lower() in XLSX_SUFFIXES:
        wb = Workbook()
        wb.remove(wb.active)
        for title, frame in (("Params", params), ("Workpaper", pretty), ("Summary", summary)):
            ws = wb.create_sheet(title)
            for row in dataframe_to_rows(frame.astype(object).where(frame.notna(), None), index=False, header=True):
                ws.append(list(row))
            ws.freeze_panes = "A2"
        # Fixed core properties + fixed zip entry dates: two runs on the same
        # inputs produce the same bytes, so the workpaper can be hashed and re-run.
        wb.properties.creator = "fund-operations/recon.py"
        wb.properties.lastModifiedBy = "fund-operations/recon.py"
        wb.properties.title = "reconciliation workpaper"
        wb.properties.created = FIXED_TIMESTAMP
        wb.properties.modified = FIXED_TIMESTAMP
        buf = io.BytesIO()
        wb.save(buf)
        return _fix_zip_timestamps(buf.getvalue())
    return pretty.to_csv(index=False).encode("utf-8")


def _fix_zip_timestamps(raw: bytes) -> bytes:
    """Make the xlsx bytes reproducible.

    openpyxl stamps the current time into zip entry dates and into
    ``dcterms:modified``, neither of which can be set from the workbook
    properties. Both are rewritten to a fixed value so re-running the recon on
    the same inputs gives the same bytes — which is what makes the printed
    sha256 worth checking.
    """
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = CORE_MODIFIED.sub(FIXED_CORE_MODIFIED, data)
            fixed = zipfile.ZipInfo(info.filename, date_time=(2000, 1, 1, 0, 0, 0))
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            dst.writestr(fixed, data)
    return out.getvalue()


def emit(args, data: bytes) -> str | None:
    """Write the workpaper to --out and/or publish it to /workspace/outputs via runtime."""
    published = None
    if args.out:
        out = Path(args.out)
        if str(out).startswith("/workspace/outputs/"):
            raise SetupError(
                "never write into /workspace/outputs with a plain file write — pass a scratch "
                "--out path and use --export NAME, which publishes through runtime.fs.write_file"
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    if args.export:
        try:
            import runtime  # noqa: PLC0415 — only present inside the sandbox
        except ImportError as exc:
            raise SetupError(
                "--export needs the sandbox runtime module; run this inside runtime_run_code "
                "or drop --export and keep --out"
            ) from exc
        target = f"/workspace/outputs/{args.export}"
        runtime.fs.write_file(target, data)
        published = target
    return published


def write_summary(args, summary: pd.DataFrame) -> None:
    if args.summary_out:
        path = Path(args.summary_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(summary.to_csv(index=False).encode("utf-8"))


def print_report(args, work: pd.DataFrame, summary: pd.DataFrame) -> None:
    breaks = work[work["bucket"].isin(BREAK_BUCKETS)]
    matched = int((work["bucket"] == "matched").sum())
    total = len(work)
    print(f"keys compared: {total}   matched: {matched} "
          f"({(100.0 * matched / total) if total else 0.0:.2f}%)   breaks: {len(breaks)}")
    print(f"gross break delta: {fmt(float(breaks['abs_delta'].sum()), args.decimals)}   "
          f"net delta (right - left): {fmt(float(work['delta'].sum()), args.decimals)}")
    print(f"tolerances recorded in the workpaper: abs={args.abs_tol} rel={args.rel_tol} "
          f"date={args.date_tol}d fee={args.fee_tol}")
    for bucket in BREAK_BUCKETS:
        chunk = breaks[breaks["bucket"] == bucket]
        if len(chunk):
            print(f"  {bucket:<15} {len(chunk):>5} keys   {fmt(float(chunk['abs_delta'].sum()), args.decimals):>16}")
    for _, r in summary[summary["group"] == "flag"].iterrows():
        if r["keys"]:
            print(f"  FLAG: {r['value']}")
    if args.json:
        payload = {
            "keys": total,
            "matched": matched,
            "breaks": int(len(breaks)),
            "gross_break_delta": float(breaks["abs_delta"].sum()),
            "net_delta": float(work["delta"].sum()),
            "by_bucket": {b: int((breaks["bucket"] == b).sum()) for b in BREAK_BUCKETS},
            "by_cause": {c: int((breaks["cause"] == c).sum()) for c in sorted(set(breaks["cause"]))},
        }
        print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("left", help="left extract (.csv/.tsv/.xlsx)")
    ap.add_argument("right", help="right extract (.csv/.tsv/.xlsx)")
    ap.add_argument("--out", help="scratch workpaper path; .xlsx writes Params/Workpaper/Summary sheets, "
                                  "anything else writes CSV. Never a path under /workspace/outputs.")
    ap.add_argument("--export", help="also publish the workpaper as /workspace/outputs/NAME via runtime.fs.write_file")
    ap.add_argument("--summary-out", help="optional summary CSV on the scratch filesystem")
    ap.add_argument("--key", required=True, help="comma-separated composite key columns, e.g. account,security_id")
    ap.add_argument("--amount", help="base amount column (both sides)")
    ap.add_argument("--quantity", help="quantity column (both sides)")
    ap.add_argument("--date", help="posting-date column (both sides)")
    ap.add_argument("--fx-rate", dest="fx_rate", help="FX rate column (both sides)")
    ap.add_argument("--local-amount", dest="local_amount", help="local-currency amount column (both sides)")
    for side in ("left", "right"):
        ap.add_argument(f"--{side}-amount", dest=f"{side}_amount")
        ap.add_argument(f"--{side}-quantity", dest=f"{side}_quantity")
        ap.add_argument(f"--{side}-date", dest=f"{side}_date")
        ap.add_argument(f"--{side}-fx-rate", dest=f"{side}_fx_rate")
        ap.add_argument(f"--{side}-local-amount", dest=f"{side}_local_amount")
        ap.add_argument(f"--{side}-sign", type=float, default=1.0, help=f"multiply {side} amounts by this (default 1)")
        ap.add_argument(f"--{side}-neg-token", action="append", help=f"token marking a negative {side} amount, e.g. CR")
        ap.add_argument(f"--{side}-col", action="append", help=f"rename a {side} header: SRC=CANONICAL")
        ap.add_argument(f"--{side}-sheet", help=f"sheet name/index for an .xlsx {side} file")
        ap.add_argument(f"--{side}-skiprows", type=int, default=0, help=f"preamble rows to skip in the {side} file")
    ap.add_argument("--left-label", default="LEFT")
    ap.add_argument("--right-label", default="RIGHT")
    ap.add_argument("--abs-tol", type=float, default=0.01, help="absolute amount tolerance (default 0.01)")
    ap.add_argument("--rel-tol", type=float, default=0.0, help="relative amount tolerance; 0 disables it (default)")
    ap.add_argument("--qty-tol", type=float, default=0.0)
    ap.add_argument("--fx-tol", type=float, default=1e-6)
    ap.add_argument("--fee-tol", type=float, default=0.0, help="deltas at or below this are cause=fee (default 0: off)")
    ap.add_argument("--date-tol", type=int, default=0, help="days of date difference still treated as the same date")
    ap.add_argument("--decimals", type=int, default=2, help="display decimals in the workpaper")
    ap.add_argument("--netting-ratio", type=float, default=0.10,
                    help="flag when |net delta| <= ratio * gross break delta (default 0.10)")
    ap.add_argument("--on-duplicate", choices=("aggregate", "error"), default="aggregate",
                    help="what to do when a key repeats on one side (default aggregate, counts reported)")
    ap.add_argument("--pair-limit", type=int, default=5000, help="max unmatched rows considered for offset pairing")
    ap.add_argument("--fail-on-breaks", action="store_true", help="exit 1 when any break row exists")
    ap.add_argument("--json", action="store_true", help="print a machine-readable summary")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.key = [c.strip() for c in args.key.split(",") if c.strip()]
    if not args.key:
        print("error: --key needs at least one column", file=sys.stderr)
        return 2
    if args.abs_tol < 0 or args.rel_tol < 0:
        print("error: tolerances cannot be negative", file=sys.stderr)
        return 2
    if not args.out and not args.export:
        print("error: give --out, --export, or both", file=sys.stderr)
        return 2
    try:
        params, work, summary = run(args)
        suffix = Path(args.out).suffix if args.out else Path(args.export).suffix
        payload = build_workpaper(args, params, work, summary, suffix or ".csv")
        write_summary(args, summary)
        published = emit(args, payload)
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print_report(args, work, summary)
    digest = hashlib.sha256(payload).hexdigest()
    print(f"workpaper sha256: {digest[:16]}  ({len(payload):,} bytes)"
          + (f"  published: {published}" if published else ""))
    breaks = int(work["bucket"].isin(BREAK_BUCKETS).sum())
    if args.fail_on_breaks and breaks:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
