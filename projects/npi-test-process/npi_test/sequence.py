"""Test Sequence runner: executes Test Items in order with retry and troubleshooting logs."""
from __future__ import annotations

import csv
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from .instruments import DeviceUnderTest, InstrumentError, TestStation
from .spec import Spec

log = logging.getLogger("npi.sequence")

RESULT_FIELDS = ["serial", "item_id", "item_name", "test_point", "unit", "lsl", "usl",
                 "value", "result", "attempts"]
UNIT_FIELDS = ["serial", "result", "first_fail", "cycle_time_s", "contact_retries"]


@dataclass
class UnitResult:
    serial: str
    passed: bool
    first_fail: str
    cycle_time_s: float
    contact_retries: int
    rows: list[dict]


def run_unit(spec: Spec, station: TestStation, dut: DeviceUnderTest,
             stop_on_fail: bool = False) -> UnitResult:
    """Run the full sequence on one board. Cycle time is simulated, not slept."""
    fx = station.fixture
    fx.load(dut)
    cycle = spec.cycle_overhead_s
    rows: list[dict] = []
    first_fail = ""
    retries = 0

    # 1) Clamp + contact check; re-seat on a bad contact (first troubleshooting step)
    while not fx.clamp(spec.items):
        retries += 1
        cycle += 3.0
        log.warning("%s: bad contact, re-seating (%d/%d)", dut.serial, retries, spec.max_contact_retries)
        if retries > spec.max_contact_retries:
            log.error("%s: contact failed after %d re-seats", dut.serial, retries - 1)
            fx.release()
            return UnitResult(dut.serial, False, "FIXTURE_CONTACT", cycle, retries, rows)

    # 2) Measure each Test Item
    for item in spec.items:
        instrument = station.instruments[item.instrument]
        value = None
        attempts = 0
        while attempts <= spec.max_instrument_retries:
            attempts += 1
            cycle += item.time_s if attempts == 1 else item.time_s * 0.5
            try:
                value = instrument.measure(item)
                break
            except InstrumentError as exc:
                log.warning("%s %s: %s (attempt %d)", dut.serial, item.id, exc, attempts)
        if value is None:
            result, shown = "ERROR", ""
        else:
            result, shown = ("PASS" if item.judge(value) else "FAIL"), round(value, 5)
        if result != "PASS" and not first_fail:
            first_fail = item.id
        rows.append({"serial": dut.serial, "item_id": item.id, "item_name": item.name,
                     "test_point": item.test_point, "unit": item.unit,
                     "lsl": "" if item.lsl is None else item.lsl,
                     "usl": "" if item.usl is None else item.usl,
                     "value": shown, "result": result, "attempts": attempts})
        log.debug("%s %s %s=%s %s", dut.serial, item.id, item.name, shown, result)
        if result != "PASS" and stop_on_fail:
            break

    fx.release()
    passed = not first_fail
    log.info("%s %s (%.1fs)", dut.serial, "PASS" if passed else f"FAIL@{first_fail}", cycle)
    return UnitResult(dut.serial, passed, first_fail, cycle, retries, rows)


def write_results(out_dir: Path, results: list[UnitResult]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rpath, upath = out_dir / "results.csv", out_dir / "units.csv"
    with rpath.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, RESULT_FIELDS)
        w.writeheader()
        for r in results:
            w.writerows(r.rows)
    with upath.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, UNIT_FIELDS)
        w.writeheader()
        for r in results:
            w.writerow({"serial": r.serial, "result": "PASS" if r.passed else "FAIL",
                        "first_fail": r.first_fail, "cycle_time_s": round(r.cycle_time_s, 2),
                        "contact_retries": r.contact_retries})
    return rpath, upath
