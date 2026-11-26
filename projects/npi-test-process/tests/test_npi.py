import random
from pathlib import Path

import pytest

from npi_test import stats
from npi_test.instruments import TestStation
from npi_test.sequence import run_unit
from npi_test.simulator import make_unit
from npi_test.spec import load_spec

SPEC = Path(__file__).resolve().parent.parent / "config" / "test_spec.json"


def test_spec_loads_and_judges():
    spec = load_spec(SPEC)
    assert len(spec.items) == 8
    t02 = spec.item("T02")
    assert t02.judge(3.30) and t02.judge(3.20) and t02.judge(3.40)  # limits inclusive
    assert not t02.judge(3.19) and not t02.judge(3.41)
    ripple = spec.item("T08")  # one-sided (USL only)
    assert ripple.judge(0.0) and ripple.judge(50.0) and not ripple.judge(50.1)


def test_cpk_known_value():
    vals = [9, 10, 11] * 10  # mean 10, sample stdev ~ 0.8305
    sigma = stats.statistics.stdev(vals)
    assert stats.cpk(vals, 7.0, 13.0) == pytest.approx(3 / (3 * sigma))
    assert stats.cpk(vals, None, 13.0) == pytest.approx(3 / (3 * sigma))  # one-sided
    assert stats.cpk([5.0, 5.0], 0, 10) is None  # zero spread


def test_fpy_uph_pareto():
    assert stats.fpy(["PASS", "PASS", "FAIL", "PASS"]) == 75.0
    assert stats.uph([30.0, 40.0]) == pytest.approx(3600 / 35)
    p = stats.pareto(["", "T02", "T02", "T05", ""])
    assert p[0][:2] == ("T02", 2) and p[-1][2] == pytest.approx(100.0)


def _grr_data(rng, repeat_sigma, op_sigma, parts=10, ops=3, reps=3):
    part_vals = [rng.gauss(0, 1.0) for _ in range(parts)]
    op_bias = [rng.gauss(0, op_sigma) for _ in range(ops)]
    return [[[part_vals[i] + op_bias[j] + rng.gauss(0, repeat_sigma) for _ in range(reps)]
             for j in range(ops)] for i in range(parts)]


def test_grr_good_vs_bad_gauge():
    rng = random.Random(1)
    good = stats.gauge_rr(_grr_data(rng, 0.02, 0.01), tolerance=6.0)
    bad = stats.gauge_rr(_grr_data(rng, 0.8, 0.5), tolerance=6.0)
    assert good.pct_grr < 10 < bad.pct_grr
    assert stats.grr_verdict(good.pct_grr) == "PASS"
    assert stats.grr_verdict(bad.pct_grr) in ("CONDITIONAL", "FAIL")
    assert good.ndc > bad.ndc


def test_grr_zero_noise():
    data = [[[float(i)] * 2 for _ in range(2)] for i in range(5)]  # identical across ops/reps
    g = stats.gauge_rr(data, tolerance=10)
    assert g.grr == pytest.approx(0.0) and g.pct_grr == pytest.approx(0.0)


def test_grr_needs_enough_data():
    with pytest.raises(ValueError):
        stats.gauge_rr([[[1.0, 1.0]]], 1.0)


def test_sequence_good_and_defective_unit():
    spec = load_spec(SPEC)
    rng = random.Random(3)
    with TestStation(rng, contact_fault_rate=0.0, comm_error_rate=0.0) as st:
        good = make_unit(spec, rng, "G1", defect_rate=0.0)
        for it in spec.items:  # force a perfect board
            good.true_values[it.id] = it.target
        ok = run_unit(spec, st, good)
        assert ok.passed and len(ok.rows) == 8 and ok.first_fail == ""

        bad = make_unit(spec, rng, "B1", defect_rate=0.0)
        for it in spec.items:
            bad.true_values[it.id] = it.target
        bad.true_values["T02"] = 2.5  # 3V3 rail short
        res = run_unit(spec, st, bad)
        assert not res.passed and res.first_fail == "T02"


def test_stop_on_fail_and_contact_failure():
    spec = load_spec(SPEC)
    rng = random.Random(5)
    with TestStation(rng, contact_fault_rate=0.0, comm_error_rate=0.0) as st:
        dut = make_unit(spec, rng, "S1", defect_rate=0.0)
        dut.true_values["T01"] = 0.0
        res = run_unit(spec, st, dut, stop_on_fail=True)
        assert len(res.rows) == 1 and res.first_fail == "T01"
    with TestStation(rng, contact_fault_rate=1.0, comm_error_rate=0.0) as st:  # jig always bad
        res = run_unit(spec, st, make_unit(spec, rng, "C1", 0.0))
        assert res.first_fail == "FIXTURE_CONTACT" and res.rows == []
