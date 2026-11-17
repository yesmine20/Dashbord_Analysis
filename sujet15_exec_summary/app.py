
"""Streamlit dashboard: KPI + charts on the left, AI narrative and human validation on the right.

Run: streamlit run app.py
"""

import json
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from src import config
from src.check_numbers import check_text
from src.detect import build_payload
from src.llm_client import PROVIDERS, default_provider, generate
from src.load_data import Scope, apply_scope, load_from_powerbi, monthly
from src.powerbi import PowerBIConnectionError
from src.semantic_model import validate_query_contract
from src.pdf_report import markdown_to_pdf
from src.report import render_markdown
from src.validate import CHECKLIST, apply_validation, log


# ================================================================
# TERMINAL LOGGING
# ================================================================

def terminal_header(title):
    print("\n" + "=" * 65, flush=True)
    print(f"  {title}", flush=True)
    print("=" * 65, flush=True)


def terminal_step(message):
    print(f"[INFO] {message}", flush=True)


def terminal_success(message, duration=None):
    if duration is not None:
        print(
            f"[OK] {message} ({duration:.2f} secondes)",
            flush=True
        )
    else:
        print(f"[OK] {message}", flush=True)


def terminal_error(message):
    print(f"[ERREUR] {message}", flush=True)


def severity_style(value):
    styles = {
        "critical": ("#fde2e1", "#b42318"),
        "high": ("#fff0d6", "#9a6700"),
        "moderate": ("#e6f4ea", "#137333"),
    }
    background, foreground = styles.get(
        str(value).lower(),
        ("#eef2f6", "#486581")
    )
    return (
        f"background-color: {background}; "
        f"color: {foreground}; "
        "font-weight: 700; "
        "text-transform: uppercase;"
    )


# ================================================================
# STREAMLIT CONFIGURATION
# ================================================================

