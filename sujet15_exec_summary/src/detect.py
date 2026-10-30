"""Deterministic anomaly detection (no LLM here).

Rules
  R1 margin_alert        monthly margin negative, or far below its trailing baseline
  R2 sales_variation     month-over-month sales change above relative AND absolute thresholds
  R3 like_for_like_yoy   latest N months vs the same N months one year earlier
  R4 channel_gap         margin gap between channels (Internet vs Reseller)
  R5 segment_outlier     category / region whose margin is far from the scope margin

The output is a JSON-serialisable dict: the ONLY input of the LLM.
"""
import pandas as pd

from .config import CURRENCY, DATE_BASIS, REPORT_NAME, DEFAULT, Thresholds
from .fmt import pct, pts, usd
from .load_data import Scope, apply_scope, monthly

DIMS = ("Channel", "Category", "Group")


# ------------------------------------------------------------------ helpers
def _months_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def _period(d: pd.Timestamp) -> str:
    return d.strftime("%Y-%m")


def _delta_contributors(df, dates_now, dates_prev, metric, top):
    """Which segments explain the change of `metric` between two sets of months."""
    now, prev = df[df["date"].isin(dates_now)], df[df["date"].isin(dates_prev)]
    out = {}
    for dim in DIMS:
        a = now.groupby(dim)[metric].sum()
        b = prev.groupby(dim)[metric].sum()
        d = a.sub(b, fill_value=0)
        if len(d) < 2:          # dimension already fixed by the scope
            continue
        d = d.reindex(d.abs().sort_values(ascending=False).index)[:top]
        out[dim] = [{"segment": k, "change": usd(v)} for k, v in d.items()]
    return out


def _month_segments(df, date, top):
    """Weakest segments (lowest profit) inside one month."""
    cur = df[df["date"] == date]
    out = {}
    for dim in DIMS:
        g = cur.groupby(dim)[["Sales", "Profit"]].sum()
        if len(g) < 2:
            continue
        g["margin"] = g["Profit"] / g["Sales"].where(g["Sales"] > 0) * 100
        g = g.sort_values("Profit").head(top)
        out[dim] = [{"segment": k, "sales": usd(r.Sales), "profit": usd(r.Profit),
                     "margin_pct": pct(r.margin) if pd.notna(r.margin) else None}
                    for k, r in g.iterrows()]
    return out


# ------------------------------------------------------------------ rules
def rule_margin(df, th: Thresholds):
    m = monthly(df)
    idx, found = list(m.index), []
    for i, d in enumerate(idx):
        r = m.loc[d]
        if r.Sales < th.margin_min_sales:
            continue
        base = None
        if i >= th.margin_lookback:
            prev = m.iloc[i - th.margin_lookback:i]
            pidx = list(prev.index) + [d]
            contiguous = all(_months_between(pidx[j], pidx[j + 1]) == 1 for j in range(len(pidx) - 1))
            if contiguous and prev.Sales.sum() > 0:
                base = prev.Profit.sum() / prev.Sales.sum() * 100
        negative = r.Profit < 0
        drop = (base - r.margin) if base is not None else None
        if negative or (drop is not None and drop >= th.margin_drop_pts):
            impact = (r.margin - base) / 100 * r.Sales if base is not None else r.Profit
            found.append((abs(impact), d, r, base, drop, impact, negative))
    found.sort(key=lambda x: -x[0])
    out = []
    for _, d, r, base, drop, impact, negative in found[:th.max_anomalies_per_rule]:
        metrics = {"sales": usd(r.Sales), "profit": usd(r.Profit), "margin_pct": pct(r.margin),
                   "negative_profit": bool(negative)}
        if base is not None:
            metrics.update({"baseline_margin_pct": pct(base), "margin_drop_pts": pts(drop),
                            "profit_vs_baseline": usd(impact)})
        out.append({"rule": "R1_margin_alert", "direction": "negative", "period": _period(d),
                    "what": ("Monthly profit was negative." if negative else
                             "Monthly profit margin fell well below its trailing baseline."),
                    "metrics": metrics,
                    "contributors": {"weakest_segments_in_month": _month_segments(df, d, th.top_contributors)}})
    return out, len(found)


