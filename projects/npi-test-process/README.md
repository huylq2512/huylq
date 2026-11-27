# Production Test Program - Electronic Control Board

Practice project (6 months): test program for a manufacturer's electronic control board (ECB-100),
from Test Specification to PVT validation.

> **Important:** the station runs on a *simulator* (synthetic boards, simulated instruments and
> cycle time). The statistics, sequence logic and reports are real code; the measurements are not
> from physical hardware. To use real equipment, implement the `Instrument` interface in
> `npi_test/instruments.py` for your DMM/counter/scope (e.g. PyVISA) and keep the rest unchanged.

## What it covers

| Phase | Where |
|---|---|
| Test Specification: items, test points, PASS/FAIL limits | `config/test_spec.json`, `npi_test/spec.py` |
| Test Station: equipment drivers, fixture/jig, parameters | `npi_test/instruments.py` |
| Test Sequence, limits, retry, debug/troubleshooting log | `npi_test/sequence.py`, `output/station.log` |
| Data processing + automated Excel report (Python/Excel) | `npi_test/report.py`, `output/pvt_report.xlsx` |
| GR&R (crossed ANOVA), Cpk, FPY, UPH, failure Pareto | `npi_test/stats.py`, `npi_test/workflow.py` |
| Standalone GR&R calculator for any measurement CSV | `npi_test/grr_tool.py` |
| PVT validation, improvement proposals | `docs/PVT_VALIDATION.md` (generated) |

## Run

```powershell
pip install -r requirements.txt
python -m npi_test all            # test 300 units + GR&R study + reports
python -m npi_test all --units 500 --seed 7 -v
python -m npi_test grr --input data.csv   # GR&R from your own measurements (part, operator, value[, item])
python -m pytest -q               # unit tests
```

Outputs: `output/results.csv`, `output/units.csv`, `output/station.log`, `output/pvt_report.xlsx`
(sheets: Summary, Cpk, Failure Pareto with chart, GRR, Raw data) and `docs/PVT_VALIDATION.md`.

## Method notes

- **Cpk** = min((USL-mean)/3s, (mean-LSL)/3s); one-sided limits supported (ripple has USL only).
  Computed over all valid measurements, so a few real defects can pull Cpk down. Results vary by
  `--seed` for this reason (e.g. one gross outlier on a tight item can flip the verdict).
- **FPY** = units passing every item on the first run / units tested.
- **UPH** = 3600 / mean cycle time of one station. Cycle time is simulated from the per-item times.
- **GR&R**: 10 boards x 3 operators x 3 replicates per item, ANOVA with interaction; %GRR is the
  share of total study variation; ndc >= 5 expected. Acceptance: <= 10% good, 10-30% conditional,
  > 30% not acceptable.
- **PVT pass** needs: FPY >= 95%, Cpk >= 1.33 on every item, no item with %GRR > 30%, UPH >= 90.
  Conditional GR&R items do not block but get an improvement proposal in the report.

## Layout

```
config/test_spec.json      limits + PVT criteria
npi_test/                  spec, instruments, sequence, simulator, stats, grr_tool, workflow, report, CLI
tests/test_npi.py          unit tests (limits, Cpk, FPY/UPH/Pareto, GR&R, sequence, contact retry)
docs/                      generated PVT validation
output/                    generated data and reports
```
