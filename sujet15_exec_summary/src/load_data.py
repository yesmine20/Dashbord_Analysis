"""Load and clean the Power BI export, apply scope filters."""
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

from . import config

REQUIRED = ["Year", "Month", "Category", "Group", "Channel", "Sales", "Cost", "Profit", "Orders"]


def _to_number(s: pd.Series) -> pd.Series:
    """Parse '$1,234', '($36)', '-$36', '40%' into floats."""
    s = s.astype(str).str.strip()
    neg = s.str.contains(r"^\(|^-|^\u2212|\$-|\$\u2212", regex=True)
    clean = s.str.replace(r"[^\d.]", "", regex=True)
    val = pd.to_numeric(clean, errors="coerce")
    return val.where(~neg, -val)


def load_clean(path=config.DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    for c in ("Sales", "Cost", "Profit", "Orders"):
        df[c] = _to_number(df[c])
    date = pd.to_datetime(df["Month"], errors="coerce")
    if date.isna().any():  # fallback for labels like 'Nov, 2017'
        date = date.fillna(pd.to_datetime(df["Month"], format="%b, %Y", errors="coerce"))
    df["date"] = date.dt.to_period("M").dt.to_timestamp()
    for c in ("Category", "Group", "Channel"):
        df[c] = df[c].astype(str).str.strip()
    df = df.dropna(subset=["date", "Sales", "Cost", "Profit"]).copy()
    df["Year"] = df["Year"].astype(int)
    return df[["date", "Year", "Category", "Group", "Channel", "Sales", "Cost", "Profit", "Orders"]]


def reconcile(df: pd.DataFrame) -> dict:
    """Compare CSV totals with the totals displayed in the Power BI report."""
    out = {}
    for k, expected in config.EXPECTED_TOTALS.items():
        got = float(df[k].sum())
        out[k] = {"csv": got, "report": expected, "ok": abs(got - expected) <= max(1.0, 0.0001 * expected)}
    return out


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
