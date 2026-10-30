"""Central configuration: paths, expected totals and detection thresholds."""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "export_kpi_mensuel.csv"
OUTPUT_DIR = ROOT / "outputs"

REPORT_NAME = "AdventureWorks Sales (Power BI export, monthly)"
CURRENCY = "USD"
# Selector that was active when the CSV was exported from Power BI Desktop.
DATE_BASIS = "Order Date (selector 'By Order Date' at export time; verify if re-exporting)"

# Totals shown by the Power BI report (row "Total" of the export table).
# Used to check that the CSV matches the dashboard (tolerance: 0.01 %).
EXPECTED_TOTALS = {"Sales": 109_809_274, "Cost": 97_257_908, "Profit": 12_551_366}


@dataclass(frozen=True)
class Thresholds:
    # R1 - margin alert
    margin_min_sales: float = 100_000     # ignore months with tiny sales (noise)
    margin_lookback: int = 3              # months used for the baseline margin
    margin_drop_pts: float = 5.0          # flag if margin < baseline - X points
    # R2 / R3 - sales variations (relative AND absolute must be exceeded)
    sales_var_pct: float = 15.0
    sales_var_abs: float = 1_000_000
    like_for_like_months: int = 6         # R3 window (latest N months vs same months a year before)
    # R4 - channel gap
    channel_gap_pts: float = 20.0
    # R5 - segment outliers
    segment_dev_pts: float = 10.0
    segment_min_sales: float = 1_000_000
    # reporting
    max_anomalies_per_rule: int = 5
    top_contributors: int = 2


DEFAULT = Thresholds()