def rule_sales_variation(df, th: Thresholds):
    m = monthly(df)
    found = []
    idx = list(m.index)
    for i in range(1, len(idx)):
        if _months_between(idx[i - 1], idx[i]) != 1:
            continue
        prev_s, cur_s = m.Sales.iloc[i - 1], m.Sales.iloc[i]
        if prev_s <= 0:
            continue
        change = cur_s - prev_s
        change_pct = change / prev_s * 100
        if abs(change_pct) >= th.sales_var_pct and abs(change) >= th.sales_var_abs:
            found.append((abs(change), idx[i], idx[i - 1], cur_s, prev_s, change, change_pct))
    found.sort(key=lambda x: -x[0])
    out = []
    for _, d, pd_, cur_s, prev_s, change, change_pct in found[:th.max_anomalies_per_rule]:
        row = m.loc[d]
        out.append({"rule": "R2_sales_variation", "direction": "positive" if change > 0 else "negative",
                    "period": _period(d),
                    "what": f"Month-over-month sales change versus {_period(pd_)}.",
                    "metrics": {"sales": usd(cur_s), "previous_sales": usd(prev_s),
                                "sales_change": usd(change), "sales_change_pct": pct(change_pct),
                                "profit": usd(row.Profit), "margin_pct": pct(row.margin)},
                    "contributors": {"largest_changes_by_segment":
                                     _delta_contributors(df, [d], [pd_], "Sales", th.top_contributors)}})
    return out, len(found)


def rule_like_for_like(df, th: Thresholds):
    m = monthly(df)
    idx, n = list(m.index), th.like_for_like_months
    if len(idx) < n:
        return [], 0
    last = idx[-n:]
    if any(_months_between(last[j], last[j + 1]) != 1 for j in range(n - 1)):
        return [], 0
    prev = [d - pd.DateOffset(years=1) for d in last]
    if any(p not in m.index for p in prev):
        return [], 0
    s_now, s_prev = m.loc[last, "Sales"].sum(), m.loc[prev, "Sales"].sum()
    p_now, p_prev = m.loc[last, "Profit"].sum(), m.loc[prev, "Profit"].sum()
    if s_prev <= 0:
        return [], 0
    ds = s_now - s_prev
    ds_pct = ds / s_prev * 100
    if abs(ds_pct) < th.sales_var_pct or abs(ds) < th.sales_var_abs:
        return [], 0
    metrics = {"sales_now": usd(s_now), "sales_before": usd(s_prev), "sales_change": usd(ds),
               "sales_change_pct": pct(ds_pct), "profit_now": usd(p_now), "profit_before": usd(p_prev),
               "profit_change": usd(p_now - p_prev),
               "margin_now_pct": pct(p_now / s_now * 100) if s_now > 0 else None,
               "margin_before_pct": pct(p_prev / s_prev * 100)}
    if p_prev > 0:
        metrics["profit_change_pct"] = pct((p_now - p_prev) / p_prev * 100)
    return [{"rule": "R3_like_for_like_yoy", "direction": "positive" if ds > 0 else "negative",
             "period": f"{_period(last[0])} to {_period(last[-1])}",
             "what": f"Latest {n} months versus the same {n} months one year earlier "
                     f"({_period(prev[0])} to {_period(prev[-1])}).",
             "metrics": metrics,
             "contributors": {"largest_changes_by_segment":
                              _delta_contributors(df, last, prev, "Sales", th.top_contributors)}}], 1


def rule_channel_gap(df, th: Thresholds):
    if df["Channel"].nunique() < 2:
        return [], 0
    g = df.groupby("Channel")[["Sales", "Profit"]].sum()
    g["margin"] = g["Profit"] / g["Sales"] * 100
    hi, lo = g["margin"].idxmax(), g["margin"].idxmin()
    gap = g.loc[hi, "margin"] - g.loc[lo, "margin"]
    if gap < th.channel_gap_pts:
        return [], 0
    total = g["Sales"].sum()

    def seg(c):
        r = g.loc[c]
        return {"channel": c, "sales": usd(r.Sales), "profit": usd(r.Profit),
                "margin_pct": pct(r.margin), "share_of_sales_pct": pct(r.Sales / total * 100)}
    return [{"rule": "R4_channel_gap", "direction": "structural", "period": "whole scope",
             "what": "Large profit-margin gap between sales channels.",
             "metrics": {"higher_margin_channel": seg(hi), "lower_margin_channel": seg(lo),
                         "margin_gap_pts": pts(gap)},
             "contributors": {}}], 1


def rule_segment_outliers(df, th: Thresholds):
    total_s = df.Sales.sum()
    overall = df.Profit.sum() / total_s * 100
    found = []
    for dim in ("Category", "Group"):
        g = df.groupby(dim)[["Sales", "Profit"]].sum()
        if len(g) < 2:
            continue
        g["margin"] = g["Profit"] / g["Sales"] * 100
        for seg, r in g.iterrows():
            gap = r.margin - overall
            if r.Sales >= th.segment_min_sales and abs(gap) >= th.segment_dev_pts:
                found.append((abs(gap) / 100 * r.Sales, dim, seg, r, gap))
    found.sort(key=lambda x: -x[0])
    out = []
    for _, dim, seg, r, gap in found[:th.max_anomalies_per_rule]:
        out.append({"rule": "R5_segment_outlier", "direction": "positive" if gap > 0 else "negative",
                    "period": "whole scope",
                    "what": f"{dim} margin far from the scope margin.",
                    "metrics": {"dimension": dim, "segment": seg, "sales": usd(r.Sales),
                                "share_of_sales_pct": pct(r.Sales / total_s * 100),
                                "margin_pct": pct(r.margin), "scope_margin_pct": pct(overall),
                                "gap_pts": pts(gap)},
                    "contributors": {}})
    return out, len(found)


