"""Glue: run production, run the GR&R study, load CSV data, assemble the PVT analysis."""
from __future__ import annotations

import csv
import logging
import random
from pathlib import Path

from . import stats
from .instruments import TestStation
from .sequence import UnitResult, run_unit, write_results
from .simulator import make_unit
from .spec import Spec

OPERATORS = ["OP-A", "OP-B", "OP-C"]


def setup_logging(out_dir: Path, verbose: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(out_dir / "station.log", mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger("npi")
    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)
    if verbose:
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        root.addHandler(sh)


def run_production(spec: Spec, n_units: int, seed: int, out_dir: Path,
                   defect_rate: float = 0.015) -> list[UnitResult]:
    rng = random.Random(seed)
    results: list[UnitResult] = []
    with TestStation(rng) as station:
        for k in range(1, n_units + 1):
            dut = make_unit(spec, rng, f"ECB{k:05d}", defect_rate)
            results.append(run_unit(spec, station, dut))
    write_results(out_dir, results)
    return results


def run_grr_study(spec: Spec, seed: int, parts: int = 10, replicates: int = 3,
                  operator_sigma_factor: float = 0.8) -> dict[str, list[list[list[float]]]]:
    """Crossed study: `parts` boards x 3 operators x `replicates`, for every item.

    Each operator gets a persistent bias (reproducibility); every measurement re-clamps the
    board, so seating error and instrument noise (repeatability) are included.
    Returns {item_id: data[part][operator][replicate]}.
    """
    rng = random.Random(seed)
    duts = [make_unit(spec, rng, f"GRR{k:02d}", defect_rate=0.0) for k in range(parts)]
    bias = {op: {i.id: rng.gauss(0, i.reprod_sigma * operator_sigma_factor) for i in spec.items}
            for op in OPERATORS}
    data = {i.id: [[[] for _ in OPERATORS] for _ in duts] for i in spec.items}
    with TestStation(rng, contact_fault_rate=0.0, comm_error_rate=0.0) as station:
        fx = station.fixture
        for pi, dut in enumerate(duts):
            for oi, op in enumerate(OPERATORS):
                fx.operator_bias = bias[op]
                for _ in range(replicates):
                    fx.load(dut)
                    fx.clamp(spec.items)
                    for item in spec.items:
                        v = station.instruments[item.instrument].measure(item)
                        data[item.id][pi][oi].append(v)
                    fx.release()
    return data


def load_results(out_dir: Path) -> tuple[list[dict], list[dict]]:
    with (out_dir / "results.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with (out_dir / "units.csv").open(encoding="utf-8") as f:
        units = list(csv.DictReader(f))
    return rows, units


def analyse(spec: Spec, rows: list[dict], units: list[dict],
            grr_data: dict[str, list[list[list[float]]]]) -> dict:
    """Compute everything the report needs and the PVT verdict."""
    crit = spec.pvt_criteria
    items = []
    for it in spec.items:
        vals = [float(r["value"]) for r in rows if r["item_id"] == it.id and r["value"] != ""]
        c = stats.cpk(vals, it.lsl, it.usl)
        g = stats.gauge_rr(grr_data[it.id], it.tolerance)
        items.append({
            "item": it, "n": len(vals),
            "mean": sum(vals) / len(vals), "stdev": stats.statistics.stdev(vals),
            "min": min(vals), "max": max(vals), "cpk": c,
            "fails": sum(1 for r in rows if r["item_id"] == it.id and r["result"] != "PASS"),
            "grr": g, "grr_verdict": stats.grr_verdict(
                g.pct_grr, crit["grr_pass_pct"], crit["grr_conditional_pct"]),
        })
    results = [u["result"] for u in units]
    y = stats.fpy(results)
    rate = stats.uph([float(u["cycle_time_s"]) for u in units])
    par = stats.pareto([u["first_fail"] for u in units])

    findings = []
    if y < crit["min_fpy_pct"]:
        findings.append(f"FPY {y:.1f}% is below {crit['min_fpy_pct']}%")
    if rate < crit["min_uph"]:
        findings.append(f"UPH {rate:.0f} is below {crit['min_uph']}")
    for r in items:
        if r["cpk"] is not None and r["cpk"] < crit["min_cpk"]:
            findings.append(f"{r['item'].id} {r['item'].name}: Cpk {r['cpk']:.2f} < {crit['min_cpk']}")
        if r["grr_verdict"] == "FAIL":
            findings.append(f"{r['item'].id} {r['item'].name}: %GRR {r['grr'].pct_grr:.1f}% not acceptable")
    conditional = [f"{r['item'].id} {r['item'].name} (%GRR {r['grr'].pct_grr:.1f}%)"
                   for r in items if r["grr_verdict"] == "CONDITIONAL"]
    return {"items": items, "fpy": y, "uph": rate, "pareto": par, "n_units": len(units),
            "n_pass": results.count("PASS"), "findings": findings, "conditional": conditional,
            "verdict": "PASS" if not findings else "FAIL"}
