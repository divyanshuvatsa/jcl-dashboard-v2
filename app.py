"""
app.py - Jindal Coke Ltd. Financial Dashboard
==============================================
Streamlit dashboard wrapping the JCL 3-statement + DCF engine.
Dark neon theme, real-time interactivity, offline analyst.

Run locally:    streamlit run app.py
Deploy:         push to GitHub -> share.streamlit.io -> point at app.py

Module dependencies:
- engine.py    Pure financial logic
- visuals.py   Plotly charts only
- analyst.py   Rule-based smart analyst
- state.py     URL params + snapshot slots
"""

from __future__ import annotations

import io
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from engine import (
    JCLFinancialEngine,
    SCENARIO_PRESETS,
    covenant_stress_sweep,
    generate_insights,
    generate_text_report,
    parse_excel_assumptions,
    solve_implied_beta,
    solve_implied_terminal_growth,
)
import visuals as viz
from analyst import SmartAnalyst
from state import (
    delete_snapshot,
    encode_assumptions_to_url,
    load_snapshot,
    restore_assumptions_from_url,
    save_snapshot,
)


# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="JCL Financial Dashboard",
    page_icon="*",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Jindal Coke Ltd. Financial Dashboard\n"
                 "Real-time DCF, scenario analysis & smart analyst.",
    },
)


# =============================================================================
# DARK NEON CSS
# =============================================================================
DARK_NEON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

