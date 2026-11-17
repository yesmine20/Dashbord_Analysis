"""Unit tests for PBIP/TMDL semantic model parsing and metadata extraction."""
import unittest
from pathlib import Path

from src.semantic_model import (
    get_model_catalog,
    get_semantic_context_for_prompt,
    validate_query_contract,
)


class TestSemanticModel(unittest.TestCase):
    def setUp(self):
        self.catalog = get_model_catalog(reload=True)

    def test_tables_loaded(self):
        expected_tables = {"Date", "Product", "Sales Territory", "Sales Order", "Sales"}
        self.assertTrue(expected_tables.issubset(set(self.catalog.tables.keys())))

    def test_core_measures_extracted(self):
        sales_table = self.catalog.tables["Sales"]
        for m_name in ("Sales", "Cost", "Profit", "Orders"):
            self.assertIn(m_name, sales_table.measures)
            m = sales_table.measures[m_name]
            self.assertTrue(len(m.expression) > 0)
            self.assertTrue(len(m.description) > 0)

    def test_profit_formula_exact(self):
        profit = self.catalog.get_measure("Profit")
        self.assertIsNotNone(profit)
        self.assertEqual(profit.expression, "[Sales] - [Cost]")
        self.assertIn("Sales minus Cost", profit.description)

    def test_relationships_active_date(self):
        active_rel = self.catalog.active_relationship_for("Sales", "Date")
        self.assertIsNotNone(active_rel)
        self.assertEqual(active_rel.from_column, "OrderDateKey")
        self.assertEqual(active_rel.to_column, "DateKey")
        self.assertTrue(active_rel.is_active)

    def test_inactive_relationships(self):
        inactive = [r for r in self.catalog.relationships if not r.is_active]
        inactive_cols = {(r.from_column, r.to_column) for r in inactive}
        self.assertIn(("DueDateKey", "DateKey"), inactive_cols)
        self.assertIn(("ShipDateKey", "DateKey"), inactive_cols)

    def test_contract_validation_succeeds(self):
        contract = validate_query_contract()
        self.assertIn("dimensions", contract)
        self.assertIn("measures", contract)
        self.assertIn("measures_definition", contract)
        self.assertIn("date_relationship", contract)
        self.assertIn("OrderDateKey", contract["date_relationship"])

    def test_prompt_context_generation(self):
        prompt_ctx = get_semantic_context_for_prompt()
        self.assertIn("Power BI TMDL", prompt_ctx)
        self.assertIn("Sales", prompt_ctx)
        self.assertIn("DISTINCTCOUNT", prompt_ctx)
        self.assertIn("OrderDateKey", prompt_ctx)


if __name__ == "__main__":
    unittest.main()
