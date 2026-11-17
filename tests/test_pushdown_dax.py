"""Unit tests for DAX Query Push-down generation and data normalization."""
import unittest
import pandas as pd

from src.load_data import Scope
from src.powerbi import (
    build_analysis_dax,
    normalize_dax_result,
    _short_column_name,
)


class TestPushdownDAX(unittest.TestCase):
    def test_base_query_without_scope(self):
        dax = build_analysis_dax()
        self.assertIn("SUMMARIZECOLUMNS", dax)
        self.assertIn("'Date'[Month]", dax)
        self.assertNotIn("FILTER(", dax)

    def test_channel_pushdown(self):
        s = Scope(channel="Reseller")
        dax = build_analysis_dax(s)
        self.assertIn("FILTER('Sales Order', 'Sales Order'[Channel] = \"Reseller\")", dax)

    def test_group_pushdown(self):
        s = Scope(group="Europe")
        dax = build_analysis_dax(s)
        self.assertIn("FILTER('Sales Territory', 'Sales Territory'[Group] = \"Europe\")", dax)

    def test_category_pushdown(self):
        s = Scope(category="Bikes")
        dax = build_analysis_dax(s)
        self.assertIn("FILTER(Product, Product[Category] = \"Bikes\")", dax)

    def test_date_range_pushdown(self):
        s = Scope(start="2018-05", end="2019-10")
        dax = build_analysis_dax(s)
        self.assertIn("'Date'[Month] >= DATE(2018, 5, 1)", dax)
        self.assertIn("'Date'[Month] <= DATE(2019, 10, 1)", dax)

    def test_all_filters_ignored(self):
        s = Scope(channel="All", group="All", category="All")
        dax = build_analysis_dax(s)
        self.assertNotIn("FILTER(", dax)

    def test_combined_pushdown(self):
        s = Scope(channel="Internet", group="North America", category="Clothing", start="2019-01", end="2019-06")
        dax = build_analysis_dax(s)
        self.assertIn("Internet", dax)
        self.assertIn("North America", dax)
        self.assertIn("Clothing", dax)
        self.assertIn("DATE(2019, 1, 1)", dax)
        self.assertIn("DATE(2019, 6, 1)", dax)

    def test_short_column_name(self):
        self.assertEqual(_short_column_name("'Product'[Category]"), "Category")
        self.assertEqual(_short_column_name("Product[Category]"), "Category")
        self.assertEqual(_short_column_name("Sales"), "Sales")

    def test_normalize_dax_result(self):
        raw = pd.DataFrame([
            {
                "'Date'[Month]": pd.Timestamp("2019-01-01"),
                "Product[Category]": "Bikes",
                "'Sales Territory'[Group]": "Europe",
                "'Sales Order'[Channel]": "Reseller",
                "Sales": "1000",
                "Cost": "800",
                "Profit": "200",
                "Orders": "10",
            }
        ])
        norm = normalize_dax_result(raw)
        self.assertIn("date", norm.columns)
        self.assertIn("Year", norm.columns)
        self.assertIn("Category", norm.columns)
        self.assertEqual(norm["Sales"].iloc[0], 1000.0)
        self.assertEqual(norm["Profit"].iloc[0], 200.0)
        self.assertEqual(norm["Year"].iloc[0], 2019)


if __name__ == "__main__":
    unittest.main()