/* Page background -- pure dark */
.stApp {
    background: linear-gradient(180deg, #050A18 0%, #0A0F1E 100%) !important;
    color: #E8EDF5 !important;
    font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background: #050A18 !important;
}
[data-testid="stHeader"] { background: rgba(5,10,24,0.85) !important; backdrop-filter: blur(8px); }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0A0F1E !important;
    border-right: 1px solid rgba(0,240,255,0.10) !important;
}
[data-testid="stSidebar"] * { color: #E8EDF5 !important; font-family: 'JetBrains Mono', monospace !important; }

/* Titles */
h1, h2, h3, h4 {
    font-family: 'Space Grotesk', 'JetBrains Mono', monospace !important;
    color: #E8EDF5 !important;
    letter-spacing: -0.01em;
}
h1 {
    background: linear-gradient(135deg, #00F0FF 0%, #BF5FFF 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent !important;
    border-bottom: 1px solid rgba(0,240,255,0.10);
}
.stTabs [data-baseweb="tab"] {
    background: rgba(15,23,41,0.55) !important;
    color: #6B7FA3 !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 9px 16px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    letter-spacing: 0.04em;
    border: 1px solid transparent !important;
    transition: all 0.18s ease;
}
.stTabs [data-baseweb="tab"]:hover { color: #00F0FF !important; background: rgba(20,29,48,0.85) !important; }
.stTabs [aria-selected="true"] {
    background: rgba(0,240,255,0.06) !important;
    color: #00F0FF !important;
    border: 1px solid rgba(0,240,255,0.30) !important;
    border-bottom: 1px solid #00F0FF !important;
    box-shadow: 0 0 14px rgba(0,240,255,0.18);
}

/* Buttons */
.stButton button, .stDownloadButton button {
    background: linear-gradient(135deg, rgba(0,240,255,0.12), rgba(191,95,255,0.12)) !important;
    color: #00F0FF !important;
    border: 1px solid rgba(0,240,255,0.30) !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    letter-spacing: 0.05em;
    padding: 7px 16px !important;
    transition: all 0.18s ease !important;
}
.stButton button:hover, .stDownloadButton button:hover {
    background: linear-gradient(135deg, rgba(0,240,255,0.22), rgba(191,95,255,0.22)) !important;
    box-shadow: 0 0 18px rgba(0,240,255,0.30) !important;
    border-color: #00F0FF !important;
}

/* Inputs / sliders */
.stSlider [data-baseweb="slider"] [role="slider"] { background: #00F0FF !important; box-shadow: 0 0 10px #00F0FF !important; }
.stSelectbox [data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {
    background: #0F1729 !important; color: #E8EDF5 !important;
    border: 1px solid rgba(0,240,255,0.20) !important; border-radius: 5px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Expanders */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {
    background: rgba(15,23,41,0.55) !important;
    color: #E8EDF5 !important;
    border-radius: 6px !important;
    border: 1px solid rgba(0,240,255,0.10) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
}

/* Metric cards (built-in) -- restyle */
[data-testid="stMetric"] {
    background: rgba(10,15,30,0.7) !important;
    padding: 14px 18px !important;
    border-radius: 8px !important;
    border: 1px solid rgba(0,240,255,0.15) !important;
}
[data-testid="stMetricLabel"] {
    color: #6B7FA3 !important; font-size: 10px !important; letter-spacing: 0.10em;
    text-transform: uppercase;
}
[data-testid="stMetricValue"] {
    color: #00F0FF !important; font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
}
[data-testid="stMetricDelta"] { font-size: 11px !important; }

/* Custom KPI card  */
.kpi-card {
    background: rgba(10,15,30,0.85);
    border: 1px solid rgba(0,240,255,0.15);
    border-radius: 10px;
    padding: 14px 16px 8px 16px;
    height: 100%;
    transition: all 0.18s ease;
}
.kpi-card:hover { border-color: rgba(0,240,255,0.4); box-shadow: 0 0 18px rgba(0,240,255,0.15); }
.kpi-label {
    color: #6B7FA3; font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.12em; font-weight: 500;
}
.kpi-value {
    color: #00F0FF; font-family: 'JetBrains Mono', monospace;
    font-size: 22px; font-weight: 700; margin-top: 2px;
}
.kpi-sub { color: #6B7FA3; font-size: 11px; margin-top: 2px; }

/* Insight pills */
.insight-row { padding: 8px 0; border-bottom: 1px dotted rgba(0,240,255,0.07); }
.insight-row:last-child { border-bottom: none; }
.insight-good    { color: #00FF9D; }
.insight-caution { color: #FFB800; }
.insight-warning { color: #FFB800; }
.insight-alert   { color: #FF2D78; font-weight: 600; }

/* Tables */
.dark-table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.dark-table th {
    background: rgba(0,240,255,0.07); color: #00F0FF; padding: 9px 11px;
    text-align: right; border-bottom: 1px solid rgba(0,240,255,0.20);
    font-weight: 600; letter-spacing: 0.05em; font-size: 11px;
}
.dark-table th:first-child, .dark-table td:first-child { text-align: left; }
.dark-table td { color: #E8EDF5; padding: 8px 11px; text-align: right; border-bottom: 1px dotted rgba(0,240,255,0.05); }
.dark-table tr:hover { background: rgba(0,240,255,0.025); }
.dark-table tr.row-bold td { background: rgba(0,240,255,0.04); font-weight: 700; color: #00F0FF; }

/* Diff badges in sidebar */
.diff-pill {
    display: inline-block; padding: 1px 6px; margin-left: 6px;
    background: rgba(255,184,0,0.12); color: #FFB800;
    border: 1px solid rgba(255,184,0,0.35); border-radius: 3px;
    font-size: 9px; letter-spacing: 0.05em; vertical-align: middle;
}

/* Chat */
[data-testid="stChatMessage"] {
    background: rgba(10,15,30,0.6) !important;
    border: 1px solid rgba(0,240,255,0.10) !important;
    border-radius: 8px !important;
    padding: 11px 14px !important;
}

/* Hide footer */
footer, #MainMenu { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }

/* Code blocks */
code, pre { font-family: 'JetBrains Mono', monospace !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0A0F1E; }
::-webkit-scrollbar-thumb { background: rgba(0,240,255,0.2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,240,255,0.4); }

/* Section divider */
.section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,240,255,0.30), transparent);
    margin: 18px 0 14px 0;
}
</style>
"""
st.markdown(DARK_NEON_CSS, unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INIT
# =============================================================================
def _init_state():
    defaults = {
        "scenario": "Base",
        "assumptions": dict(SCENARIO_PRESETS["Base"]),
        "monte_carlo_evs": None,
        "analyst_history": [],
        "stress_sweep_result": None,
        "saved_slots": {},
        "state_restored_from_url": False,
        "implied_beta_result": None,
        "implied_g_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.state_restored_from_url:
        if restore_assumptions_from_url():
            pass
        st.session_state.state_restored_from_url = True


_init_state()


# =============================================================================
# CACHED MODEL RUNNERS
# =============================================================================
@st.cache_data(show_spinner=False)
def run_model(assumptions_tuple: Tuple) -> Dict:
    a = dict(assumptions_tuple)
    return JCLFinancialEngine(assumptions=a).build()


@st.cache_data(show_spinner=False)
def run_tornado(assumptions_tuple: Tuple) -> pd.DataFrame:
    a = dict(assumptions_tuple)
    return JCLFinancialEngine(assumptions=a).tornado_analysis()


@st.cache_data(show_spinner=False)
def run_monte_carlo(assumptions_tuple: Tuple, n: int = 1000) -> np.ndarray:
    a = dict(assumptions_tuple)
    return JCLFinancialEngine(assumptions=a).monte_carlo(n=n, seed=42)


@st.cache_data(show_spinner=False)
def run_all_scenarios_cached() -> Dict[str, Dict]:
    return {
        name: JCLFinancialEngine(assumptions=dict(preset)).build()
        for name, preset in SCENARIO_PRESETS.items()
    }


def _assumptions_tuple(a: dict) -> Tuple:
    """Hashable + ordered representation of assumptions."""
    return tuple(sorted(a.items()))


# =============================================================================
# SIDEBAR
# =============================================================================
def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='font-size:18px; font-weight:700; color:#00F0FF; "
            "letter-spacing:0.05em; margin-bottom:4px;'>JCL CONTROL DECK</div>"
            "<div style='font-size:10px; color:#6B7FA3; margin-bottom:14px;'>"
            "Live model | INR Crores</div>",
            unsafe_allow_html=True,
        )

        # ---------- Scenario picker
        st.markdown("**Scenario**")
        scn_options = ["Bull", "Base", "Bear", "Custom"]
        try:
            scn_idx = scn_options.index(st.session_state.scenario)
        except ValueError:
            scn_idx = 1
        new_scn = st.selectbox(
            "Pick scenario",
            scn_options,
            index=scn_idx,
            label_visibility="collapsed",
            key="scn_picker",
        )
        if new_scn != st.session_state.scenario:
            st.session_state.scenario = new_scn
            if new_scn in SCENARIO_PRESETS:
                st.session_state.assumptions = SCENARIO_PRESETS[new_scn].copy()
            st.rerun()

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("Reset to Base", use_container_width=True):
                st.session_state.scenario = "Base"
                st.session_state.assumptions = SCENARIO_PRESETS["Base"].copy()
                st.session_state.monte_carlo_evs = None
                st.rerun()
        with col_r2:
            if st.button("Share URL", use_container_width=True):
                encode_assumptions_to_url(
                    st.session_state.assumptions, st.session_state.scenario
                )
                st.toast("URL updated -> copy from address bar", icon="*")

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

        # ---------- Diff tracker
        base = SCENARIO_PRESETS["Base"]
        diffs = []
        for k, v in st.session_state.assumptions.items():
            bv = base.get(k)
            if bv is None:
                continue
            try:
                if abs(float(v) - float(bv)) > 1e-6:
                    diffs.append((k, float(v), float(bv)))
            except (TypeError, ValueError):
                continue

        diff_label = (
            f"<span style='color:#00FF9D;'>* No changes from Base</span>"
            if not diffs else
            f"<span style='color:#FFB800; font-weight:600;'>* "
            f"{len(diffs)} change{'s' if len(diffs) != 1 else ''} from Base</span>"
        )
        st.markdown(f"<div style='font-size:11px; margin-bottom:6px;'>{diff_label}</div>",
                    unsafe_allow_html=True)
        if diffs:
            for k, v, bv in diffs:
                st.markdown(
                    f"`{k}`: <span style='color:#FFB800;'>{v:.4g}</span> "
                    f"<span style='color:#6B7FA3;'>(base {bv:.4g})</span>",
                    unsafe_allow_html=True,
                )

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

        # ---------- Drivers
        a = st.session_state.assumptions
        st.markdown("**Operations**")
        a["cob2_util_steady"] = st.slider(
            "COB-2 Utilisation (steady)", 0.20, 1.00,
            float(a["cob2_util_steady"]), 0.01, format="%.2f",
        )
        a["coke_realization"] = st.slider(
            "Coke Realisation (INR/MT)", 15_000, 50_000,
            int(a["coke_realization"]), 500,
        )
        a["cogs_pct"] = st.slider(
            "COGS % (FY25A anchor)", 0.70, 0.95,
            float(a["cogs_pct"]), 0.005, format="%.3f",
        )
        a["capex_intensity"] = st.slider(
            "Maintenance Capex %", 0.005, 0.060,
            float(a["capex_intensity"]), 0.005, format="%.3f",
        )

        st.markdown("**Financing**")
        a["interest_rate"] = st.slider(
            "Interest Rate (%)", 0.04, 0.20,
            float(a["interest_rate"]), 0.005, format="%.3f",
        )
        a["target_de"] = st.slider(
            "Target D/E (x)", 0.10, 2.50,
            float(a["target_de"]), 0.05, format="%.2f",
        )

        st.markdown("**Cost of Capital**")
        a["unlevered_beta"] = st.slider(
            "Unlevered Beta", 0.40, 2.00,
            float(a["unlevered_beta"]), 0.05, format="%.2f",
        )
        a["rf_rate"] = st.slider(
            "Risk-Free Rate (%)", 0.03, 0.12,
            float(a["rf_rate"]), 0.0025, format="%.4f",
        )
        a["erp"] = st.slider(
            "Equity Risk Premium (%)", 0.04, 0.12,
            float(a["erp"]), 0.0025, format="%.4f",
        )
        a["terminal_growth"] = st.slider(
            "Terminal Growth (g)", -0.01, 0.06,
            float(a["terminal_growth"]), 0.005, format="%.3f",
        )

        st.session_state.assumptions = a
        if (st.session_state.scenario in SCENARIO_PRESETS
                and a != SCENARIO_PRESETS[st.session_state.scenario]):
            st.session_state.scenario = "Custom"

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

        # ---------- Saved snapshots
        st.markdown("**Saved Snapshots**")
        col_s1, col_s2 = st.columns([3, 2])
        with col_s1:
            snap_name = st.text_input(
                "Slot name", value="", placeholder="e.g. Bear+Refi",
                label_visibility="collapsed", key="snap_name",
            )
        with col_s2:
            if st.button("Save", use_container_width=True):
                actual = save_snapshot(snap_name, st.session_state.assumptions)
                st.toast(f"Saved as `{actual}`", icon="*")
                st.rerun()

        if st.session_state.saved_slots:
            for name in list(st.session_state.saved_slots.keys()):
                cs1, cs2, cs3 = st.columns([3, 1, 1])
                cs1.markdown(
                    f"<div style='font-size:11px; padding-top:4px; "
                    f"color:#E8EDF5;'>{name}</div>",
                    unsafe_allow_html=True,
                )
                if cs2.button("Load", key=f"load_{name}", use_container_width=True):
                    if load_snapshot(name) is not None:
                        st.toast(f"Loaded `{name}`", icon="*")
                        st.rerun()
                if cs3.button("X", key=f"del_{name}", use_container_width=True):
                    delete_snapshot(name)
                    st.rerun()
        else:
            st.markdown(
                "<div style='font-size:10px; color:#6B7FA3;'>"
                f"No snapshots saved yet (max {5}).</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

        # ---------- Excel sync
        st.markdown("**Sync from Excel**")
        st.markdown(
            "<div style='font-size:10px; color:#6B7FA3; margin-bottom:6px;'>"
            "Upload `JCL_Financial_Model_EXP.xlsx` to pull Base assumptions "
            "from the Scenario Engine sheet.</div>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Excel file", type=["xlsx"], label_visibility="collapsed",
            key="excel_uploader",
        )
        if uploaded is not None:
            parsed = parse_excel_assumptions(uploaded)
            if parsed:
                for k, v in parsed.items():
                    st.session_state.assumptions[k] = float(v)
                st.session_state.scenario = "Custom"
                st.success(
                    f"Pulled {len(parsed)} assumptions from Excel.",
                    icon="*",
                )
                st.rerun()
            else:
                st.error(
                    "Could not parse the Scenario Engine sheet. "
                    "Verify sheet name and Base column.",
                    icon="*",
                )


# =============================================================================
# HEADER
# =============================================================================
def render_header(results: Dict):
    dcf = results["dcf"]
    insights = generate_insights(results)

    title_col, scn_col = st.columns([3, 1])
    with title_col:
        st.markdown(
            "<h1 style='font-size:34px; margin-bottom:0;'>"
            "JINDAL COKE LTD.</h1>"
            "<div style='color:#6B7FA3; font-size:12px; letter-spacing:0.10em; "
            "margin-top:0; margin-bottom:14px;'>"
            "FINANCIAL DASHBOARD &nbsp;|&nbsp; FY24A - FY33E "
            "&nbsp;|&nbsp; INR CRORES</div>",
            unsafe_allow_html=True,
        )
    with scn_col:
        scn_color = {
            "Bull": "#00FF9D", "Base": "#00F0FF",
            "Bear": "#FF2D78", "Custom": "#BF5FFF",
        }.get(st.session_state.scenario, "#00F0FF")
        st.markdown(
            f"<div style='text-align:right; padding-top:14px;'>"
            f"<div style='color:#6B7FA3; font-size:10px; letter-spacing:0.12em;'>"
            f"ACTIVE SCENARIO</div>"
            f"<div style='color:{scn_color}; font-size:24px; font-weight:700; "
            f"font-family:JetBrains Mono;'>"
            f"{st.session_state.scenario.upper()}</div></div>",
            unsafe_allow_html=True,
        )

    # Insights row
    if insights:
        st.markdown(
            "<div style='background:rgba(15,23,41,0.55); padding:10px 14px; "
            "border-radius:8px; border:1px solid rgba(0,240,255,0.10); "
            "margin-bottom:14px;'>",
            unsafe_allow_html=True,
        )
        for ins in insights:
            level_class = {
                "good": "insight-good", "caution": "insight-caution",
                "warning": "insight-warning", "alert": "insight-alert",
            }.get(ins["level"], "insight-good")
            st.markdown(
                f"<div class='insight-row {level_class}'>"
                f"<span style='font-weight:600; letter-spacing:0.05em;'>"
                f"[{ins['icon']}]</span> {ins['text']}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# KPI MATRIX
# =============================================================================
def _kpi_card(label: str, value: str, sub: str, sparkline_fig=None,
              spark_color: str = "#00F0FF"):
    st.markdown(
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"<div class='kpi-sub'>{sub}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if sparkline_fig is not None:
        st.plotly_chart(
            sparkline_fig,
            use_container_width=True,
            config={"displayModeBar": False, "staticPlot": True},
        )


def render_kpi_matrix(results: Dict):
    dcf = results["dcf"]
    inc = results["income"]
    rat = results["ratios"]

    spark_ebitda = viz.chart_kpi_sparkline(
        list(inc["EBITDA_Margin"]), color="#FFB800"
    )
    spark_dscr = viz.chart_kpi_sparkline(
        list(rat["DSCR"]), color="#00FF9D"
    )
    spark_nd = viz.chart_kpi_sparkline(
        list(rat["Net_Debt"]), color="#FF2D78"
    )
    spark_roce = viz.chart_kpi_sparkline(
        list(rat["ROCE"]), color="#BF5FFF"
    )

    cols = st.columns(4)
    with cols[0]:
        _kpi_card(
            "Value / Share",
            f"INR {dcf['value_per_share']:,.0f}",
            f"EV: INR {dcf['enterprise_value']:,.0f} Cr",
        )
    with cols[1]:
        _kpi_card(
            "WACC",
            f"{dcf['wacc']:.2%}",
            f"g: {dcf['terminal_growth']:.2%}",
        )
    with cols[2]:
        _kpi_card(
            "FY29E EBITDA Margin",
            f"{inc.loc['FY29E', 'EBITDA_Margin']:.1%}",
            "FY24A-FY33E trajectory",
            sparkline_fig=spark_ebitda, spark_color="#FFB800",
        )
    with cols[3]:
        _kpi_card(
            "Min DSCR",
            f"{rat['DSCR'].min():.2f}x",
            f"{rat['DSCR'].idxmin()} (floor 1.20x)",
            sparkline_fig=spark_dscr, spark_color="#00FF9D",
        )

    cols2 = st.columns(4)
    with cols2[0]:
        _kpi_card(
            "% EV from Terminal",
            f"{dcf['pct_ev_terminal']:.1%}",
            "Lower = healthier",
        )
    with cols2[1]:
        _kpi_card(
            "Peak ND/EBITDA",
            f"{rat['Net_Debt_EBITDA'].max():.2f}x",
            "Year of peak leverage",
        )
    with cols2[2]:
        _kpi_card(
            "Net Debt FY29E",
            f"INR {rat.loc['FY29E', 'Net_Debt']:,.0f} Cr",
            "Negative = net cash",
            sparkline_fig=spark_nd, spark_color="#FF2D78",
        )
    with cols2[3]:
        _kpi_card(
            "FY29E ROCE",
            f"{rat.loc['FY29E', 'ROCE']:.1%}",
            "Return on capital employed",
            sparkline_fig=spark_roce, spark_color="#BF5FFF",
        )


# =============================================================================
# TABLE RENDERERS (HTML, dark)
# =============================================================================
def render_styled_table_html(df: pd.DataFrame, fmt_map: Dict[str, str],
                             bold_rows: list = None) -> str:
    bold_rows = bold_rows or []
    cols = ["Year"] + [c for c in df.index]
    rows_html = []
    for label, row in df.iterrows():
        row_class = "row-bold" if label in bold_rows else ""
        cells = [f"<td>{label}</td>"]
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                cells.append("<td>-</td>")
                continue
            fmt = fmt_map.get(col, "{:,.1f}")
            cells.append(f"<td>{fmt.format(val)}</td>")
        rows_html.append(f"<tr class='{row_class}'>" + "".join(cells) + "</tr>")
    head_cells = ["<th>Metric</th>"] + [f"<th>{c}</th>" for c in df.columns]
    return ("<table class='dark-table'><thead><tr>"
            + "".join(head_cells)
            + "</tr></thead><tbody>"
            + "".join(rows_html)
            + "</tbody></table>")


def _income_table_html(income_df: pd.DataFrame) -> str:
    keep = ["Net_Sales", "COGS", "Gross_Profit", "Employee", "SGA",
            "EBITDA", "Depreciation", "EBIT", "Other_Income", "Interest",
            "PBT", "Tax", "PAT"]
    df = income_df[keep].T
    fmt = {c: "{:,.1f}" for c in df.columns}
    bold = ["Gross_Profit", "EBITDA", "EBIT", "PBT", "PAT"]
    return render_styled_table_html(df, fmt, bold)


def _balance_table_html(balance_df: pd.DataFrame) -> str:
    keep = ["Share_Capital", "Reserves_Surplus", "Total_Equity",
            "LT_Borrowings", "Trade_Payables",
            "Net_Fixed_Assets", "CWIP", "Inventories",
            "Trade_Receivables", "Cash", "Total_Assets"]
    df = balance_df[keep].T
    fmt = {c: "{:,.0f}" for c in df.columns}
    bold = ["Total_Equity", "Total_Assets"]
    return render_styled_table_html(df, fmt, bold)


def _cashflow_table_html(cfs_df: pd.DataFrame) -> str:
    df = cfs_df.T
    fmt = {c: "{:,.1f}" for c in df.columns}
    bold = ["CFO", "CFI", "CFF", "Net_Change_Cash", "Closing_Cash"]
    return render_styled_table_html(df, fmt, bold)


def _ratios_table_html(ratios_df: pd.DataFrame) -> str:
    pct_cols = ["EBITDA_Margin", "PAT_Margin", "ROE", "ROCE", "Gross_Margin"]
    x_cols = ["Debt_Equity", "Net_Debt_EBITDA", "DSCR",
              "Interest_Coverage", "Current_Ratio"]
    cr_cols = ["Net_Debt", "Total_Debt"]
    df = ratios_df[pct_cols + x_cols + cr_cols].T
    fmt = {c: "{:,.0f}" if any(b in c for b in cr_cols) else "{:,.2f}"
           for c in df.columns}
    return render_styled_table_html(df, fmt)


# =============================================================================
# TAB BUILDERS
# =============================================================================
def tab_valuation_bridge(results: Dict):
    st.markdown("### Valuation Bridge & DCF Composition")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:14px;'>"
        "EV-to-Equity bridge | Per-year present value composition "
        "| Reverse-DCF solver</div>",
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            viz.chart_valuation_bridge(results["dcf"]),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_valuation_bridge"}},
        )
    with col2:
        st.plotly_chart(
            viz.chart_dcf_components(results["dcf"]),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_dcf_components"}},
        )

    st.plotly_chart(
        viz.chart_revenue_ebitda_trend(results["income"]),
        use_container_width=True,
        config={"displaylogo": False,
                "toImageButtonOptions": {"format": "png", "scale": 3,
                                         "filename": "JCL_revenue_ebitda"}},
    )

    pct_mode = st.checkbox("Show as YoY revenue growth (%)", value=False,
                           key="rev_pct_toggle")
    if pct_mode:
        st.plotly_chart(
            viz.chart_revenue_ebitda_trend(results["income"], pct_mode=True),
            use_container_width=True,
            config={"displaylogo": False},
        )

    # ---------- Reverse DCF
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("### Reverse DCF Solver")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:12px;'>"
        "Given a target intrinsic value per share, what unlevered beta or "
        "terminal growth rate does the market imply?</div>",
        unsafe_allow_html=True,
    )

    rcol1, rcol2 = st.columns(2)
    with rcol1:
        st.markdown("**Solve for Implied Beta**")
        target_vps_b = st.number_input(
            "Target VPS (INR)", min_value=100.0, max_value=2000.0,
            value=600.0, step=10.0, key="solve_beta_vps",
        )
        if st.button("Solve Implied Beta", key="btn_solve_beta",
                     use_container_width=True):
            res = solve_implied_beta(
                st.session_state.assumptions, target_vps=target_vps_b
            )
            st.session_state.implied_beta_result = res

        res_b = st.session_state.implied_beta_result
        if res_b is not None:
            st.markdown(
                f"<div class='kpi-card'>"
                f"<div class='kpi-label'>Implied Unlevered Beta</div>"
                f"<div class='kpi-value'>{res_b['beta']:.3f}</div>"
                f"<div class='kpi-sub'>Implied WACC: "
                f"{res_b['implied_wacc']:.2%} | "
                f"Achieved VPS: INR {res_b['achieved_vps']:,.0f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.session_state.implied_beta_result is None:
                st.markdown(
                    "<div style='color:#6B7FA3; font-size:11px;'>"
                    "Click solve to see the implied beta. Target may be "
                    "outside achievable range (beta in [0.30, 2.50]).</div>",
                    unsafe_allow_html=True,
                )

    with rcol2:
        st.markdown("**Solve for Implied Terminal Growth**")
        target_vps_g = st.number_input(
            "Target VPS (INR)", min_value=100.0, max_value=2000.0,
            value=600.0, step=10.0, key="solve_g_vps",
        )
        if st.button("Solve Implied g", key="btn_solve_g",
                     use_container_width=True):
            res = solve_implied_terminal_growth(
                st.session_state.assumptions, target_vps=target_vps_g
            )
            st.session_state.implied_g_result = res

        res_g = st.session_state.implied_g_result
        if res_g is not None:
            st.markdown(
                f"<div class='kpi-card'>"
                f"<div class='kpi-label'>Implied Terminal Growth (g)</div>"
                f"<div class='kpi-value'>{res_g['terminal_growth']:.2%}</div>"
                f"<div class='kpi-sub'>Achieved VPS: "
                f"INR {res_g['achieved_vps']:,.0f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.session_state.implied_g_result is None:
                st.markdown(
                    "<div style='color:#6B7FA3; font-size:11px;'>"
                    "Click solve to see the implied g. Target may be "
                    "outside achievable range (g in [-1%, 7%]).</div>",
                    unsafe_allow_html=True,
                )


def tab_three_statement(results: Dict):
    st.markdown("### Revenue, Cash Flow & Debt Profile")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:14px;'>"
        "Composition by product | Cash flow build | Debt vs DSCR</div>",
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            viz.chart_revenue_mix(results["revenue"]),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_revenue_mix"}},
        )
    with col2:
        st.plotly_chart(
            viz.chart_debt_coverage(results["ratios"], results["balance"]),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_debt_coverage"}},
        )

    st.plotly_chart(
        viz.chart_cashflow_build(results["cashflow"]),
        use_container_width=True,
        config={"displaylogo": False,
                "toImageButtonOptions": {"format": "png", "scale": 3,
                                         "filename": "JCL_cashflow"}},
    )


def tab_sensitivity(results: Dict):
    st.markdown("### Sensitivity & Risk")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:14px;'>"
        "WACC x g heatmap | Tornado of value drivers | "
        "Covenant stress sweep</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.plotly_chart(
            viz.chart_wacc_sensitivity(
                results["sensitivity"],
                results["dcf"]["wacc"],
                results["dcf"]["terminal_growth"],
            ),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_wacc_sens"}},
        )
    with col2:
        with st.spinner("Computing tornado..."):
            tornado = run_tornado(_assumptions_tuple(st.session_state.assumptions))
        st.plotly_chart(
            viz.chart_tornado(tornado),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_tornado"}},
        )

    # ---------- Covenant stress
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("### Covenant Stress Tester")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:12px;'>"
        "Sweep one driver to find the breach point where DSCR falls below "
        "1.20x. Useful for credit committee discussion.</div>",
        unsafe_allow_html=True,
    )

    sc1, sc2, sc3 = st.columns([2, 1, 1])
    with sc1:
        driver = st.selectbox(
            "Driver to stress",
            options=["interest_rate", "cogs_pct", "cob2_util_steady"],
            format_func=lambda k: {
                "interest_rate": "Interest Rate",
                "cogs_pct": "COGS % of Sales",
                "cob2_util_steady": "COB-2 Utilisation",
            }[k],
            key="stress_driver",
        )
    with sc2:
        floor = st.number_input(
            "Covenant floor (DSCR)", min_value=1.0, max_value=2.5,
            value=1.20, step=0.05, key="stress_floor",
        )
    with sc3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("Run Stress", use_container_width=True, key="btn_stress"):
            with st.spinner("Sweeping driver..."):
                st.session_state.stress_sweep_result = covenant_stress_sweep(
                    st.session_state.assumptions,
                    driver_key=driver, covenant_floor=floor, steps=30,
                )

    sweep = st.session_state.stress_sweep_result
    if sweep is not None and sweep["driver_key"] == driver:
        st.plotly_chart(
            viz.chart_covenant_stress(sweep),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_stress"}},
        )
        if sweep["breach_value"] is not None:
            st.markdown(
                f"<div class='kpi-card' style='border-color:rgba(255,45,120,0.4);'>"
                f"<div class='kpi-label' style='color:#FF2D78;'>Covenant Breach Point</div>"
                f"<div class='kpi-value' style='color:#FF2D78;'>"
                f"{sweep['breach_value']:.2%}</div>"
                f"<div class='kpi-sub'>"
                f"Min DSCR drops below {floor:.2f}x in {sweep['breach_year']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='kpi-card' style='border-color:rgba(0,255,157,0.4);'>"
                f"<div class='kpi-label' style='color:#00FF9D;'>No Breach in Sweep Range</div>"
                f"<div class='kpi-value' style='color:#00FF9D;'>SAFE</div>"
                f"<div class='kpi-sub'>DSCR stays above {floor:.2f}x across the entire range.</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<div style='color:#6B7FA3; font-size:11px;'>"
            "Click Run Stress to see how DSCR responds to driver changes.</div>",
            unsafe_allow_html=True,
        )


def tab_monte_carlo(results: Dict):
    st.markdown("### Monte Carlo Simulation")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:14px;'>"
        "Probabilistic enterprise-value distribution | Stochastic shocks on "
        "five key drivers</div>",
        unsafe_allow_html=True,
    )

    mc1, mc2 = st.columns([1, 3])
    with mc1:
        n_sims = st.select_slider(
            "Simulations", options=[200, 500, 1000, 2000, 5000],
            value=1000, key="mc_n",
        )
        if st.button("Run Simulation", use_container_width=True, key="btn_mc"):
            with st.spinner(f"Running {n_sims} simulations..."):
                st.session_state.monte_carlo_evs = run_monte_carlo(
                    _assumptions_tuple(st.session_state.assumptions), n_sims
                )

    with mc2:
        evs = st.session_state.monte_carlo_evs
        if evs is not None and len(evs) > 0:
            st.plotly_chart(
                viz.chart_monte_carlo(evs, results["dcf"]["enterprise_value"]),
                use_container_width=True,
                config={"displaylogo": False,
                        "toImageButtonOptions": {"format": "png", "scale": 3,
                                                 "filename": "JCL_monte_carlo"}},
            )
            mean_ev = float(np.mean(evs))
            p5 = float(np.percentile(evs, 5))
            p95 = float(np.percentile(evs, 95))
            std = float(np.std(evs))

            kpi_cols = st.columns(4)
            with kpi_cols[0]:
                _kpi_card("Mean EV", f"INR {mean_ev:,.0f} Cr",
                          f"vs Base INR {results['dcf']['enterprise_value']:,.0f} Cr")
            with kpi_cols[1]:
                _kpi_card("Std Deviation", f"INR {std:,.0f} Cr",
                          f"CV: {std / mean_ev * 100:.1f}%")
            with kpi_cols[2]:
                _kpi_card("P5 (Downside)", f"INR {p5:,.0f} Cr",
                          f"5% probability below")
            with kpi_cols[3]:
                _kpi_card("P95 (Upside)", f"INR {p95:,.0f} Cr",
                          f"5% probability above")
        else:
            st.markdown(
                "<div style='color:#6B7FA3; font-size:11px; padding:24px; "
                "text-align:center;'>"
                "Click Run Simulation to generate the EV distribution.</div>",
                unsafe_allow_html=True,
            )


def tab_detailed(results: Dict):
    st.markdown("### Detailed Statements")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:14px;'>"
        "Income Statement | Balance Sheet | Cash Flow | Ratios | "
        "Excel & report downloads</div>",
        unsafe_allow_html=True,
    )

    sub_inc, sub_bs, sub_cfs, sub_rat = st.tabs(
        ["Income", "Balance Sheet", "Cash Flow", "Ratios"]
    )
    with sub_inc:
        st.markdown(_income_table_html(results["income"]),
                    unsafe_allow_html=True)
    with sub_bs:
        st.markdown(_balance_table_html(results["balance"]),
                    unsafe_allow_html=True)
    with sub_cfs:
        st.markdown(_cashflow_table_html(results["cashflow"]),
                    unsafe_allow_html=True)
    with sub_rat:
        st.markdown(_ratios_table_html(results["ratios"]),
                    unsafe_allow_html=True)

    # ---------- Downloads
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("### Downloads")
    dl1, dl2 = st.columns(2)
    with dl1:
        # Build multi-sheet xlsx in memory
        buf = io.BytesIO()
        try:
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                results["income"].to_excel(writer, sheet_name="Income")
                results["balance"].to_excel(writer, sheet_name="Balance")
                results["cashflow"].to_excel(writer, sheet_name="CashFlow")
                results["ratios"].to_excel(writer, sheet_name="Ratios")
                results["revenue"].to_excel(writer, sheet_name="Revenue")
                results["sensitivity"].to_excel(writer, sheet_name="WACC_x_g")
                pd.DataFrame([results["assumptions"]]).T.to_excel(
                    writer, sheet_name="Assumptions"
                )
                if "fcff" in results["dcf"]:
                    results["dcf"]["fcff"].to_excel(
                        writer, sheet_name="FCFF_Build"
                    )
            buf.seek(0)
            st.download_button(
                "Download Excel Workbook (.xlsx)",
                data=buf,
                file_name=f"JCL_Model_{st.session_state.scenario}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Excel generation failed: {e}")

    with dl2:
        report = generate_text_report(
            results, st.session_state.assumptions, st.session_state.scenario
        )
        st.download_button(
            "Download Analyst Report (.md)",
            data=report,
            file_name=f"JCL_Report_{st.session_state.scenario}.md",
            mime="text/markdown",
            use_container_width=True,
        )


def tab_smart_analyst(results: Dict, all_scen: Dict[str, Dict]):
    st.markdown("### Smart Analyst")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:14px;'>"
        "Ask questions in plain English. The analyst routes your query "
        "through 14 specialist templates and answers with live model numbers. "
        "Fully offline, no API.</div>",
        unsafe_allow_html=True,
    )

    analyst = SmartAnalyst(
        results, st.session_state.assumptions,
        st.session_state.scenario, all_scen,
    )

    # Quick-prompt buttons
    st.markdown("**Quick prompts**")
    qp_cols = st.columns(4)
    quick_prompts = [
        ("Walk me through WACC", "Walk me through the WACC build"),
        ("Covenant status", "What's the DSCR and covenant status?"),
        ("Top 3 value drivers", "What are the top 3 sensitivity drivers?"),
        ("Scenario comparison", "Compare Bull, Base and Bear scenarios"),
    ]
    pending_query = None
    for col, (label, q) in zip(qp_cols, quick_prompts):
        if col.button(label, use_container_width=True, key=f"qp_{label}"):
            pending_query = q

    qp_cols2 = st.columns(4)
    quick_prompts2 = [
        ("Margin trajectory", "Why are margins moving from FY25 to FY29?"),
        ("Debt schedule", "Walk me through the debt and deleveraging"),
        ("Cash flow build", "Explain the cash flow trajectory"),
        ("Full report", "Give me a full analyst summary"),
    ]
    for col, (label, q) in zip(qp_cols2, quick_prompts2):
        if col.button(label, use_container_width=True, key=f"qp2_{label}"):
            pending_query = q

    # ---------- Render history
    for entry in st.session_state.analyst_history:
        with st.chat_message("user"):
            st.markdown(entry["q"])
        with st.chat_message("assistant"):
            st.markdown(entry["a"])

    # ---------- Input
    typed = st.chat_input("Ask about WACC, margins, covenants, scenarios...")
    user_query = pending_query or typed
    if user_query:
        with st.chat_message("user"):
            st.markdown(user_query)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = analyst.answer(user_query)
            st.markdown(response)
        st.session_state.analyst_history.append(
            {"q": user_query, "a": response}
        )
        st.rerun()

    if st.session_state.analyst_history:
        if st.button("Clear conversation", use_container_width=False):
            st.session_state.analyst_history = []
            st.rerun()


def tab_scenario_compare():
    st.markdown("### Scenario Comparison")
    st.markdown(
        "<div style='color:#6B7FA3; font-size:12px; margin-bottom:14px;'>"
        "Side-by-side Bull vs Base vs Bear | Time-series overlay | "
        "Financial health radar</div>",
        unsafe_allow_html=True,
    )

    all_scen = run_all_scenarios_cached()

    # Three KPI cards
    cols = st.columns(3)
    scen_colors = {"Bull": "#00FF9D", "Base": "#00F0FF", "Bear": "#FF2D78"}
    for col, sname in zip(cols, ["Bull", "Base", "Bear"]):
        with col:
            r = all_scen[sname]
            d = r["dcf"]
            inc = r["income"]
            rat = r["ratios"]
            sc = scen_colors[sname]
            st.markdown(
                f"<div class='kpi-card' style='border-color:{sc}40;'>"
                f"<div class='kpi-label' style='color:{sc};'>{sname.upper()}</div>"
                f"<div class='kpi-value' style='color:{sc};'>"
                f"INR {d['value_per_share']:,.0f}</div>"
                f"<div class='kpi-sub'>"
                f"EV: INR {d['enterprise_value']:,.0f} Cr<br>"
                f"WACC: {d['wacc']:.2%} | g: {d['terminal_growth']:.2%}<br>"
                f"FY29E EBITDA: {inc.loc['FY29E', 'EBITDA_Margin']:.1%}<br>"
                f"Min DSCR: {rat['DSCR'].min():.2f}x"
                f"</div></div>",
                unsafe_allow_html=True,
            )

    # Overlay + radar
    ov1, ov2 = st.columns([1.2, 1])
    with ov1:
        st.plotly_chart(
            viz.chart_scenario_overlay(all_scen),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_overlay"}},
        )
    with ov2:
        radar_year = st.selectbox(
            "Radar year", options=["FY26E", "FY27E", "FY29E", "FY31E", "FY33E"],
            index=2, key="radar_year",
        )
        st.plotly_chart(
            viz.chart_health_radar(
                {n: r["ratios"] for n, r in all_scen.items()},
                year=radar_year,
            ),
            use_container_width=True,
            config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "scale": 3,
                                             "filename": "JCL_radar"}},
        )

    st.markdown(
        "<div style='color:#6B7FA3; font-size:11px; padding-top:8px;'>"
        "Radar normalises each metric to a 0-10 score against JCL benchmarks "
        "(EBITDA margin 5-25%, DSCR 1.0-4.0x, ROCE 8-25%, Interest Cover "
        "3-15x, Current Ratio 1.0-3.0).</div>",
        unsafe_allow_html=True,
    )


# =============================================================================
# MAIN
# =============================================================================
def main():
    # Try sidebar, but if it fails, we have controls in main area anyway
    try:
        render_sidebar()
    except Exception:
        pass  # Sidebar failed - controls in main area below
    
    # Build current scenario results (cached)
    results = run_model(_assumptions_tuple(st.session_state.assumptions))
    all_scen = run_all_scenarios_cached()

    render_header(results)
    
    # ========== MAIN CONTROL PANEL (instead of sidebar) ==========
    st.markdown("### ⚙️ Control Panel")
    cp_col1, cp_col2, cp_col3 = st.columns(3)
    with cp_col1:
        scn_options = ["Bull", "Base", "Bear", "Custom"]
        try:
            scn_idx = scn_options.index(st.session_state.scenario)
        except ValueError:
            scn_idx = 1
        new_scn = st.selectbox(
            "Scenario",
            scn_options,
            index=scn_idx,
            key="main_scn_picker",
        )
        if new_scn != st.session_state.scenario:
            st.session_state.scenario = new_scn
            if new_scn in SCENARIO_PRESETS:
                st.session_state.assumptions = SCENARIO_PRESETS[new_scn].copy()
            st.rerun()
    
    with cp_col2:
        if st.button("Reset to Base", use_container_width=True):
            st.session_state.scenario = "Base"
            st.session_state.assumptions = SCENARIO_PRESETS["Base"].copy()
            st.rerun()
    
    with cp_col3:
        if st.button("Share URL", use_container_width=True):
            encode_assumptions_to_url(
                st.session_state.assumptions, st.session_state.scenario
            )
            st.toast("URL updated!", icon="*")
    
    # Driver sliders in 3 columns
    a = st.session_state.assumptions
    st.markdown("**Operations**")
    col_ops1, col_ops2 = st.columns(2)
    with col_ops1:
        a["cob2_util_steady"] = st.slider(
            "COB-2 Utilisation", 0.20, 1.00,
            float(a["cob2_util_steady"]), 0.01, format="%.2f",
        )
        a["cogs_pct"] = st.slider(
            "COGS %", 0.70, 0.95,
            float(a["cogs_pct"]), 0.005, format="%.3f",
        )
    with col_ops2:
        a["coke_realization"] = st.slider(
            "Coke Realisation (₹/MT)", 15_000, 50_000,
            int(a["coke_realization"]), 500,
        )
        a["capex_intensity"] = st.slider(
            "Capex Intensity", 0.005, 0.060,
            float(a["capex_intensity"]), 0.005, format="%.3f",
        )
    
    st.markdown("**Financing**")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        a["interest_rate"] = st.slider(
            "Interest Rate", 0.04, 0.20,
            float(a["interest_rate"]), 0.005, format="%.3f",
        )
    with col_fin2:
        a["target_de"] = st.slider(
            "Target D/E", 0.10, 2.50,
            float(a["target_de"]), 0.05, format="%.2f",
        )
    
    st.markdown("**Cost of Capital**")
    col_coc1, col_coc2 = st.columns(2)
    with col_coc1:
        a["unlevered_beta"] = st.slider(
            "Unlevered Beta", 0.40, 2.00,
            float(a["unlevered_beta"]), 0.05, format="%.2f",
        )
        a["rf_rate"] = st.slider(
            "Risk-Free Rate", 0.03, 0.12,
            float(a["rf_rate"]), 0.0025, format="%.4f",
        )
    with col_coc2:
        a["erp"] = st.slider(
            "Equity Risk Premium", 0.04, 0.12,
            float(a["erp"]), 0.0025, format="%.4f",
        )
        a["terminal_growth"] = st.slider(
            "Terminal Growth (g)", -0.01, 0.06,
            float(a["terminal_growth"]), 0.005, format="%.3f",
        )
    
    st.session_state.assumptions = a
    if (st.session_state.scenario in SCENARIO_PRESETS
            and a != SCENARIO_PRESETS[st.session_state.scenario]):
        st.session_state.scenario = "Custom"
    
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    
    render_kpi_matrix(results)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    tabs = st.tabs([
        "Valuation Bridge",
        "3-Statement",
        "Sensitivity & Risk",
        "Monte Carlo",
        "Detailed Tables",
        "Smart Analyst",
        "Scenario Compare",
    ])
    with tabs[0]: tab_valuation_bridge(results)
    with tabs[1]: tab_three_statement(results)
    with tabs[2]: tab_sensitivity(results)
    with tabs[3]: tab_monte_carlo(results)
    with tabs[4]: tab_detailed(results)
    with tabs[5]: tab_smart_analyst(results, all_scen)
    with tabs[6]: tab_scenario_compare()

    # Footer
    st.markdown(
        "<div style='text-align:center; color:#6B7FA3; font-size:10px; "
        "padding-top:24px; border-top:1px solid rgba(0,240,255,0.10); "
        "margin-top:24px;'>"
        "Jindal Coke Ltd. | Illustrative valuation model "
        "| For institutional training only "
        "| Independent verification required for any investment decision."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
