#!/usr/bin/env python3
"""Deterministic leveraged returns and debt-schedule calculator.

Run it with a JSON assumption spec:

    python3 returns.py deal.json
    python3 returns.py deal.json --json
    python3 returns.py deal.json --no-sensitivity

It prints the operating and debt schedule it actually used, entry metrics,
MOIC/IRR/XIRR from dated cash flows, a returns attribution, and three
sensitivity grids (entry x exit multiple, exit multiple x hold, leverage x
exit multiple). Every number is computed in Python — there is no Excel
engine here, and nothing in this script depends on one.

Exit codes: 0 clean, 1 a structural check failed, 2 bad input.

Spec schema (all amounts in one currency and one unit — declare it in "units"):

{
  "target": "Titan Software", "currency": "USD", "units": "millions",
  "entry":  {"date": "2026-10-01", "ebitda": 25.0, "multiple": 8.0,
             "fees": 3.0, "equity_invested": null},
  "operating": {"revenue": 100.0,
                "revenue_growth": [0.12, 0.10, 0.08, 0.07, 0.06],
                "ebitda_margin":  [0.25, 0.26, 0.27, 0.28, 0.28],
                "da_pct_revenue": 0.04, "capex_pct_revenue": 0.05,
                "nwc_pct_revenue": 0.10, "tax_rate": 0.25},
  "debt": [{"name": "Term Loan B", "x_ebitda": 4.0, "rate": 0.09,
            "amort_pct": 0.01, "sweep_pct": 1.0},
           {"name": "Notes", "x_ebitda": 1.5, "rate": 0.11,
            "amort_pct": 0.0, "sweep_pct": 0.0}],
  "exit": {"date": "2031-10-01", "multiple": 8.0},
  "distributions": [{"date": "2029-10-01", "amount": 10.0}]
}

Conventions (declared, not configurable — a returns number without its
conventions is not comparable to anything):
  * interest is charged on OPENING balances, so the model is non-circular;
  * mandatory amortization is a % of ORIGINAL face;
  * the cash sweep runs after mandatory amortization, in list order from
    senior to junior, each taking its sweep_pct of remaining excess cash,
    never below a zero cash balance;
  * the equity check fills the gap: uses (EV + fees) - debt raised;
  * fees reduce the day-one equity value and appear in the attribution;
  * there is no opening cash and no PIK — add them downstream if the term
    sheet has them.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DAYS_PER_YEAR = 365.0


# --------------------------------------------------------------------------
# date helpers
# --------------------------------------------------------------------------

def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bad date {value!r}: expected YYYY-MM-DD") from exc


def add_years(start: date, years: int) -> date:
    try:
        return start.replace(year=start.year + years)
    except ValueError:  # 29 Feb -> 28 Feb
        return start.replace(year=start.year + years, day=28)


def year_fraction(start: date, end: date) -> float:
    return (end - start).days / DAYS_PER_YEAR


# --------------------------------------------------------------------------
# XIRR — bisection on NPV, dated cash flows, no third-party dependency
# --------------------------------------------------------------------------

def xirr(flows: list[tuple[date, float]]) -> float:
    """Annualized IRR of dated cash flows. Raises ValueError if unsolvable."""
    if len(flows) < 2:
        raise ValueError("XIRR needs at least two cash flows")
    if not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        raise ValueError("XIRR needs both a negative and a positive cash flow")
    origin = min(d for d, _ in flows)

    def npv(rate: float) -> float:
        return sum(a / (1.0 + rate) ** ((d - origin).days / DAYS_PER_YEAR) for d, a in flows)

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        raise ValueError("XIRR bracket failed — cash-flow signs may be degenerate")
    for _ in range(300):
        mid = (lo + hi) / 2.0
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# --------------------------------------------------------------------------
# spec
# --------------------------------------------------------------------------

@dataclass
class Tranche:
    name: str
    x_ebitda: float
    rate: float
    amort_pct: float = 0.0
    sweep_pct: float = 0.0


@dataclass
class Spec:
    target: str
    currency: str
    units: str
    entry_date: date
    entry_ebitda: float
    entry_multiple: float
    fees: float
    revenue0: float
    growth: list[float]
    margin: list[float]
    da_pct: float
    capex_pct: float
    nwc_pct: float
    tax_rate: float
    tranches: list[Tranche]
    exit_date: date
    exit_multiple: float
    distributions: list[tuple[date, float]]
    equity_override: float | None

    @property
    def hold_years(self) -> int:
        return round(year_fraction(self.entry_date, self.exit_date))


def _req(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d or d[key] is None:
        raise ValueError(f"missing required key {where}.{key}")
    return d[key]


def load_spec(path: Path) -> Spec:
    raw = json.loads(path.read_text())
    entry = _req(raw, "entry", "spec")
    operating = _req(raw, "operating", "spec")
    exit_ = _req(raw, "exit", "spec")
    debt = raw.get("debt", [])
    if not debt:
        raise ValueError("spec.debt must list at least one tranche")

    spec = Spec(
        target=raw.get("target", path.stem),
        currency=raw.get("currency", "USD"),
        units=raw.get("units", "millions"),
        entry_date=parse_date(_req(entry, "date", "entry")),
        entry_ebitda=float(_req(entry, "ebitda", "entry")),
        entry_multiple=float(_req(entry, "multiple", "entry")),
        fees=float(entry.get("fees", 0.0)),
        revenue0=float(_req(operating, "revenue", "operating")),
        growth=[float(x) for x in _req(operating, "revenue_growth", "operating")],
        margin=[float(x) for x in _req(operating, "ebitda_margin", "operating")],
        da_pct=float(operating.get("da_pct_revenue", 0.0)),
        capex_pct=float(operating.get("capex_pct_revenue", 0.0)),
        nwc_pct=float(operating.get("nwc_pct_revenue", 0.0)),
        tax_rate=float(operating.get("tax_rate", 0.0)),
        tranches=[
            Tranche(
                name=_req(t, "name", "debt[]"),
                x_ebitda=float(_req(t, "x_ebitda", "debt[]")),
                rate=float(_req(t, "rate", "debt[]")),
                amort_pct=float(t.get("amort_pct", 0.0)),
                sweep_pct=float(t.get("sweep_pct", 0.0)),
            )
            for t in debt
        ],
        exit_date=parse_date(_req(exit_, "date", "exit")),
        exit_multiple=float(_req(exit_, "multiple", "exit")),
        distributions=[
            (parse_date(_req(d, "date", "distributions[]")), float(_req(d, "amount", "distributions[]")))
            for d in raw.get("distributions", [])
        ],
        equity_override=entry.get("equity_invested"),
    )

    if spec.entry_ebitda <= 0 or spec.entry_multiple <= 0 or spec.exit_multiple <= 0:
        raise ValueError("entry EBITDA and both multiples must be positive")
    if spec.exit_date <= spec.entry_date:
        raise ValueError("exit date must be after the entry date")
    return spec


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

@dataclass
class YearRow:
    year: int
    revenue: float
    ebitda: float
    interest: float
    da: float
    cash_taxes: float
    capex: float
    d_nwc: float
    cash_available: float
    mandatory: float
    sweep: float
    opening_debt: list[float]
    amort_by_tranche: list[float]
    sweep_by_tranche: list[float]
    closing_debt: list[float]
    cash_balance: float


@dataclass
class Result:
    entry_date: date
    exit_date: date
    hold_years: float
    entry_ev: float
    debt_faces: list[float]
    equity_invested: float
    rows: list[YearRow]
    exit_ebitda: float
    exit_ev: float
    exit_net_debt: float
    exit_equity: float
    distributions: list[tuple[date, float]]
    moic: float
    irr: float
    simple_irr: float
    entry_leverage: float
    interest_coverage_y1: float
    attribution: dict[str, float] = field(default_factory=dict)
    checks: list[tuple[str, bool]] = field(default_factory=list)


def growth_at(spec: Spec, i: int) -> float:
    return spec.growth[i] if i < len(spec.growth) else spec.growth[-1]


def margin_at(spec: Spec, i: int) -> float:
    return spec.margin[i] if i < len(spec.margin) else spec.margin[-1]


def run(spec: Spec, entry_multiple: float | None = None, exit_multiple: float | None = None,
        hold_years: int | None = None, leverage_scale: float = 1.0) -> Result:
    """Run the model. Overrides drive the sensitivity grids; the base case passes none."""
    em = spec.entry_multiple if entry_multiple is None else entry_multiple
    xm = spec.exit_multiple if exit_multiple is None else exit_multiple
    years = spec.hold_years if hold_years is None else hold_years
    exit_date = spec.exit_date if hold_years is None else add_years(spec.entry_date, years)

    entry_ev = em * spec.entry_ebitda
    faces = [t.x_ebitda * spec.entry_ebitda * leverage_scale for t in spec.tranches]
    uses = entry_ev + spec.fees
    equity = uses - sum(faces)
    if spec.equity_override is not None and entry_multiple is None and hold_years is None:
        equity = float(spec.equity_override)
    if equity <= 0:
        raise ValueError(
            f"equity check is {equity:.2f} at {em:.2f}x — debt raised exceeds uses"
        )

    balances = list(faces)
    cash = 0.0
    prior_revenue = spec.revenue0
    rows: list[YearRow] = []

    for i in range(years):
        opening = list(balances)
        revenue = prior_revenue * (1.0 + growth_at(spec, i))
        ebitda = revenue * margin_at(spec, i)
        interest = sum(t.rate * b for t, b in zip(spec.tranches, opening))
        da = revenue * spec.da_pct
        pretax = ebitda - da - interest
        cash_taxes = max(0.0, pretax) * spec.tax_rate
        capex = revenue * spec.capex_pct
        d_nwc = (revenue - prior_revenue) * spec.nwc_pct
        cash_available = ebitda - interest - cash_taxes - capex - d_nwc

        amort = [0.0] * len(spec.tranches)
        for idx, t in enumerate(spec.tranches):
            pay = min(t.amort_pct * faces[idx], balances[idx])
            balances[idx] -= pay
            amort[idx] = pay
        mandatory = sum(amort)
        if mandatory > cash + cash_available + 1e-9:
            raise ValueError(
                f"year {i + 1}: mandatory amortization of {mandatory:,.2f} exceeds available cash "
                f"of {cash + cash_available:,.2f} — restructure amortization; a negative cash balance "
                "is an input error, not a finding"
            )
        cash = cash + cash_available - mandatory

        sweeps = [0.0] * len(spec.tranches)
        excess = cash
        for idx, t in enumerate(spec.tranches):
            if t.sweep_pct <= 0:
                continue
            take = min(t.sweep_pct * excess, balances[idx])
            balances[idx] -= take
            excess -= take
            sweeps[idx] = take
        cash -= sum(sweeps)

        rows.append(YearRow(
            year=i + 1, revenue=revenue, ebitda=ebitda, interest=interest, da=da,
            cash_taxes=cash_taxes, capex=capex, d_nwc=d_nwc,
            cash_available=cash_available, mandatory=mandatory, sweep=sum(sweeps),
            opening_debt=opening, amort_by_tranche=amort, sweep_by_tranche=sweeps,
            closing_debt=list(balances), cash_balance=cash,
        ))
        prior_revenue = revenue

    exit_ebitda = margin_at(spec, years - 1) * revenue if years else spec.entry_ebitda
    exit_ev = xm * exit_ebitda
    exit_net_debt = sum(balances) - cash
    exit_equity = exit_ev - exit_net_debt

    flows = [(spec.entry_date, -equity)]
    flows += [(d, a) for d, a in spec.distributions if spec.entry_date < d <= exit_date]
    flows.append((exit_date, exit_equity))
    proceeds = exit_equity + sum(a for d, a in flows[1:-1])
    moic = proceeds / equity
    irr = xirr(flows)
    hold = year_fraction(spec.entry_date, exit_date)
    simple_irr = moic ** (1.0 / hold) - 1.0 if hold > 0 and moic > 0 else float("nan")

    # attribution: growth + multiple + debt paydown reconcile to the gain, with fees/distributions as the remainder
    growth_effect = (exit_ebitda - spec.entry_ebitda) * em
    multiple_effect = (xm - em) * exit_ebitda
    paydown_effect = sum(faces) - exit_net_debt
    fees_and_dist = proceeds - equity - growth_effect - multiple_effect - paydown_effect
    attribution = {
        "EBITDA growth": growth_effect,
        "Multiple change": multiple_effect,
        "Debt paydown / cash build": paydown_effect,
        "Fees and interim distributions": fees_and_dist,
    }
    attribution_ties = abs(
        sum(attribution.values()) - (proceeds - equity)
    ) < 1e-6 * max(1.0, abs(proceeds - equity))

    checks: list[tuple[str, bool]] = [
        ("sources = uses (debt + equity = EV + fees)",
         abs((sum(faces) + equity) - uses) < 1e-6 * max(1.0, uses)),
        ("exit equity = exit EV - exit net debt",
         abs(exit_equity - (exit_ev - exit_net_debt)) < 1e-6 * max(1.0, abs(exit_ev))),
        ("cash never negative", all(r.cash_balance >= -1e-9 for r in rows)),
        ("no tranche repaid below zero", all(b >= -1e-9 for b in balances)),
        ("total debt = sum of tranche balances",
         abs(sum(balances) - sum(rows[-1].closing_debt)) < 1e-9 if rows else True),
        ("returns attribution ties to total gain", attribution_ties),
    ]
    for idx, t in enumerate(spec.tranches):
        opens_tie = all(
            abs(prev.closing_debt[idx] - nxt.opening_debt[idx]) < 1e-9
            for prev, nxt in zip(rows, rows[1:])
        )
        rolls_tie = all(
            abs(row.opening_debt[idx] - row.amort_by_tranche[idx] - row.sweep_by_tranche[idx]
                - row.closing_debt[idx]) < 1e-9
            for row in rows
        )
        checks.append((f"debt roll-forward ties: {t.name}", opens_tie and rolls_tie))
    if not spec.distributions:
        checks.append(("MOIC = (1 + IRR)^years (single in/out pair)",
                       abs(moic - (1 + irr) ** hold) < 1e-4 * max(1.0, moic)))

    return Result(
        entry_date=spec.entry_date, exit_date=exit_date, hold_years=hold, entry_ev=entry_ev,
        debt_faces=faces, equity_invested=equity, rows=rows, exit_ebitda=exit_ebitda,
        exit_ev=exit_ev, exit_net_debt=exit_net_debt, exit_equity=exit_equity,
        distributions=flows[1:-1], moic=moic, irr=irr, simple_irr=simple_irr,
        entry_leverage=sum(faces) / spec.entry_ebitda,
        interest_coverage_y1=(rows[0].ebitda / rows[0].interest) if rows and rows[0].interest else float("inf"),
        attribution=attribution, checks=checks,
    )


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def money(x: float) -> str:
    return f"{x:,.1f}"


def render(spec: Spec, r: Result, grids: bool = True) -> None:
    u = spec.units
    print(f"{spec.target} — {spec.currency}, {u}")
    print(f"Entry {r.entry_date} → exit {r.exit_date}  ({r.hold_years:.2f} years)\n")

    print("OPERATING AND DEBT SCHEDULE (as used)")
    head = f"{'':>4}{'Revenue':>12}{'EBITDA':>12}{'Margin':>9}{'Interest':>11}{'Taxes':>10}" \
           f"{'Capex':>9}{'dNWC':>9}{'CashAvail':>12}{'Amort':>10}{'Sweep':>10}{'Cash':>9}"
    print(head)
    for row in r.rows:
        print(f"{row.year:>4}{money(row.revenue):>12}{money(row.ebitda):>12}"
              f"{row.ebitda / row.revenue:>8.1%}{money(row.interest):>11}{money(row.cash_taxes):>10}"
              f"{money(row.capex):>9}{money(row.d_nwc):>9}{money(row.cash_available):>12}"
              f"{money(row.mandatory):>10}{money(row.sweep):>10}{money(row.cash_balance):>9}")

    print("\nDEBT BALANCES (closing)")
    print(f"{'':>4}" + "".join(f"{t.name:>18}" for t in spec.tranches) + f"{'Total':>16}")
    for row in r.rows:
        print(f"{row.year:>4}" + "".join(f"{money(b):>18}" for b in row.closing_debt)
              + f"{money(sum(row.closing_debt)):>16}")

    print("\nENTRY")
    print(f"  Equity invested              {money(r.equity_invested)}")
    print(f"  Debt raised                  {money(sum(r.debt_faces))}")
    print(f"  Total leverage               {r.entry_leverage:.2f}x EBITDA")
    print(f"  Year-1 interest coverage     {r.interest_coverage_y1:.2f}x")

    print("\nEXIT")
    print(f"  Exit EBITDA                  {money(r.exit_ebitda)}")
    print(f"  Exit EV                      {money(r.exit_ev)}  ({spec.exit_multiple:.2f}x)")
    print(f"  Exit net debt                {money(r.exit_net_debt)}")
    print(f"  Exit equity                  {money(r.exit_equity)}")

    print("\nRETURNS")
    print(f"  MOIC                         {r.moic:.2f}x")
    print(f"  IRR (XIRR, dated flows)      {r.irr:.1%}")
    print(f"  IRR (annual compounding)     {r.simple_irr:.1%}   [= MOIC^(1/years) - 1]")
    print("  Cash flows used:")
    for d, a in [(spec.entry_date, -r.equity_invested)] + r.distributions + [(r.exit_date, r.exit_equity)]:
        print(f"    {d}  {money(a):>12}")

    print("\nATTRIBUTION OF EQUITY VALUE CHANGE")
    for label, value in r.attribution.items():
        print(f"  {label:<32}{money(value):>12}")
    print(f"  {'Total gain':<32}{money(r.exit_equity + sum(a for _, a in r.distributions) - r.equity_invested):>12}")

    if grids:
        entry_rows = [spec.entry_multiple - 1, spec.entry_multiple, spec.entry_multiple + 1]
        exit_cols = [spec.exit_multiple + delta for delta in (-2, -1, 0, 1, 2)]
        print("\nSENSITIVITY — IRR (rows: entry multiple, cols: exit multiple; debt faces fixed)")
        print(f"{'entry\\exit':>12}" + "".join(f"{c:>10.2f}x" for c in exit_cols))
        for em in entry_rows:
            cells = []
            for xm in exit_cols:
                try:
                    cells.append(f"{run(spec, entry_multiple=em, exit_multiple=xm).irr:>10.1%}")
                except ValueError:
                    cells.append(f"{'n/a':>10}")
            print(f"{em:>11.2f}x" + "".join(cells))

        hold_cols = sorted({max(1, spec.hold_years - 1), spec.hold_years, spec.hold_years + 1})
        print("\nSENSITIVITY — MOIC (rows: exit multiple, cols: hold years; operating path extends flat)")
        print(f"{'exit\\hold':>12}" + "".join(f"{h:>10}y" for h in hold_cols))
        for xm in exit_cols:
            cells = []
            for h in hold_cols:
                try:
                    cells.append(f"{run(spec, exit_multiple=xm, hold_years=h).moic:>10.2f}x")
                except ValueError:
                    cells.append(f"{'n/a':>10}")
            print(f"{xm:>11.2f}x" + "".join(cells))

        print("\nSENSITIVITY — IRR (rows: leverage vs base, cols: exit multiple; hold and entry fixed)")
        print(f"{'lev\\exit':>12}" + "".join(f"{c:>10.2f}x" for c in exit_cols))
        for scale in (0.75, 1.0, 1.25):
            cells = []
            for xm in exit_cols:
                try:
                    cells.append(f"{run(spec, exit_multiple=xm, leverage_scale=scale).irr:>10.1%}")
                except ValueError:
                    cells.append(f"{'n/a':>10}")
            print(f"{scale:>11.2f}x" + "".join(cells))

    print("\nCHECKS")
    for label, ok in r.checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def to_json(spec: Spec, r: Result) -> dict[str, Any]:
    return {
        "target": spec.target, "currency": spec.currency, "units": spec.units,
        "entry_date": str(r.entry_date), "exit_date": str(r.exit_date),
        "hold_years": r.hold_years, "entry_ev": r.entry_ev, "equity_invested": r.equity_invested,
        "debt_faces": r.debt_faces, "entry_leverage": r.entry_leverage,
        "interest_coverage_y1": r.interest_coverage_y1,
        "schedule": [row.__dict__ for row in r.rows],
        "exit_ebitda": r.exit_ebitda, "exit_ev": r.exit_ev, "exit_net_debt": r.exit_net_debt,
        "exit_equity": r.exit_equity, "moic": r.moic, "irr": r.irr,
        "attribution": r.attribution,
        "checks": [{"label": label, "pass": ok} for label, ok in r.checks],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path, help="JSON assumption spec (see module docstring)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-sensitivity", action="store_true", help="skip the sensitivity grids")
    args = ap.parse_args(argv)

    if not args.spec.exists():
        print(f"no such spec: {args.spec}", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        result = run(spec)
    except (ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(to_json(spec, result), indent=2))
    else:
        render(spec, result, grids=not args.no_sensitivity)

    return 0 if all(ok for _, ok in result.checks) else 1


if __name__ == "__main__":
    sys.exit(main())
