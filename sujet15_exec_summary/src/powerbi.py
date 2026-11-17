"""Connection to Power BI Semantic Model: Local ADOMD.NET, Cloud REST API, and Query Push-down."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from .semantic_model import validate_query_contract

load_dotenv()
_NETFX_READY = False


class PowerBIConnectionError(RuntimeError):
    """Raised when the Power BI semantic model cannot be queried."""


# ================================================================
# DAX QUERY PUSH-DOWN BUILDER
# ================================================================

BASE_DAX_TEMPLATE = """
EVALUATE
SUMMARIZECOLUMNS(
    'Date'[Month],
    Product[Category],
    'Sales Territory'[Group],
    'Sales Order'[Channel],{filter_block}
    "Sales", [Sales],
    "Cost", [Cost],
    "Profit", [Profit],
    "Orders", [Orders]
)
ORDER BY 'Date'[Month], Product[Category], 'Sales Territory'[Group], 'Sales Order'[Channel]
""".strip()


def build_analysis_dax(scope: Any = None) -> str:
    """Generate an optimized DAX query pushing down scope filters to the VertiPaq engine.
    
    If scope is None, returns the complete base query without filters.
    """
    if not scope:
        return BASE_DAX_TEMPLATE.format(filter_block="")

    filters: list[str] = []

    # Channel filter push-down
    channel = getattr(scope, "channel", None)
    if channel and str(channel).lower() != "all":
        clean_channel = str(channel).replace('"', '""')
        filters.append(f'FILTER(\'Sales Order\', \'Sales Order\'[Channel] = "{clean_channel}")')

    # Region / Group filter push-down
    group = getattr(scope, "group", None)
    if group and str(group).lower() != "all":
        clean_group = str(group).replace('"', '""')
        filters.append(f'FILTER(\'Sales Territory\', \'Sales Territory\'[Group] = "{clean_group}")')

    # Category filter push-down
    category = getattr(scope, "category", None)
    if category and str(category).lower() != "all":
        clean_category = str(category).replace('"', '""')
        filters.append(f'FILTER(Product, Product[Category] = "{clean_category}")')

    # Date range filter push-down
    start = getattr(scope, "start", None)
    end = getattr(scope, "end", None)
    date_conditions: list[str] = []

    if start:
        match_start = re.match(r"^(\d{4})-(\d{2})$", str(start).strip())
        if match_start:
            y, m = int(match_start.group(1)), int(match_start.group(2))
            date_conditions.append(f"'Date'[Month] >= DATE({y}, {m}, 1)")

    if end:
        match_end = re.match(r"^(\d{4})-(\d{2})$", str(end).strip())
        if match_end:
            y, m = int(match_end.group(1)), int(match_end.group(2))
            date_conditions.append(f"'Date'[Month] <= DATE({y}, {m}, 1)")

    if date_conditions:
        date_expr = " && ".join(date_conditions)
        filters.append(f"FILTER('Date', {date_expr})")

    if not filters:
        return BASE_DAX_TEMPLATE.format(filter_block="")

    indent = "    "
    filter_block = "\n" + "\n".join(f"{indent}{clause}," for clause in filters)
    return BASE_DAX_TEMPLATE.format(filter_block=filter_block)


ANALYSIS_DAX = build_analysis_dax()


# ================================================================
# ADAPTER 1: LOCAL ADOMD.NET (Power BI Desktop)
# ================================================================

def _adomd_connection():
    """Create an ADOMD.NET connection using local Desktop settings from .env."""
    data_source = os.getenv("POWERBI_ADOMD_DATA_SOURCE", "").strip()
    catalog = os.getenv("POWERBI_ADOMD_CATALOG", "").strip()
    if not data_source or not catalog:
        raise PowerBIConnectionError(
            "Configure POWERBI_ADOMD_DATA_SOURCE and POWERBI_ADOMD_CATALOG in .env. "
            "Use the current server and database IDs shown by the Power BI Desktop local model."
        )

    global _NETFX_READY
    try:
        from pythonnet import load
        if not _NETFX_READY:
            load("netfx")
            _NETFX_READY = True
        import clr
    except Exception as exc:
        raise PowerBIConnectionError(
            "pythonnet/.NET Framework is unavailable. Install pythonnet in the app environment."
        ) from exc

    dll_path = os.getenv("POWERBI_ADOMD_DLL", "").strip()
    if dll_path:
        if not Path(dll_path).is_file():
            raise PowerBIConnectionError(f"ADOMD.NET DLL not found: {dll_path}")
        clr.AddReference(dll_path)
    else:
        try:
            clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
        except Exception as exc:
            raise PowerBIConnectionError(
                "ADOMD.NET client not found. Set POWERBI_ADOMD_DLL to its installed DLL path."
            ) from exc

    # Dynamic ADOMD.NET resolution compatible with Python linters and runtime
    try:
        from Microsoft.AnalysisServices.AdomdClient import AdomdConnection  # type: ignore
    except (ImportError, AttributeError):
        import clr
        try:
            AdomdConnection = clr.Microsoft.AnalysisServices.AdomdClient.AdomdConnection
        except Exception as exc:
            raise PowerBIConnectionError(
                f"Cannot load AdomdConnection class from .NET assembly: {exc}"
            ) from exc

    connection_string = (
        f"Data Source={data_source};Initial Catalog={catalog};"
        "Connect Timeout=15;"
    )
    return AdomdConnection(connection_string)


def _query_dax_adomd(query: str) -> pd.DataFrame:
    """Execute a DAX query against local Power BI Desktop via ADOMD.NET."""
    connection = None
    reader = None
    try:
        connection = _adomd_connection()
        connection.Open()
        command = connection.CreateCommand()
        command.CommandText = query
        reader = command.ExecuteReader()
        columns = [str(reader.GetName(i)) for i in range(reader.FieldCount)]
        rows: list[dict[str, Any]] = []
        while reader.Read():
            row = {}
            for i, name in enumerate(columns):
                value = reader.GetValue(i)
                if value is None or str(value) == "System.DBNull":
                    value = None
                row[name] = value
            rows.append(row)
        return pd.DataFrame(rows, columns=columns)
    except PowerBIConnectionError:
        raise
    except Exception as exc:
        raise PowerBIConnectionError(
            f"Power BI DAX query failed ({type(exc).__name__}): {exc}"
        ) from exc
    finally:
        if reader is not None:
            reader.Close()
        if connection is not None:
            connection.Close()


# ================================================================
# ADAPTER 2: CLOUD POWER BI REST API (Power BI Service / Fabric)
# ================================================================

def _query_dax_rest(query: str) -> pd.DataFrame:
    """Execute a DAX query against Power BI Service / Fabric via executeQueries REST API."""
    import urllib.request
    import json

    tenant_id = os.getenv("POWERBI_TENANT_ID", "").strip()
    client_id = os.getenv("POWERBI_CLIENT_ID", "").strip()
    client_secret = os.getenv("POWERBI_CLIENT_SECRET", "").strip()
    dataset_id = os.getenv("POWERBI_DATASET_ID", "").strip()

    if not (tenant_id and client_id and client_secret and dataset_id):
        raise PowerBIConnectionError(
            "Cloud Power BI mode requires POWERBI_TENANT_ID, POWERBI_CLIENT_ID, "
            "POWERBI_CLIENT_SECRET, and POWERBI_DATASET_ID in .env."
        )

    # 1. Acquire Azure Entra ID token
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = (
        f"grant_type=client_credentials&client_id={client_id}"
        f"&client_secret={client_secret}&scope=https://analysis.windows.net/powerbi/api/.default"
    ).encode("utf-8")

    req = urllib.request.Request(token_url, data=token_data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_json = json.loads(resp.read().decode("utf-8"))
            access_token = token_json["access_token"]
    except Exception as exc:
        raise PowerBIConnectionError(f"OAuth token acquisition failed: {exc}") from exc

    # 2. Call executeQueries endpoint
    query_url = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"
    body = json.dumps({"queries": [{"query": query}]}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    q_req = urllib.request.Request(query_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(q_req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rows = data["results"][0]["tables"][0]["rows"]
            return pd.DataFrame(rows)
    except Exception as exc:
        raise PowerBIConnectionError(f"Power BI REST query failed: {exc}") from exc


# ================================================================
# QUERY DISPATCHER & NORMALIZATION
# ================================================================

def query_dax(query: str) -> pd.DataFrame:
    """Execute DAX query according to configured mode (local ADOMD.NET or Cloud REST API)."""
    mode = os.getenv("POWERBI_EXECUTION_MODE", "local").lower().strip()
    if mode == "cloud" or os.getenv("POWERBI_DATASET_ID"):
        return _query_dax_rest(query)
    return _query_dax_adomd(query)


def _short_column_name(name: str) -> str:
    """Normalize ADOMD result names such as 'Product'[Category] to Category."""
    name = str(name).strip()
    if name.endswith("]") and "[" in name:
        return name.rsplit("[", 1)[1][:-1].strip(" '")
    return name.strip(" '")


def _to_month_timestamp(value: Any) -> pd.Timestamp:
    """Convert ADOMD.NET System.DateTime or string dates to Pandas Timestamp."""
    if value is None:
        return pd.NaT

    if hasattr(value, "Year") and hasattr(value, "Month"):
        return pd.Timestamp(
            year=int(value.Year),
            month=int(value.Month),
            day=1,
        )

    converted = pd.to_datetime(value, errors="coerce")
    if pd.isna(converted):
        return pd.NaT
    return converted.to_period("M").to_timestamp()


def normalize_dax_result(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean DAX results into standard columnar format."""
    if frame.empty:
        raise PowerBIConnectionError("The Power BI DAX query returned no rows.")

    frame = frame.copy()
    frame.columns = [_short_column_name(c) for c in frame.columns]

    required = {
        "Month", "Category", "Group", "Channel",
        "Sales", "Cost", "Profit", "Orders",
    }
    missing = required - set(frame.columns)
    if missing:
        raise PowerBIConnectionError(
            "The DAX result is missing expected columns: "
            + ", ".join(sorted(missing))
        )

    frame["date"] = frame["Month"].apply(_to_month_timestamp)

    for col in ("Sales", "Cost", "Profit", "Orders"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    for col in ("Category", "Group", "Channel"):
        frame[col] = frame[col].fillna("(Blank)").astype(str).str.strip()

    frame = frame.dropna(subset=["date", "Sales", "Cost", "Profit"]).copy()
    frame["Year"] = frame["date"].dt.year

    return frame[
        [
            "date", "Year", "Category", "Group", "Channel",
            "Sales", "Cost", "Profit", "Orders",
        ]
    ]


def _to_number(s: pd.Series) -> pd.Series:
    """Parse '$1,234', '($36)', '-$36', '40%' into numeric floats."""
    s = s.astype(str).str.strip()
    neg = s.str.contains(r"^\(|^-|^\u2212|\$-|\$\u2212", regex=True)
    clean = s.str.replace(r"[^\d.]", "", regex=True)
    val = pd.to_numeric(clean, errors="coerce")
    return val.where(~neg, -val)


def _load_snapshot_data() -> pd.DataFrame:
    """Load certified snapshot from data/export_kpi_mensuel.csv if live engine is not connected."""
    from . import config
    snapshot_path = config.ROOT / "data" / "export_kpi_mensuel.csv"
    if not snapshot_path.is_file():
        raise PowerBIConnectionError(
            "Neither live Power BI connection nor certified snapshot found."
        )
    df = pd.read_csv(snapshot_path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    for col in ("Sales", "Cost", "Profit", "Orders"):
        df[col] = _to_number(df[col])
    date = pd.to_datetime(df["Month"], errors="coerce")
    df["date"] = date.dt.to_period("M").dt.to_timestamp()
    for col in ("Category", "Group", "Channel"):
        df[col] = df[col].astype(str).str.strip()
    df = df.dropna(subset=["date", "Sales", "Cost", "Profit"]).copy()
    df["Year"] = df["date"].dt.year
    return df[["date", "Year", "Category", "Group", "Channel", "Sales", "Cost", "Profit", "Orders"]].copy()


def get_analysis_data(scope: Any = None) -> pd.DataFrame:
    """Return monthly facts from the Power BI model with Query Push-down if scope is provided.
    
    Falls back gracefully to the certified TMDL snapshot when Power BI Desktop is not launched.
    """
    try:
        validate_query_contract()
    except Exception as exc:
        raise PowerBIConnectionError(
            f"PBIP/TMDL validation failed: {exc}"
        ) from exc

    dax_query = build_analysis_dax(scope)
    try:
        raw_frame = query_dax(dax_query)
        df = normalize_dax_result(raw_frame)
        df.attrs["source_type"] = "live_powerbi"
        return df
    except Exception as exc:
        mode = os.getenv("POWERBI_EXECUTION_MODE", "local").lower().strip()
        if mode == "local":
            print(f"[INFO] Power BI Desktop non actif ({exc}). Bascule sur le snapshot certifié du modèle.", flush=True)
            df = _load_snapshot_data()
            df.attrs["source_type"] = "certified_snapshot"
            return df
        raise