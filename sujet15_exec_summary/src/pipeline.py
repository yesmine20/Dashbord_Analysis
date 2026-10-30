"""End-to-end run: CSV -> detection -> JSON -> LLM text -> number check -> Markdown (AI draft).

Examples
  python -m src.pipeline --scenario S02
  python -m src.pipeline --channel Reseller --start 2018-01 --end 2018-12 --provider openai
  python -m src.pipeline --all
"""
import argparse
import json
from pathlib import Path

from . import config
from .check_numbers import check_text
from .detect import build_payload
from .llm_client import default_provider, generate
from .load_data import Scope, load_clean, reconcile
from .report import render_markdown

SCENARIO_FILE = config.ROOT / "scenarios" / "scenarios.json"


def run(df, scope: Scope, name: str, provider: str | None = None, out_dir: Path = config.OUTPUT_DIR,
        write: bool = True) -> dict:
    provider = (provider or default_provider()).lower()
    payload = build_payload(df, scope)
    summary = generate("summary", payload, provider)
    root_cause = generate("root_cause", payload, provider)
    if payload["status"] == "ok":
        check = check_text(summary + "\n" + root_cause, payload)
    else:
        check = None
    md = render_markdown(name, payload, summary, root_cause, check, provider)
    result = {"name": name, "payload": payload, "summary": summary, "root_cause": root_cause,
              "check": check, "markdown": md}
    if write:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{name}_input.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / f"{name}_report.md").write_text(md, encoding="utf-8")
    return result


def load_scenarios() -> list[dict]:
    return json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", help="scenario id from scenarios/scenarios.json (e.g. S02)")
    ap.add_argument("--all", action="store_true", help="run every scenario")
    ap.add_argument("--channel"); ap.add_argument("--group"); ap.add_argument("--category")
    ap.add_argument("--start", help="YYYY-MM"); ap.add_argument("--end", help="YYYY-MM")
    ap.add_argument("--provider", help="mock | openai | azure | anthropic | groq (default: LLM_PROVIDER or mock)")
    ap.add_argument("--out-dir", default=str(config.OUTPUT_DIR))
    ap.add_argument("--data", default=str(config.DATA_PATH))
    a = ap.parse_args()

    df = load_clean(a.data)
    rec = reconcile(df)
    bad = [k for k, v in rec.items() if not v["ok"]]
    print("Data check vs Power BI totals:", "OK" if not bad else f"MISMATCH on {bad}")

    jobs = []
    if a.all:
        jobs = [(s["id"], Scope(**s["scope"])) for s in load_scenarios()]
    elif a.scenario:
        found = {s["id"]: s for s in load_scenarios()}
        if a.scenario not in found:
            raise SystemExit(f"Unknown scenario {a.scenario}. Available: {sorted(found)}")
        jobs = [(a.scenario, Scope(**found[a.scenario]["scope"]))]
    else:
        jobs = [("custom", Scope(a.channel, a.group, a.category, a.start, a.end))]

    for name, scope in jobs:
        r = run(df, scope, name, a.provider, Path(a.out_dir))
        status = r["payload"]["status"]
        n_anom = len(r["payload"].get("anomalies", []))
        chk = "-" if r["check"] is None else ("OK" if r["check"]["ok"] else f"{len(r['check']['ungrounded'])} ungrounded")
        print(f"{name}: status={status} anomalies={n_anom} number_check={chk}")


if __name__ == "__main__":
    main()