# ------------------------------------------------------------------ payload
def _scope_text(scope: Scope, start, end) -> str:
    parts = [scope.channel or "all channels", scope.group or "all regions", scope.category or "all categories"]
    return f"{', '.join(parts)}, {start} to {end}"


def _breakdowns(df):
    total = df.Sales.sum()
    out = {}
    for dim in DIMS:
        g = df.groupby(dim)[["Sales", "Profit"]].sum()
        if len(g) < 2:
            continue
        g["margin"] = g["Profit"] / g["Sales"].where(g["Sales"] > 0) * 100
        out[dim] = [{"segment": k, "sales": usd(r.Sales), "profit": usd(r.Profit),
                     "margin_pct": pct(r.margin), "share_of_sales_pct": pct(r.Sales / total * 100)}
                    for k, r in g.sort_values("Sales", ascending=False).iterrows()]
    return out


def _yearly(df):
    out = []
    for y, g in df.groupby(df["date"].dt.year):
        s, p = g.Sales.sum(), g.Profit.sum()
        months = g["date"].nunique()
        out.append({"year": int(y), "months_covered": int(months), "complete_year": bool(months == 12),
                    "sales": usd(s), "profit": usd(p), "margin_pct": pct(p / s * 100) if s > 0 else None})
    return out


def build_payload(df_all: pd.DataFrame, scope: Scope, th: Thresholds = DEFAULT) -> dict:
    sub, problems = apply_scope(df_all, scope)
    base_meta = {"report": REPORT_NAME, "currency": CURRENCY, "date_basis": DATE_BASIS,
                 "scope": scope.as_dict()}
    if problems:
        return {"status": "no_data", "meta": base_meta, "reason": " ".join(problems)}

    start, end = _period(sub["date"].min()), _period(sub["date"].max())
    s, c, p = sub.Sales.sum(), sub.Cost.sum(), sub.Profit.sum()

    rules = [("R1_margin_alert", rule_margin), ("R2_sales_variation", rule_sales_variation),
             ("R3_like_for_like_yoy", rule_like_for_like), ("R4_channel_gap", rule_channel_gap),
             ("R5_segment_outlier", rule_segment_outliers)]
    anomalies, counts = [], {}
    for name, fn in rules:
        found, n_flagged = fn(sub, th)
        counts[name] = {"flagged": n_flagged, "reported": len(found)}
        anomalies.extend(found)
    anomalies = [{"id": f"A{i:02d}", **a} for i, a in enumerate(anomalies, 1)]

    yearly = _yearly(sub)
    partial = [f"{y['year']} ({y['months_covered']} months)" for y in yearly if not y["complete_year"]]
    limitations = [
        "The data show where and when changes happened, not why. Contributing segments are not confirmed causes.",
        "Order counts are not additive across rows and are excluded from this analysis.",
        "The dataset contains no sales targets, so no target-gap analysis is possible.",
    ]
    if partial:
        limitations.append("Calendar years with less than 12 months of data: " + ", ".join(partial)
                           + ". Year-over-year comparisons use like-for-like windows only.")
    r2 = counts["R2_sales_variation"]
    if r2["flagged"] > r2["reported"]:
        limitations.append(f"Month-to-month sales are volatile in this scope: {r2['flagged']} months exceed the "
                           f"thresholds, only the {r2['reported']} largest are listed.")

    return {
        "status": "ok",
        "meta": {**base_meta, "scope_text": _scope_text(scope, start, end),
                 "period_start": start, "period_end": end, "months_covered": int(sub["date"].nunique()),
                 "thresholds": {"sales_variation_pct": th.sales_var_pct,
                                "sales_variation_abs_usd": th.sales_var_abs,
                                "margin_drop_pts": th.margin_drop_pts,
                                "channel_gap_pts": th.channel_gap_pts,
                                "segment_deviation_pts": th.segment_dev_pts},
                 "rule_counts": counts},
        "kpis": {"sales": usd(s), "cost": usd(c), "profit": usd(p),
                 "profit_margin_pct": pct(p / s * 100) if s > 0 else None},
        "breakdown": _breakdowns(sub),
        "yearly": yearly,
        "anomalies": anomalies,
        "limitations": limitations,
    }
