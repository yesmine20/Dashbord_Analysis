import json
import unittest
from unittest.mock import patch

import pandas as pd

from src import mock_llm
from src.check_numbers import check_text
from src.detect import build_payload
from src.llm_client import PROVIDERS, generate
from src.load_data import Scope
from src.validate import apply_validation, CHECKLIST

def make_test_frame():
    """Small deterministic fixture: unit tests do not require a live model or CSV."""
    rows = []
    for month in pd.date_range("2018-01-01", "2020-06-01", freq="MS"):
        scale = 1.3 if month >= pd.Timestamp("2020-01-01") else 1.0
        for category in ("Components", "Bikes"):
            for group in ("North America", "Europe"):
                for channel, margin in (("Internet", 0.45), ("Reseller", 0.15)):
                    sales = 500_000 * scale
                    profit = -100_000 if month == pd.Timestamp("2019-07-01") else sales * margin
                    rows.append({"date": month, "Year": month.year, "Category": category,
                                 "Group": group, "Channel": channel, "Sales": sales,
                                 "Profit": profit, "Cost": sales - profit, "Orders": 100})
    return pd.DataFrame(rows)


DF = make_test_frame()


def anomalies(payload, rule):
    return [a for a in payload["anomalies"] if a["rule"] == rule]


class TestData(unittest.TestCase):
    def test_period(self):
        self.assertEqual(DF["date"].min().strftime("%Y-%m"), "2018-01")
        self.assertEqual(DF["date"].max().strftime("%Y-%m"), "2020-06")


class TestDetection(unittest.TestCase):
    def setUp(self):
        self.p = build_payload(DF, Scope())

    def test_negative_margin_july_2019(self):
        periods = {a["period"]: a for a in anomalies(self.p, "R1_margin_alert")}
        self.assertIn("2019-07", periods)
        self.assertTrue(periods["2019-07"]["metrics"]["negative_profit"])

    def test_channel_gap(self):
        a = anomalies(self.p, "R4_channel_gap")[0]
        self.assertEqual(a["metrics"]["lower_margin_channel"]["channel"], "Reseller")

    def test_like_for_like_window(self):
        a = anomalies(self.p, "R3_like_for_like_yoy")[0]
        self.assertEqual(a["period"], "2020-01 to 2020-06")
        self.assertEqual(a["direction"], "positive")

    def test_partial_years_are_declared(self):
        self.assertTrue(any("less than 12 months" in l for l in self.p["limitations"]))

    def test_no_anomaly_scenario(self):
        p = build_payload(DF, Scope(channel="Internet", category="Components", start="2018-07", end="2019-06"))
        self.assertEqual(p["status"], "ok")
        self.assertEqual(p["anomalies"], [])

    def test_ids_unique(self):
        ids = [a["id"] for a in self.p["anomalies"]]
        self.assertEqual(len(ids), len(set(ids)))


class TestGuardrails(unittest.TestCase):
    def test_groq_provider_is_available(self):
        self.assertIn("groq", PROVIDERS)

    def test_root_cause_without_anomalies_skips_llm(self):
        payload = {"status": "ok", "anomalies": []}
        with patch("src.llm_client.mock_llm.root_cause") as mock_root_cause:
            self.assertEqual(
                generate("root_cause", payload, "groq"),
                "No anomaly to explain: nothing exceeded the thresholds in this scope.",
            )
            mock_root_cause.assert_not_called()

    def test_unknown_region_is_no_data(self):
        p = build_payload(DF, Scope(group="Germany"))
        self.assertEqual(p["status"], "no_data")
        self.assertEqual(generate("summary", p, "mock"), "No data available")

    def test_out_of_range_period_is_no_data(self):
        p = build_payload(DF, Scope(start="2023-01", end="2023-12"))
        self.assertEqual(p["status"], "no_data")

    def test_checker_accepts_grounded_text(self):
        p = build_payload(DF, Scope(channel="Reseller"))
        text = mock_llm.executive_summary(p) + mock_llm.root_cause(p)
        self.assertTrue(check_text(text, p)["ok"])

    def test_checker_flags_invented_figure(self):
        p = build_payload(DF, Scope())
        res = check_text("Sales reached $99.99M and margin was 63.2%.", p)
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["ungrounded"]), 2)

    def test_json_is_serialisable(self):
        json.dumps(build_payload(DF, Scope()))


class TestValidation(unittest.TestCase):
    def test_status_changes(self):
        md = "# T\n\n**Status: AI DRAFT - not yet validated by a human**\n\n## Human validation\n\nPending.\n"
        out, info = apply_validation(md, "Alice", {q: True for q in CHECKLIST})
        self.assertIn("VALIDATED by Alice", out)
        out2, info2 = apply_validation(md, "Alice", {q: False for q in CHECKLIST})
        self.assertEqual(info2["decision"], "NEEDS REVISION")


if __name__ == "__main__":
    unittest.main()
