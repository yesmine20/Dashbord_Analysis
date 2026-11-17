"""Load semantic-model query results and apply analysis scope filters."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import pandas as pd
from .powerbi import get_analysis_data


def load_from_powerbi(scope: Scope | None = None) -> pd.DataFrame:
    """Query the Power BI semantic model (with optional DAX Query Push-down)."""
    return get_analysis_data(scope=scope)


@dataclass
class Scope:
    channel: str | None = None
    group: str | None = None
    category: str | None = None
    start: str | None = None   # 'YYYY-MM'
    end: str | None = None     # 'YYYY-MM'

    def as_dict(self) -> dict:
        return asdict(self)


def apply_scope(df: pd.DataFrame, scope: Scope):
    """Return (filtered_df, problems). Unknown filter values are reported, never silently ignored."""
    problems = []
    out = df
    for col, val in (("Channel", scope.channel), ("Group", scope.group), ("Category", scope.category)):
        if val:
            valid = {v.lower(): v for v in df[col].unique()}
            if val.lower() not in valid:
                problems.append(f"Unknown {col} '{val}'. Available: {sorted(df[col].unique())}")
            else:
                out = out[out[col] == valid[val.lower()]]
    if scope.start:
        out = out[out["date"] >= pd.Timestamp(scope.start + "-01")]
    if scope.end:
        out = out[out["date"] <= pd.Timestamp(scope.end + "-01")]
    if not problems and out.empty:
        problems.append("No rows for the requested period/filters "
                        f"(data cover {df['date'].min():%Y-%m} to {df['date'].max():%Y-%m}).")
    return out, problems


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    m = df.groupby("date")[["Sales", "Cost", "Profit"]].sum().sort_index()
    m["margin"] = (m["Profit"] / m["Sales"].where(m["Sales"] > 0)) * 100
    return m
