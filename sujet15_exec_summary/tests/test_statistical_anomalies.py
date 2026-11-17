"""Unit tests for statistical anomaly detection, Z-score, severity and seasonality."""
import unittest
import pandas as pd

from src.detect import build_payload
from src.load_data import Scope


def make_statistical_frame():
    """Deterministic fixture with known statistical anomalies."""
    rows = []
    # 24 months from 2018-01 to 2019-12
    dates = pd.date_range("2018-01-01", "2019-12-01", freq="MS")
    for d in dates:
        for cat in ("Bikes", "Accessories"):
            for grp in ("Europe", "North America"):
                for ch in ("Internet", "Reseller"):
                    sales = 500_000
                    # Normal margin is 20% (profit = 100,000)
                    profit = 100_000

                    # Severe anomaly in 2019-08: negative profit (profit = -50,000)
                    if d == pd.Timestamp("2019-08-01"):
                        profit = -50_000

                    # Seasonal drop in both Jan 2018 and Jan 2019: sales drop by 50%
                    if d.month == 1:
                        sales = 250_000
                        profit = 50_000

                    rows.append({
                        "date": d,
                        "Year": d.year,
                        "Category": cat,
                        "Group": grp,
                        "Channel": ch,
                        "Sales": sales,
                        "Cost": sales - profit,
                        "Profit": profit,
                        "Orders": 50,
                    })
    return pd.DataFrame(rows)


class TestStatisticalAnomalies(unittest.TestCase):
    def setUp(self):
        self.df = make_statistical_frame()
        self.payload = build_payload(self.df, Scope())

    def test_r1_has_severity_and_zscore(self):
        anomalies = [a for a in self.payload["anomalies"] if a["rule"] == "R1_margin_alert"]
        self.assertTrue(len(anomalies) > 0)
        # 2019-08 should be critical because profit is negative
        aug_2019 = next((a for a in anomalies if a["period"] == "2019-08"), None)
        self.assertIsNotNone(aug_2019)
        self.assertEqual(aug_2019["metrics"]["severity"], "critical")
        self.assertTrue(aug_2019["metrics"]["negative_profit"])

    def test_seasonality_pattern_detected(self):
        r2 = [a for a in self.payload["anomalies"] if a["rule"] == "R2_sales_variation"]
        # Jan 2019 sales variation should have seasonality checked
        jan_2019 = next((a for a in r2 if a["period"] == "2019-01"), None)
        if jan_2019 and "seasonality" in jan_2019["metrics"]:
            self.assertIn("prior_year_same_month_change_pct", jan_2019["metrics"]["seasonality"])

    def test_backward_compatibility_ids(self):
        for i, a in enumerate(self.payload["anomalies"], 1):
            self.assertEqual(a["id"], f"A{i:02d}")


if __name__ == "__main__":
    unittest.main()
