"""Process statistics: Cpk, FPY, UPH, failure Pareto and Gauge R&R (ANOVA method)."""
from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass


def cpk(values: list[float], lsl: float | None, usl: float | None) -> float | None:
    """Process capability index. Supports one-sided limits. None if not computable."""
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    sigma = statistics.stdev(values)
    if sigma == 0:
        return None
    parts = []
    if usl is not None:
        parts.append((usl - mean) / (3 * sigma))
    if lsl is not None:
        parts.append((mean - lsl) / (3 * sigma))
    return min(parts)


def fpy(unit_results: list[str]) -> float:
    """First Pass Yield in %: units that passed on the first run / all units."""
    if not unit_results:
        return 0.0
    return 100.0 * sum(1 for r in unit_results if r == "PASS") / len(unit_results)


def uph(cycle_times_s: list[float]) -> float:
    """Units per hour of one station from the mean cycle time."""
    if not cycle_times_s:
        return 0.0
    return 3600.0 / statistics.fmean(cycle_times_s)


def pareto(first_fails: list[str]) -> list[tuple[str, int, float]]:
    """Failure Pareto: (item, count, cumulative %) sorted by count, ignoring passes."""
    counts = Counter(f for f in first_fails if f)
    total = sum(counts.values())
    out, cum = [], 0
    for item, n in counts.most_common():
        cum += n
        out.append((item, n, 100.0 * cum / total))
    return out


@dataclass
class GrrResult:
    repeatability: float      # variance
    reproducibility: float    # variance (operator + interaction)
    grr: float                # variance
    part: float               # variance
    pct_grr: float            # % of total study variation
    pct_tolerance: float      # 6*sigma_grr / tolerance
    ndc: int                  # number of distinct categories


def gauge_rr(data: list[list[list[float]]], tolerance: float) -> GrrResult:
    """Crossed Gauge R&R, ANOVA method.

    data[part][operator][replicate]. Needs >= 2 parts, operators, replicates, balanced.
    Negative variance components are floored at 0 (standard practice).
    """
    p, o, r = len(data), len(data[0]), len(data[0][0])
    if p < 2 or o < 2 or r < 2:
        raise ValueError("need at least 2 parts, 2 operators and 2 replicates")
    flat = [x for part in data for op in part for x in op]
    grand = statistics.fmean(flat)
    part_mean = [statistics.fmean([x for op in data[i] for x in op]) for i in range(p)]
    op_mean = [statistics.fmean([x for i in range(p) for x in data[i][j]]) for j in range(o)]
    cell_mean = [[statistics.fmean(data[i][j]) for j in range(o)] for i in range(p)]

    ss_part = o * r * sum((m - grand) ** 2 for m in part_mean)
    ss_op = p * r * sum((m - grand) ** 2 for m in op_mean)
    ss_cell = r * sum((cell_mean[i][j] - grand) ** 2 for i in range(p) for j in range(o))
    ss_int = ss_cell - ss_part - ss_op
    ss_err = sum((x - cell_mean[i][j]) ** 2 for i in range(p) for j in range(o) for x in data[i][j])

    ms_part = ss_part / (p - 1)
    ms_op = ss_op / (o - 1)
    ms_int = ss_int / ((p - 1) * (o - 1))
    ms_err = ss_err / (p * o * (r - 1))

    repeat = ms_err
    inter = max(0.0, (ms_int - ms_err) / r)
    oper = max(0.0, (ms_op - ms_int) / (p * r))
    part = max(0.0, (ms_part - ms_int) / (o * r))
    reprod = oper + inter
    grr = repeat + reprod
    total = grr + part
    pct = 100.0 * math.sqrt(grr / total) if total > 0 else 0.0
    pct_tol = 100.0 * 6 * math.sqrt(grr) / tolerance if tolerance > 0 else 0.0
    ndc = int(1.41 * math.sqrt(part / grr)) if grr > 0 else 99
    return GrrResult(repeat, reprod, grr, part, pct, pct_tol, ndc)


def grr_verdict(pct_grr: float, pass_pct: float = 10.0, cond_pct: float = 30.0) -> str:
    """AIAG-style acceptance: <=10% good, 10-30% conditional, >30% not acceptable."""
    if pct_grr <= pass_pct:
        return "PASS"
    if pct_grr <= cond_pct:
        return "CONDITIONAL"
    return "FAIL"