st.set_page_config(
    page_title="Executive Summary & Anomalies",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    :root {
        --navy: #102a43;
        --blue: #1976d2;
        --teal: #00897b;
        --muted: #627d98;
        --surface: #ffffff;
        --border: #d9e2ec;
    }

    .stApp {
        background: #f5f7fb;
    }

    [data-testid="stHeader"] {
        background: rgba(245, 247, 251, 0.92);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #102a43 0%, #163b5c 100%);
    }

    [data-testid="stSidebar"] * {
        color: #f0f4f8;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="input"] > div {
        background: #ffffff;
        color: #102a43;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="input"] input {
        color: #102a43;
    }

    h1 {
        color: var(--navy);
        letter-spacing: -0.03em;
    }

    h2, h3 {
        color: var(--navy);
    }

    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 3px 12px rgba(16, 42, 67, 0.06);
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
    }

    [data-testid="stMetricValue"] {
        color: var(--navy);
    }

    [data-testid="stPlotlyChart"],
    [data-testid="stDataFrame"],
    [data-testid="stExpander"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        box-shadow: 0 3px 12px rgba(16, 42, 67, 0.04);
    }

    [data-testid="stPlotlyChart"] {
        padding: 8px;
    }

    .dashboard-kicker {
        color: var(--blue);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: -0.5rem;
    }

    .scope-caption {
        color: var(--muted);
        font-size: 0.92rem;
        margin-bottom: 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ================================================================
# STEP 1: POWER BI DATA EXTRACTION
# ================================================================

@st.cache_data(
    ttl=60,
    show_spinner="Interrogation du modèle sémantique Power BI..."
)
def get_data() -> pd.DataFrame:

    terminal_header("[ÉTAPE 1/6] MODÈLE SÉMANTIQUE & EXTRACTION DAX")

    start_time = time.perf_counter()

    terminal_step(
        "Connexion au modèle sémantique Power BI..."
    )

    try:
        df = load_from_powerbi()

        duration = time.perf_counter() - start_time

        terminal_success(
            f"Extraction terminée : {len(df)} lignes récupérées",
            duration
        )

        return df

    except Exception as exc:
        terminal_error(f"Échec de l'extraction Power BI : {exc}")
        raise


try:
    df = get_data()

except PowerBIConnectionError as exc:

    terminal_error(str(exc))

    st.error(
        "Connexion au modèle sémantique Power BI impossible."
    )

    st.code(str(exc))

    st.info(
        "Ouvre le PBIP dans Power BI Desktop et renseigne "
        "POWERBI_ADOMD_DATA_SOURCE, POWERBI_ADOMD_CATALOG "
        "et éventuellement POWERBI_ADOMD_DLL dans .env."
    )

    st.stop()

except Exception as exc:

    terminal_error(str(exc))

    st.error(
        "Une erreur est survenue pendant la récupération des données."
    )

    st.exception(exc)

    st.stop()


if df.empty:

    terminal_error("Aucune donnée récupérée depuis Power BI.")

    st.error(
        "La requête DAX n'a retourné aucune ligne "
        "pour les mesures et dimensions requises."
    )

    st.stop()


# Cette ligne s'affiche aussi si les données viennent du cache.
# Elle ne signifie donc pas forcément une nouvelle extraction Power BI.
terminal_success(
    f"Dataset disponible : {len(df)} lignes."
)


# ================================================================
# DASHBOARD HEADER
# ================================================================

st.markdown(
    '<div class="dashboard-kicker">POWER BI · GENERATIVE BI</div>',
    unsafe_allow_html=True
)

st.title(
    "Executive Summary & Anomalies - AdventureWorks Sales"
)

st.markdown(
    f'<div class="scope-caption">Source : modèle sémantique Power BI · '
    f'{len(df):,} combinaisons mensuelles · '
    f"{df['date'].min():%Y-%m} à {df['date'].max():%Y-%m}</div>",
    unsafe_allow_html=True
)


# ================================================================
# SIDEBAR: FILTERS AND AI PROVIDER
# ================================================================

with st.sidebar:

    st.header("Scope")

    if getattr(df, "attrs", {}).get("source_type") == "live_powerbi":
        st.success(
            "🟢 Connecté en direct au modèle Power BI"
        )
    else:
        st.info(
            "🟡 Mode Snapshot Certifié (PBIP / TMDL)"
        )

    with st.expander("Champs validés depuis PBIP/TMDL"):

        st.json(
            validate_query_contract()
        )

    channel = st.selectbox(
        "Channel",
        ["All"] + sorted(df["Channel"].unique())
    )

    group = st.selectbox(
        "Region",
        ["All"] + sorted(df["Group"].unique())
    )

    category = st.selectbox(
        "Category",
        ["All"] + sorted(df["Category"].unique())
    )

    months = [
        d.strftime("%Y-%m")
        for d in sorted(df["date"].unique())
    ]

    start, end = st.select_slider(
        "Period",
        options=months,
        value=(months[0], months[-1])
    )

    st.header("Text generation")

    options = ["mock"] + list(PROVIDERS)

    default = (
        default_provider()
        if default_provider() in options
        else "mock"
    )

    provider = st.selectbox(
        "Provider",
        options,
        index=options.index(default),
        help=(
            "'mock' = offline templates (no API key). "
            "Others need the .env file."
        )
    )

    st.caption(
        "Les KPI et segments proviennent des mesures DAX du modèle."
    )


# ================================================================
# STEP 2: FILTERING
# ================================================================

terminal_header("[ÉTAPE 2/6] FILTRAGE DU PÉRIMÈTRE (SCOPE & PUSH-DOWN)")

scope = Scope(
    None if channel == "All" else channel,
    None if group == "All" else group,
    None if category == "All" else category,
    start,
    end
)

terminal_step("Application des filtres sélectionnés...")

filter_start = time.perf_counter()

try:

    sub, _ = apply_scope(df, scope)

    filter_duration = time.perf_counter() - filter_start

    terminal_success(
        f"Filtrage terminé : {len(sub)} lignes conservées",
        filter_duration
    )

except Exception as exc:

    terminal_error(f"Erreur pendant le filtrage : {exc}")

    st.error(
        "Impossible d'appliquer les filtres."
    )

    st.exception(exc)

    st.stop()


# ================================================================
# STEP 3: ANOMALY DETECTION
# ================================================================

terminal_step(
    "Exécution du moteur de détection des anomalies..."
)

detection_start = time.perf_counter()

try:

    payload = build_payload(df, scope)

    detection_duration = time.perf_counter() - detection_start

    if payload["status"] == "ok":

        terminal_success(
            f"Détection terminée : "
            f"{len(payload['anomalies'])} anomalie(s) détectée(s)",
            detection_duration
        )

        # Détail des anomalies dans le terminal
        for anomaly in payload["anomalies"]:

            print(
                f"   - {anomaly['id']} | "
                f"{anomaly['rule']} | "
                f"{anomaly['period']} | "
                f"{anomaly['direction']} | "
                f"{anomaly.get('metrics', {}).get('severity', 'moderate')}",
                flush=True
            )

    else:

        terminal_error(
            payload.get(
                "reason",
                "Aucune donnée exploitable pour ce périmètre."
            )
        )

except Exception as exc:

    terminal_error(
        f"Erreur pendant la détection : {exc}"
    )

    st.error(
        "Le moteur de détection des anomalies a rencontré une erreur."
    )

    st.exception(exc)

    st.stop()


terminal_success(
    "Préparation des résultats terminée."
)

print("=" * 65, flush=True)


# ================================================================
# DASHBOARD LAYOUT
# ================================================================

left, right = st.columns([1.1, 1])


# ================================================================
# LEFT: KPIs, CHARTS AND ANOMALIES
# ================================================================

with left:

    st.header("Business performance")

    if payload["status"] != "ok":

        st.warning(
            "No data available for this scope. "
            + payload.get("reason", "")
        )

    else:

        # --------------------------------------------------------
        # KPIs
        # --------------------------------------------------------

        k = payload["kpis"]

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Sales",
            k["sales"]["display"]
        )

        c2.metric(
            "Cost",
            k["cost"]["display"]
        )

        c3.metric(
            "Profit",
            k["profit"]["display"]
        )

        c4.metric(
            "Margin",
            k["profit_margin_pct"]["display"]
        )

        # --------------------------------------------------------
        # Monthly sales
        # --------------------------------------------------------

        m = monthly(sub).reset_index()

        flagged = {
            a["period"]
            for a in payload["anomalies"]
            if a["rule"] in (
                "R1_margin_alert",
                "R2_sales_variation"
            )
        }

        m["flagged"] = (
            m["date"].dt.strftime("%Y-%m").isin(flagged)
        )

        fig = px.bar(
            m,
            x="date",
            y="Sales",
            color="flagged",
            title=(
                "Monthly sales "
                "(months with an anomaly highlighted)"
            ),
            color_discrete_map={
                True: "#d62728",
                False: "#1f77b4"
            }
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

        # --------------------------------------------------------
        # Monthly profit margin
        # --------------------------------------------------------

        fig2 = px.line(
            m,
            x="date",
            y="margin",
            title="Monthly profit margin (%)",
            markers=True
        )

        st.plotly_chart(
            fig2,
            width="stretch"
        )

        # --------------------------------------------------------
        # Margin by channel
        # --------------------------------------------------------

        if "Channel" in payload["breakdown"]:

            b = pd.DataFrame([
                {
                    "Channel": r["segment"],
                    "Margin %": r["margin_pct"]["value"]
                }
                for r in payload["breakdown"]["Channel"]
            ])

            st.plotly_chart(
                px.bar(
                    b,
                    x="Channel",
                    y="Margin %",
                    title="Margin by channel"
                ),
                width="stretch"
            )

        # --------------------------------------------------------
        # Detected anomalies
        # --------------------------------------------------------

        st.subheader(
            "Anomalies detected by the engine"
        )

        rows = [
            {
                "id": a["id"],
                "rule": a["rule"],
                "severity": a.get("metrics", {}).get("severity", "moderate"),
                "direction": a["direction"],
                "period": a["period"],
                "what": a["what"]
            }
            for a in payload["anomalies"]
        ]

        anomalies_frame = pd.DataFrame(rows)
        st.dataframe(
            anomalies_frame.style.map(
                severity_style,
                subset=["severity"]
            ),
            width="stretch",
            hide_index=True
        )

        # --------------------------------------------------------
        # JSON sent to the LLM
        # --------------------------------------------------------

        with st.expander("JSON sent to the LLM"):

            st.code(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2
                ),
                language="json"
            )


