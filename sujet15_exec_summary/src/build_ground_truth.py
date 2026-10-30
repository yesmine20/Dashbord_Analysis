"""Build the recipe matrix (Ground Truth): scenario, filters, TRUE values from the data, expected LLM behaviour.

  python -m src.build_ground_truth     ->  scenarios/ground_truth.csv  (';' separated, opens directly in French Excel)

The last columns are meant to be filled by a human after running the LLM on each scenario.
"""
import csv
import json

from . import config
from .detect import build_payload
from .load_data import Scope, load_clean
from .pipeline import load_scenarios

COLUMNS = ["id", "type", "description", "filters", "true_sales", "true_profit", "true_margin",
           "anomalies_detected_by_engine", "expected_llm_behaviour",
           "llm_answer_pasted_here", "figures_correct (0/1)", "anomalies_covered (0/1)",
           "no_invented_cause (0/1)", "tone_c_level (0/1)", "reviewer", "comments"]


def _short(a: dict) -> str:
    m = a["metrics"]
    d = lambda x: x["display"]
    if a["rule"] == "R1_margin_alert":
        return f"{a['id']} margin alert {a['period']}: margin {d(m['margin_pct'])}, profit {d(m['profit'])}"
    if a["rule"] == "R2_sales_variation":
        return f"{a['id']} sales variation {a['period']}: {d(m['sales_change'])} ({d(m['sales_change_pct'])})"
    if a["rule"] == "R3_like_for_like_yoy":
        return f"{a['id']} like-for-like {a['period']}: {d(m['sales_change'])} ({d(m['sales_change_pct'])})"
    if a["rule"] == "R4_channel_gap":
        return f"{a['id']} channel gap: {d(m['margin_gap_pts'])}"
    return f"{a['id']} {m['dimension']} outlier {m['segment']}: margin {d(m['margin_pct'])}"


def main():
    df = load_clean()
    rows = []
    for s in load_scenarios():
        p = build_payload(df, Scope(**s["scope"]))
        filters = json.dumps({k: v for k, v in s["scope"].items() if v}, ensure_ascii=False) or "{}"
        if p["status"] != "ok":
            row = [s["id"], s["type"], s["description"], filters, "", "", "", "none (no data)",
                   "Answer must be exactly: No data available. No figure, no invented period or region."]
        else:
            k = p["kpis"]
            anomalies = " | ".join(_short(a) for a in p["anomalies"]) or "none"
            if s["type"] == "no_anomaly" or not p["anomalies"]:
                exp = ("Must report sales, profit and margin, state that no anomaly exceeded the thresholds, "
                       "and must NOT invent an anomaly or a cause.")
            else:
                exp = (f"Must report sales {k['sales']['display']}, profit {k['profit']['display']}, margin "
                       f"{k['profit_margin_pct']['display']}; must cover the main anomalies listed; every figure must come "
                       "from the JSON; causes only as 'possible contributing factors'.")
            row = [s["id"], s["type"], s["description"], filters, k["sales"]["value"], k["profit"]["value"],
                   k["profit_margin_pct"]["value"], anomalies, exp]
        rows.append(row + [""] * (len(COLUMNS) - len(row)))
    out = config.ROOT / "scenarios" / "ground_truth.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLUMNS)
        w.writerows(rows)
    print(f"{len(rows)} scenarios -> {out}")


if __name__ == "__main__":
    main()
