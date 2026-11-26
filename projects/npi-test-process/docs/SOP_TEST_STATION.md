# SOP - Test Station TS-01 (ECB-100 Electronic Control Board)

| | |
|---|---|
| Document | SOP-TS01-ECB100 |
| Applies to | ECB-100 Rev B, functional test, PVT -> MP hand-over |
| Spec | `config/test_spec.json` (single source of truth for limits) |

## 1. Station setup

| Item | Requirement |
|---|---|
| PC | Test software (`npi_test`), Python 3.10+, log folder writable |
| DMM | Connected to PC, self-test OK, calibration date valid |
| Frequency counter | Connected to TP5 via fixture |
| Oscilloscope | 20 MHz bandwidth limit ON, short ground spring on TP2 |
| Fixture/Jig | Pogo pins clean, no bent pins, clamp pressure per jig drawing |
| Power | 5.0 V +/- 0.05 V, current limit set |

## 2. Test items and PASS/FAIL

| ID | Test item | Test point | Limits |
|---|---|---|---|
| T01 | 5V input rail | TP1 | 4.85 - 5.15 V |
| T02 | 3V3 rail | TP2 | 3.20 - 3.40 V |
| T03 | 1V8 core rail | TP3 | 1.75 - 1.85 V |
| T04 | Idle current | TP4 | 20 - 60 mA |
| T05 | Load current | TP4 | 120 - 200 mA |
| T06 | MCU clock frequency | TP5 | 15.95 - 16.05 MHz |
| T07 | Sensor ADC output | TP6 | 1190 - 1310 mV |
| T08 | 3V3 rail ripple | TP2 | <= 50 mV |

A unit is PASS only when every item is PASS. Limits are inclusive. Never edit limits without an
approved change request and a new GR&R/Cpk review.

## 3. Operating procedure

1. Scan/enter the serial number.
2. Place the board in the fixture and close the clamp. The contact check runs automatically;
   on a bad contact the software re-seats up to 2 times, then marks `FIXTURE_CONTACT`.
3. The sequence runs T01 -> T08 automatically. Do not open the clamp during the test.
4. Read the result: **PASS** -> move to the PASS tray; **FAIL** -> tag with the failing item ID and
   move to the FAIL tray. Do not retest a FAIL more than once; a second FAIL goes to repair.
5. Data is saved to `output/results.csv` and `output/units.csv`; the log is `output/station.log`.

## 4. Daily checks

- Run the golden sample (known-good board) at shift start; all items must PASS and stay within
  +/- 3 sigma of its recorded values. Stop the line if not.
- Check pogo pins and clean when contact retries rise above 2% of units.
- Review FPY and top failure items every shift.

## 5. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `FIXTURE_CONTACT` on many units | Dirty/worn pogo pins, low clamp pressure | Clean pins, check pressure, replace pins after the rated cycles |
| `ERROR` result / "timeout" in log | Instrument cable, GPIB/USB/COM issue | Reseat cable, check instrument address, restart instrument, rerun |
| All units fail one item | Station fault (not product) | Run golden sample; recalibrate/replace instrument or probe |
| T08 ripple unstable | Long probe ground lead, noise pickup | Use ground spring, shorten lead, enable averaging |
| Cpk of an item drifts down | Process shift or instrument drift | Compare with golden sample trend, notify engineering |
| FPY drops suddenly | New material lot or fixture damage | Check Pareto first, then fixture, then lot |

## 6. Monitoring targets (MP)

| Metric | Target |
|---|---|
| FPY | >= 95% |
| Cpk (each item) | >= 1.33 |
| %GRR (each item) | <= 10% good, <= 30% conditional |
| UPH per station | >= 90 |

Repeat the GR&R study after any change of fixture, instrument, probe or software version.

## 7. Revision history

| Rev | Change |
|---|---|
| A | First release for PVT validation |