# ================================================================
# RIGHT: AI NARRATIVE AND HUMAN VALIDATION
# ================================================================

with right:

    st.header("AI narrative")

    # ------------------------------------------------------------
    # Reset AI results when filters or provider change
    # ------------------------------------------------------------

    key = (
        json.dumps(
            scope.as_dict(),
            sort_keys=True
        )
        + provider
    )

    if st.session_state.get("key") != key:

        st.session_state.update(
            key=key,
            summary="",
            root_cause="",
            validated=None
        )

    # ------------------------------------------------------------
    # STEP 4: AI GENERATION
    # ------------------------------------------------------------

    if st.button(
        "Generate summary",
        type="primary",
        disabled=payload["status"] != "ok"
    ):

        terminal_header("[ÉTAPE 4/6] GÉNÉRATION DU RÉSUMÉ EXÉCUTIF PAR LE LLM")

        try:

            # Generate executive summary
            ai_start = time.perf_counter()

            terminal_step(
                f"Envoi du payload au fournisseur IA : {provider}"
            )

            terminal_step(
                "Génération du résumé exécutif..."
            )

            st.session_state.summary = generate(
                "summary",
                payload,
                provider
            )

            summary_duration = (
                time.perf_counter() - ai_start
            )

            terminal_success(
                "Résumé exécutif généré",
                summary_duration
            )

            # Explain anomalies
            root_start = time.perf_counter()

            terminal_step(
                "Génération de l'explication des anomalies..."
            )

            st.session_state.root_cause = generate(
                "root_cause",
                payload,
                provider
            )

            root_duration = (
                time.perf_counter() - root_start
            )

            terminal_success(
                "Explication des anomalies générée",
                root_duration
            )

            st.session_state.validated = None

            terminal_success(
                "Génération IA terminée."
            )

            print("=" * 65, flush=True)

        except Exception as exc:

            terminal_error(
                f"Échec de la génération IA : {exc}"
            )

            st.error(
                f"Generation failed: {exc}"
            )

    # ------------------------------------------------------------
    # DISPLAY AI CONTENT
    # ------------------------------------------------------------

    if st.session_state.get("summary"):

        st.subheader(
            "Executive summary"
        )

        st.session_state.summary = st.text_area(
            "Executive summary (editable)",
            st.session_state.summary,
            height=260
        )

        st.session_state.root_cause = st.text_area(
            "Anomalies explained (editable)",
            st.session_state.root_cause,
            height=260
        )

        # --------------------------------------------------------
        # STEP 5: NUMBER VERIFICATION
        # --------------------------------------------------------

        terminal_step(
            "Vérification des chiffres du texte IA..."
        )

        check = check_text(
            st.session_state.summary
            + "\n"
            + st.session_state.root_cause,
            payload
        )

        if check["ok"]:

            terminal_success(
                f"Vérification terminée : "
                f"{check['numbers_checked']} chiffres vérifiés"
            )

            st.success(
                f"Number check: all "
                f"{check['numbers_checked']} figures found in the JSON."
            )

        else:

            terminal_error(
                "Certains chiffres du texte ne sont pas présents dans le JSON."
            )

            st.error(
                "Figures not found in the JSON: "
                + ", ".join(
                    u["text"]
                    for u in check["ungrounded"]
                )
            )

        # --------------------------------------------------------
        # STEP 6: HUMAN VALIDATION
        # --------------------------------------------------------

        st.subheader(
            "Human validation"
        )

        reviewer = st.text_input(
            "Reviewer name"
        )

        answers = {
            q: st.checkbox(
                q,
                key=f"chk_{i}"
            )
            for i, q in enumerate(CHECKLIST)
        }

        notes = st.text_input(
            "Notes (optional)"
        )

        name = "app_" + "_".join(
            v
            for v in (
                channel,
                group,
                category,
                start,
                end
            )
            if v and v != "All"
        )

        draft = render_markdown(
            name,
            payload,
            st.session_state.summary,
            st.session_state.root_cause,
            check,
            provider
        )

        # --------------------------------------------------------
        # Record human decision
        # --------------------------------------------------------

        if st.button(
            "Record decision",
            disabled=not reviewer
        ):

            terminal_step(
                "Enregistrement de la décision humaine..."
            )

            try:

                md, info = apply_validation(
                    draft,
                    reviewer,
                    answers,
                    notes
                )

                st.session_state.validated = md

                config.OUTPUT_DIR.mkdir(
                    exist_ok=True
                )

                pdf_path = (
                    config.OUTPUT_DIR
                    / f"{name}_report.pdf"
                )

                pdf_path.write_bytes(
                    markdown_to_pdf(md)
                )

                log(
                    info,
                    pdf_path.name
                )

                terminal_success(
                    f"Décision enregistrée : {info['decision']}"
                )

                terminal_success(
                    f"Rapport PDF créé : {pdf_path}"
                )

                st.success(
                    info["decision"]
                )

            except Exception as exc:

                terminal_error(
                    f"Erreur pendant la validation : {exc}"
                )

                st.error(
                    f"Validation failed: {exc}"
                )

        # --------------------------------------------------------
        # STEP 7: PDF EXPORT
        # --------------------------------------------------------

        final = (
            st.session_state.get("validated")
            or draft
        )

        st.caption(
            "Status of the export: "
            + (
                "validated report"
                if st.session_state.get("validated")
                else "AI draft"
            )
        )

        st.download_button(
            "Download report (PDF)",
            markdown_to_pdf(final),
            file_name=f"{name}_report.pdf",
            mime="application/pdf"
        )
