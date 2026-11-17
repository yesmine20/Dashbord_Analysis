"""Human validation step: a reviewer checks the AI draft and marks it VALIDATED or NEEDS REVISION.

  python -m src.validate outputs/S02_report.md --reviewer "Your Name"
The decision and the checklist are written into the report and appended to outputs/validation_log.csv.
"""
import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

from . import config

CHECKLIST = [
    "Every figure matches the Power BI report or the JSON input",
    "No cause is stated as a fact (only 'possible contributing factors')",
    "The scope (channel, region, category, period) is clear for every figure",
    "The tone is suitable for a C-level audience",
]


def apply_validation(md: str, reviewer: str, checklist: dict, notes: str = "") -> tuple[str, dict]:
    decision = "VALIDATED" if all(checklist.values()) else "NEEDS REVISION"
    info = {"reviewer": reviewer, "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "decision": decision, "notes": notes, "checklist": checklist}
    md = re.sub(r"\*\*Status: .*?\*\*", f"**Status: {decision} by {reviewer} on {info['date']}**", md, count=1)
    head = md.split("## Human validation")[0]
    block = ["## Human validation", "", f"- Reviewer: {reviewer}", f"- Date: {info['date']}",
             f"- Decision: {decision}", f"- Notes: {notes or '-'}"]
    block += [f"- [{'x' if v else ' '}] {q}" for q, v in checklist.items()]
    return head + "\n".join(block) + "\n", info


def log(info: dict, report: str):
    path = config.OUTPUT_DIR / "validation_log.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "report", "reviewer", "decision", "notes"])
        w.writerow([info["date"], report, info["reviewer"], info["decision"], info["notes"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    path = Path(a.report)
    print(path.read_text(encoding="utf-8"))
    checklist = {}
    for q in CHECKLIST:
        checklist[q] = input(f"{q}? [y/N] ").strip().lower() in ("y", "yes", "o", "oui")
    md, info = apply_validation(path.read_text(encoding="utf-8"), a.reviewer, checklist, a.notes)
    path.write_text(md, encoding="utf-8")
    log(info, path.name)
    print(f"-> {info['decision']}")


if __name__ == "__main__":
    main()
