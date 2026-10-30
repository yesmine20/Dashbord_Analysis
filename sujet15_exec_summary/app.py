"""Streamlit dashboard: KPI + charts on the left, AI narrative and human validation on the right.

Run:  streamlit run app.py
"""
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src import config
from src.check_numbers import check_text
from src.detect import build_payload
from src.llm_client import PROVIDERS, default_provider, generate
from src.load_data import Scope, apply_scope, load_clean, monthly, reconcile
from src.pdf_report import markdown_to_pdf
from src.report import render_markdown
from src.validate import CHECKLIST, apply_validation, log

st.set_page_config(page_title="Executive Summary & Anomalies", layout="wide")


@st.cache_data
def get_data() -> pd.DataFrame:
    return load_clean()


df = get_data()
st.title("Executive Summary & Anomalies - AdventureWorks Sales")

# ----------------------------------------------------------------- sidebar: scope
with st.sidebar:
    st.header("Scope")
    channel = st.selectbox("Channel", ["All"] + sorted(df["Channel"].unique()))
    group = st.selectbox("Region", ["All"] + sorted(df["Group"].unique()))
    category = st.selectbox("Category", ["All"] + sorted(df["Category"].unique()))
    months = [d.strftime("%Y-%m") for d in sorted(df["date"].unique())]
    start, end = st.select_slider("Period", options=months, value=(months[0], months[-1]))
    st.header("Text generation")
    options = ["mock"] + list(PROVIDERS)
    default = default_provider() if default_provider() in options else "mock"
    provider = st.selectbox("Provider", options, index=options.index(default),
                            help="'mock' = offline templates (no API key). Others need the .env file.")
    rec = reconcile(df)
    st.caption("Data check vs Power BI totals: " + ("OK" if all(v["ok"] for v in rec.values()) else "MISMATCH"))

scope = Scope(None if channel == "All" else channel, None if group == "All" else group,
              None if category == "All" else category, start, end)
payload = build_payload(df, scope)
sub, _ = apply_scope(df, scope)

left, right = st.columns([1.1, 1])

# ----------------------------------------------------------------- left: KPIs + charts
with left:
    if payload["status"] != "ok":
        st.warning("No data available for this scope. " + payload.get("reason", ""))
    else:
        k = payload["kpis"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sales", k["sales"]["display"])
        c2.metric("Cost", k["cost"]["display"])
        c3.metric("Profit", k["profit"]["display"])
        c4.metric("Margin", k["profit_margin_pct"]["display"])

        m = monthly(sub).reset_index()
        flagged = {a["period"] for a in payload["anomalies"] if a["rule"] in ("R1_margin_alert", "R2_sales_variation")}
        m["flagged"] = m["date"].dt.strftime("%Y-%m").isin(flagged)
        fig = px.bar(m, x="date", y="Sales", color="flagged", title="Monthly sales (months with an anomaly highlighted)",
                     color_discrete_map={True: "#d62728", False: "#1f77b4"})
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.line(m, x="date", y="margin", title="Monthly profit margin (%)", markers=True)
        st.plotly_chart(fig2, use_container_width=True)
        if "Channel" in payload["breakdown"]:
            b = pd.DataFrame([{"Channel": r["segment"], "Margin %": r["margin_pct"]["value"]}
                              for r in payload["breakdown"]["Channel"]])
            st.plotly_chart(px.bar(b, x="Channel", y="Margin %", title="Margin by channel"), use_container_width=True)

        st.subheader("Anomalies detected by the engine ")
        rows = [{"id": a["id"], "rule": a["rule"], "direction": a["direction"], "period": a["period"],
                 "what": a["what"]} for a in payload["anomalies"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        with st.expander("JSON sent to the LLM"):
            st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

# ----------------------------------------------------------------- right: narrative + validation
with right:
    st.subheader("AI narrative")
    key = json.dumps(scope.as_dict(), sort_keys=True) + provider
    if st.session_state.get("key") != key:
        st.session_state.update(key=key, summary="", root_cause="", validated=None)

    if st.button("Generate summary", type="primary", disabled=payload["status"] != "ok"):
        with st.spinner("Generating..."):
            try:
                st.session_state.summary = generate("summary", payload, provider)
                st.session_state.root_cause = generate("root_cause", payload, provider)
                st.session_state.validated = None
            except Exception as e:  # missing key, network, quota...
                st.error(f"Generation failed: {e}")

    if st.session_state.get("summary"):
        st.session_state.summary = st.text_area("Executive summary (editable)", st.session_state.summary, height=260)
        st.session_state.root_cause = st.text_area("Anomalies explained (editable)", st.session_state.root_cause, height=260)
        check = check_text(st.session_state.summary + "\n" + st.session_state.root_cause, payload)
        if check["ok"]:
            st.success(f"Number check: all {check['numbers_checked']} figures found in the JSON.")
        else:
            st.error("Figures not found in the JSON: " + ", ".join(u["text"] for u in check["ungrounded"]))

        st.subheader("Human validation")
        reviewer = st.text_input("Reviewer name")
        answers = {q: st.checkbox(q, key=f"chk_{i}") for i, q in enumerate(CHECKLIST)}
        notes = st.text_input("Notes (optional)")
        name = "app_" + "_".join(v for v in (channel, group, category, start, end) if v and v != "All")
        draft = render_markdown(name, payload, st.session_state.summary, st.session_state.root_cause, check, provider)
        if st.button("Record decision", disabled=not reviewer):
            md, info = apply_validation(draft, reviewer, answers, notes)
            st.session_state.validated = md
            config.OUTPUT_DIR.mkdir(exist_ok=True)
            pdf_path = config.OUTPUT_DIR / f"{name}_report.pdf"
            pdf_path.write_bytes(markdown_to_pdf(md))
            log(info, pdf_path.name)
            st.success(info["decision"])
        final = st.session_state.get("validated") or draft
        st.caption("Status of the export: " + ("validated report" if st.session_state.get("validated") else "AI draft"))
        st.download_button("Download report (PDF)", markdown_to_pdf(final),
                           file_name=f"{name}_report.pdf", mime="application/pdf")
