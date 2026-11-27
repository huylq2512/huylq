"""Standalone GR&R calculator: read measurement CSV, report %GRR / %tolerance / ndc per item.

CSV columns: part, operator, value; optional item (defaults to one item) and replicate.
Rows of the same part/operator/item are taken as replicates in file order.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .spec import Spec
from .stats import GrrResult, gauge_rr, grr_verdict

REQUIRED = {"part", "operator", "value"}


def load_measurements(path: Path) -> dict[str, list[list[list[float]]]]:
    """Return {item: data[part][operator][replicate]}; raises ValueError on bad/unbalanced input."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing column(s): {', '.join(sorted(missing))}")
        cells: dict[str, dict[tuple[str, str], list[float]]] = defaultdict(lambda: defaultdict(list))
        for n, row in enumerate(reader, start=2):
            try:
                value = float(row["value"])
            except ValueError:
                raise ValueError(f"line {n}: value {row['value']!r} is not a number") from None
            cells[row.get("item") or "ITEM"][(row["part"], row["operator"])].append(value)

    out: dict[str, list[list[list[float]]]] = {}
    for item, cell in cells.items():
        parts = sorted({p for p, _ in cell})
        ops = sorted({o for _, o in cell})
        reps = {len(cell.get((p, o), [])) for p in parts for o in ops}
        if len(reps) != 1 or 0 in reps:
            raise ValueError(f"item {item}: study is not balanced (every part x operator needs the same replicates)")
        out[item] = [[cell[(p, o)] for o in ops] for p in parts]
    return out


def analyse_file(path: Path, tolerance: float = 0.0, spec: Spec | None = None) -> list[tuple[str, GrrResult, str]]:
    tol_by_item = {i.id: i.tolerance for i in spec.items} if spec else {}
    return [(item, (g := gauge_rr(data, tol_by_item.get(item, tolerance))), grr_verdict(g.pct_grr))
            for item, data in load_measurements(path).items()]


def format_results(results: list[tuple[str, GrrResult, str]]) -> str:
    lines = [f"{'item':<8}{'%GRR':>8}{'%tol':>8}{'ndc':>5}  verdict"]
    lines += [f"{item:<8}{g.pct_grr:>8.1f}{g.pct_tolerance:>8.1f}{g.ndc:>5}  {v}" for item, g, v in results]
    return "\n".join(lines)
