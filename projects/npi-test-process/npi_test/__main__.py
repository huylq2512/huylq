"""CLI: python -m npi_test {run,report,all}"""
from __future__ import annotations

import argparse
from pathlib import Path

from .report import write_excel, write_pvt_markdown
from .spec import load_spec
from .workflow import analyse, load_results, run_grr_study, run_production, setup_logging

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(prog="npi_test", description="NPI test process toolkit (simulated station)")
    ap.add_argument("command", choices=["run", "report", "all"],
                    help="run = test units, report = analyse + Excel/Markdown, all = both")
    ap.add_argument("--spec", type=Path, default=ROOT / "config" / "test_spec.json")
    ap.add_argument("--out", type=Path, default=ROOT / "output")
    ap.add_argument("--units", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--defect-rate", type=float, default=0.015)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    setup_logging(args.out, args.verbose)

    if args.command in ("run", "all"):
        res = run_production(spec, args.units, args.seed, args.out, args.defect_rate)
        print(f"Tested {len(res)} units -> {args.out / 'results.csv'}")

    if args.command in ("report", "all"):
        rows, units = load_results(args.out)
        grr = run_grr_study(spec, args.seed + 1)
        a = analyse(spec, rows, units, grr)
        write_excel(args.out / "pvt_report.xlsx", spec, a, rows, units)
        write_pvt_markdown(ROOT / "docs" / "PVT_VALIDATION.md", spec, a)
        print(f"FPY {a['fpy']:.1f}%  UPH {a['uph']:.0f}  PVT verdict: {a['verdict']}")
        for f in a["findings"]:
            print(f"  - {f}")
        print(f"Excel: {args.out / 'pvt_report.xlsx'}")


if __name__ == "__main__":
    main()
