"""Automated reports: Excel workbook (openpyxl) and PVT validation summary (Markdown)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .spec import Spec

HEAD = PatternFill("solid", fgColor="1E3A5F")
GREEN = PatternFill("solid", fgColor="C6EFCE")
AMBER = PatternFill("solid", fgColor="FFEB9C")
RED = PatternFill("solid", fgColor="FFC7CE")
THIN = Side(style="thin", color="BBBBBB")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _header(ws, row: int, labels: list[str]) -> None:
    for c, label in enumerate(labels, 1):
        cell = ws.cell(row=row, column=c, value=label)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEAD
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX


def _autowidth(ws, minimum: int = 10, maximum: int = 42) -> None:
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(minimum, min(maximum, width + 2))


def _cpk_fill(v, minimum: float):
    if v is None:
        return None
    if v >= minimum:
        return GREEN
    return AMBER if v >= 1.0 else RED


def _grr_fill(verdict: str):
    return {"PASS": GREEN, "CONDITIONAL": AMBER, "FAIL": RED}[verdict]


def write_excel(path: Path, spec: Spec, a: dict, rows: list[dict], units: list[dict]) -> None:
    crit = spec.pvt_criteria
    wb = Workbook()

    # --- Summary -------------------------------------------------------------
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"PVT Test Process Report - {spec.board} ({spec.revision})"
    ws["A1"].font = Font(bold=True, size=14, color="1E3A5F")
    meta = [("Station", spec.station), ("Units tested", a["n_units"]), ("Units passed", a["n_pass"]),
            ("FPY (%)", round(a["fpy"], 2)), ("UPH (simulated cycle time)", round(a["uph"], 1)),
            ("PVT verdict", a["verdict"])]
    for i, (k, v) in enumerate(meta, 3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws["B8"].fill = GREEN if a["verdict"] == "PASS" else RED
    ws["B8"].font = Font(bold=True)
    ws["A10"] = "Acceptance criteria"
    ws["A10"].font = Font(bold=True)
    crit_rows = [("FPY >= (%)", crit["min_fpy_pct"]), ("Cpk >=", crit["min_cpk"]),
                 ("%GRR pass <= / conditional <=", f"{crit['grr_pass_pct']} / {crit['grr_conditional_pct']}"),
                 ("UPH >=", crit["min_uph"])]
    for i, (k, v) in enumerate(crit_rows, 11):
        ws.cell(row=i, column=1, value=k)
        ws.cell(row=i, column=2, value=v)
    ws["A16"] = "Findings (blocking)"
    ws["A16"].font = Font(bold=True)
    r = 17
    for f in a["findings"] or ["None"]:
        ws.cell(row=r, column=1, value=f)
        r += 1
    ws.cell(row=r + 1, column=1, value="Conditional (improvement recommended)").font = Font(bold=True)
    r += 2
    for f in a["conditional"] or ["None"]:
        ws.cell(row=r, column=1, value=f)
        r += 1
    ws.cell(row=r + 1, column=1,
            value="Note: data comes from a simulated station (synthetic boards, no real hardware).").font = Font(italic=True)
    _autowidth(ws, 18, 60)

    # --- Limits & Cpk ---------------------------------------------------------
    ws = wb.create_sheet("Cpk")
    _header(ws, 1, ["ID", "Test item", "Test point", "Unit", "LSL", "USL", "N", "Mean", "StDev",
                    "Min", "Max", "Fails", "Cpk", "Status"])
    for i, rr in enumerate(a["items"], 2):
        it = rr["item"]
        vals = [it.id, it.name, it.test_point, it.unit, it.lsl, it.usl, rr["n"], rr["mean"],
                rr["stdev"], rr["min"], rr["max"], rr["fails"], rr["cpk"]]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=i, column=c, value=round(v, 4) if isinstance(v, float) else v)
            cell.border = BOX
        fill = _cpk_fill(rr["cpk"], crit["min_cpk"])
        ws.cell(row=i, column=13).fill = fill
        ws.cell(row=i, column=14, value="OK" if fill is GREEN else "REVIEW").border = BOX
    ws.freeze_panes = "A2"
    _autowidth(ws)

    # --- Pareto ---------------------------------------------------------------
    ws = wb.create_sheet("Failure Pareto")
    _header(ws, 1, ["First-fail item", "Name", "Count", "Cumulative %"])
    names = {i.id: i.name for i in spec.items}
    names["FIXTURE_CONTACT"] = "Fixture contact"
    for i, (item, n, cum) in enumerate(a["pareto"], 2):
        for c, v in enumerate([item, names.get(item, item), n, round(cum, 1)], 1):
            ws.cell(row=i, column=c, value=v).border = BOX
    if a["pareto"]:
        chart = BarChart()
        chart.title = "Failure Pareto (first fail per unit)"
        chart.y_axis.title = "Units"
        chart.add_data(Reference(ws, min_col=3, min_row=1, max_row=len(a["pareto"]) + 1), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(a["pareto"]) + 1))
        chart.height, chart.width = 8, 16
        ws.add_chart(chart, "F2")
    _autowidth(ws)

    # --- GR&R -----------------------------------------------------------------
    ws = wb.create_sheet("GRR")
    _header(ws, 1, ["ID", "Test item", "Repeatability var", "Reproducibility var", "GRR var", "Part var",
                    "%GRR (study var)", "%Tolerance", "ndc", "Verdict"])
    for i, rr in enumerate(a["items"], 2):
        g = rr["grr"]
        vals = [rr["item"].id, rr["item"].name, g.repeatability, g.reproducibility, g.grr, g.part,
                round(g.pct_grr, 2), round(g.pct_tolerance, 2), g.ndc, rr["grr_verdict"]]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=i, column=c, value=float(f"{v:.4g}") if isinstance(v, float) and c in (3, 4, 5, 6) else v)
            cell.border = BOX
        ws.cell(row=i, column=10).fill = _grr_fill(rr["grr_verdict"])
    ws.cell(row=len(a["items"]) + 3, column=1,
            value="Method: crossed ANOVA, 10 parts x 3 operators x 3 replicates. ndc >= 5 required.").font = Font(italic=True)
    ws.freeze_panes = "A2"
    _autowidth(ws)

    # --- Raw data -------------------------------------------------------------
    ws = wb.create_sheet("Raw data")
    cols = list(rows[0].keys())
    _header(ws, 1, cols)
    for i, row in enumerate(rows, 2):
        for c, k in enumerate(cols, 1):
            v = row[k]
            try:
                v = float(v) if k in ("lsl", "usl", "value") and v != "" else v
            except ValueError:
                pass
            cell = ws.cell(row=i, column=c, value=v)
            if k == "result" and v != "PASS":
                cell.fill = RED
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    _autowidth(ws)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def write_pvt_markdown(path: Path, spec: Spec, a: dict) -> None:
    crit = spec.pvt_criteria
    L = [f"# PVT Test Process Validation - {spec.board} ({spec.revision})", "",
         "> Generated by `python -m npi_test all`. Data is simulated (synthetic boards).", "",
         f"**Verdict: {a['verdict']}**", "",
         "## Result vs. criteria", "",
         "| Metric | Result | Criterion | Status |", "|---|---|---|---|",
         f"| FPY | {a['fpy']:.1f}% | >= {crit['min_fpy_pct']}% | {'OK' if a['fpy'] >= crit['min_fpy_pct'] else 'FAIL'} |",
         f"| UPH | {a['uph']:.0f} | >= {crit['min_uph']} | {'OK' if a['uph'] >= crit['min_uph'] else 'FAIL'} |",
         f"| Units tested / passed | {a['n_units']} / {a['n_pass']} | - | - |", "",
         "## Per test item", "",
         "| ID | Item | Cpk | %GRR | ndc | GRR verdict |", "|---|---|---|---|---|---|"]
    for r in a["items"]:
        cpk = "n/a" if r["cpk"] is None else f"{r['cpk']:.2f}"
        L.append(f"| {r['item'].id} | {r['item'].name} | {cpk} | {r['grr'].pct_grr:.1f}% | "
                 f"{r['grr'].ndc} | {r['grr_verdict']} |")
    L += ["", "## Findings", ""]
    L += [f"- {f}" for f in a["findings"]] or ["- No blocking findings."]
    L += ["", "## Improvement proposals", ""]
    worst = sorted((r for r in a["items"] if r["grr_verdict"] != "PASS"),
                   key=lambda r: -r["grr"].pct_grr)
    for r in worst:
        L.append(f"- **{r['item'].id} {r['item'].name}** (%GRR {r['grr'].pct_grr:.1f}%): "
                 "increase averaging/sample count, shield and shorten the probe ground lead, "
                 "re-check pogo-pin seating, then repeat the GR&R study.")
    for r in a["items"]:
        if r["cpk"] is not None and r["cpk"] < crit["min_cpk"]:
            L.append(f"- **{r['item'].id} {r['item'].name}** (Cpk {r['cpk']:.2f}): review the process "
                     "centering/spread with design before MP; do not widen the limits to hide it.")
    if a["pareto"]:
        top = a["pareto"][0]
        L.append(f"- Top failure contributor: **{top[0]}** ({top[1]} units). Verify with a failure analysis "
                 "sample before changing limits.")
    L += ["", "## Deliverables", "",
          "- Test specification: `config/test_spec.json`",
          "- Raw data: `output/results.csv`, `output/units.csv`; Excel report: `output/pvt_report.xlsx`", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")
