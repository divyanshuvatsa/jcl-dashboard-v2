"""
app.py - Jindal Coke Ltd. Financial Dashboard
Native Streamlit components only. No custom CSS.
"""

from __future__ import annotations
import io
from typing import Dict, Tuple
import numpy as np
import pandas as pd
import streamlit as st

from engine import (
    JCLFinancialEngine, SCENARIO_PRESETS, covenant_stress_sweep,
    generate_insights, generate_text_report, parse_excel_assumptions,
    solve_implied_beta, solve_implied_terminal_growth,
)
import visuals as viz
from analyst import SmartAnalyst
from state import (
    delete_snapshot, encode_assumptions_to_url, load_snapshot,
    restore_assumptions_from_url, save_snapshot,
)

st.set_page_config(
    page_title="JCL Financial Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
        restore_assumptions_from_url()
        st.session_state.state_restored_from_url = True

_init_state()

@st.cache_data(show_spinner=False)
def run_model(assumptions_tuple: Tuple) -> Dict:
    return JCLFinancialEngine(assumptions=dict(assumptions_tuple)).build()

@st.cache_data(show_spinner=False)
def run_tornado(assumptions_tuple: Tuple) -> pd.DataFrame:
    return JCLFinancialEngine(assumptions=dict(assumptions_tuple)).tornado_analysis()

@st.cache_data(show_spinner=False)
def run_monte_carlo(assumptions_tuple: Tuple, n: int = 1000) -> np.ndarray:
    return JCLFinancialEngine(assumptions=dict(assumptions_tuple)).monte_carlo(n=n, seed=42)

@st.cache_data(show_spinner=False)
def run_all_scenarios_cached() -> Dict[str, Dict]:
    return {name: JCLFinancialEngine(assumptions=dict(preset)).build()
            for name, preset in SCENARIO_PRESETS.items()}

def _atuple(a: dict) -> Tuple:
    return tuple(sorted(a.items()))

CHART_CFG = {"displaylogo": False,
             "toImageButtonOptions": {"format": "png", "scale": 3, "filename": "JCL_chart"}}

def render_sidebar():
    st.sidebar.title("JCL Control Deck")
    st.sidebar.caption("Live model | INR Crores")
    st.sidebar.divider()

    scn_options = ["Bull", "Base", "Bear", "Custom"]
    try:
        scn_idx = scn_options.index(st.session_state.scenario)
    except ValueError:
        scn_idx = 1

    new_scn = st.sidebar.selectbox("Scenario", scn_options, index=scn_idx)
    if new_scn != st.session_state.scenario:
        st.session_state.scenario = new_scn
        if new_scn in SCENARIO_PRESETS:
            st.session_state.assumptions = SCENARIO_PRESETS[new_scn].copy()
        st.rerun()

    c1, c2 = st.sidebar.columns(2)
    if c1.button("Reset to Base", use_container_width=True):
        st.session_state.scenario = "Base"
        st.session_state.assumptions = SCENARIO_PRESETS["Base"].copy()
        st.session_state.monte_carlo_evs = None
        st.rerun()
    if c2.button("Share URL", use_container_width=True):
        encode_assumptions_to_url(st.session_state.assumptions, st.session_state.scenario)
        st.toast("URL updated")

    st.sidebar.divider()

    base = SCENARIO_PRESETS["Base"]
    diffs = [(k, float(v), float(base[k])) for k, v in st.session_state.assumptions.items()
             if base.get(k) is not None and abs(float(v) - float(base[k])) > 1e-6]
    if not diffs:
        st.sidebar.success("No changes from Base")
    else:
        st.sidebar.warning(f"{len(diffs)} change(s) from Base")
        for k, v, bv in diffs:
            st.sidebar.caption(f"{k}: {v:.4g} (base {bv:.4g})")

    st.sidebar.divider()
    a = st.session_state.assumptions

    st.sidebar.subheader("Operations")
    a["cob2_util_steady"] = st.sidebar.slider("COB-2 Utilisation", 0.20, 1.00, float(a["cob2_util_steady"]), 0.01, format="%.2f")
    a["coke_realization"] = st.sidebar.slider("Coke Realisation (INR/MT)", 15000, 50000, int(a["coke_realization"]), 500)
    a["cogs_pct"] = st.sidebar.slider("COGS %", 0.70, 0.95, float(a["cogs_pct"]), 0.005, format="%.3f")
    a["capex_intensity"] = st.sidebar.slider("Capex Intensity", 0.005, 0.060, float(a["capex_intensity"]), 0.005, format="%.3f")

    st.sidebar.subheader("Financing")
    a["interest_rate"] = st.sidebar.slider("Interest Rate", 0.04, 0.20, float(a["interest_rate"]), 0.005, format="%.3f")
    a["target_de"] = st.sidebar.slider("Target D/E", 0.10, 2.50, float(a["target_de"]), 0.05, format="%.2f")

    st.sidebar.subheader("Cost of Capital")
    a["unlevered_beta"] = st.sidebar.slider("Unlevered Beta", 0.40, 2.00, float(a["unlevered_beta"]), 0.05, format="%.2f")
    a["rf_rate"] = st.sidebar.slider("Risk-Free Rate", 0.03, 0.12, float(a["rf_rate"]), 0.0025, format="%.4f")
    a["erp"] = st.sidebar.slider("Equity Risk Premium", 0.04, 0.12, float(a["erp"]), 0.0025, format="%.4f")
    a["terminal_growth"] = st.sidebar.slider("Terminal Growth (g)", -0.01, 0.06, float(a["terminal_growth"]), 0.005, format="%.3f")

    st.session_state.assumptions = a
    if st.session_state.scenario in SCENARIO_PRESETS and a != SCENARIO_PRESETS[st.session_state.scenario]:
        st.session_state.scenario = "Custom"

    st.sidebar.divider()
    st.sidebar.subheader("Saved Snapshots")
    snap_name = st.sidebar.text_input("Slot name", placeholder="e.g. Bear+Refi")
    if st.sidebar.button("Save Snapshot", use_container_width=True):
        actual = save_snapshot(snap_name, st.session_state.assumptions)
        st.toast(f"Saved as {actual}")
        st.rerun()
    for name in list(st.session_state.saved_slots.keys()):
        sc1, sc2, sc3 = st.sidebar.columns([3, 1, 1])
        sc1.caption(name)
        if sc2.button("Load", key=f"load_{name}"):
            load_snapshot(name)
            st.rerun()
        if sc3.button("X", key=f"del_{name}"):
            delete_snapshot(name)
            st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Sync from Excel")
    uploaded = st.sidebar.file_uploader("Upload JCL Excel", type=["xlsx"])
    if uploaded:
        parsed = parse_excel_assumptions(uploaded)
        if parsed:
            for k, v in parsed.items():
                st.session_state.assumptions[k] = float(v)
            st.session_state.scenario = "Custom"
            st.sidebar.success(f"Pulled {len(parsed)} assumptions")
            st.rerun()
        else:
            st.sidebar.error("Could not parse Scenario Engine sheet")


def render_header(results: Dict):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("Jindal Coke Ltd.")
        st.caption("Financial Dashboard | FY24A - FY33E | INR Crores")
    with c2:
        st.metric("Active Scenario", st.session_state.scenario)

    for ins in generate_insights(results):
        if ins["level"] == "good":
            st.success(f"[{ins['icon']}] {ins['text']}")
        elif ins["level"] in ("caution", "warning"):
            st.warning(f"[{ins['icon']}] {ins['text']}")
        else:
            st.error(f"[{ins['icon']}] {ins['text']}")


def render_kpi_matrix(results: Dict):
    dcf, inc, rat = results["dcf"], results["income"], results["ratios"]
    st.subheader("Key Metrics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Value / Share", f"INR {dcf['value_per_share']:,.0f}", f"EV: INR {dcf['enterprise_value']:,.0f} Cr")
    c2.metric("WACC", f"{dcf['wacc']:.2%}", f"g: {dcf['terminal_growth']:.2%}")
    c3.metric("FY29E EBITDA Margin", f"{inc.loc['FY29E', 'EBITDA_Margin']:.1%}")
    c4.metric("Min DSCR", f"{rat['DSCR'].min():.2f}x", f"{rat['DSCR'].idxmin()} (floor 1.20x)")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("% EV from Terminal", f"{dcf['pct_ev_terminal']:.1%}")
    c6.metric("Peak ND/EBITDA", f"{rat['Net_Debt_EBITDA'].max():.2f}x")
    c7.metric("Net Debt FY29E", f"INR {rat.loc['FY29E', 'Net_Debt']:,.0f} Cr")
    c8.metric("FY29E ROCE", f"{rat.loc['FY29E', 'ROCE']:.1%}")


def tab_valuation_bridge(results: Dict):
    st.subheader("Valuation Bridge & DCF Composition")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(viz.chart_valuation_bridge(results["dcf"]), use_container_width=True, config=CHART_CFG)
    with c2:
        st.plotly_chart(viz.chart_dcf_components(results["dcf"]), use_container_width=True, config=CHART_CFG)
    pct_mode = st.checkbox("Show YoY Revenue Growth (%)", value=False)
    st.plotly_chart(viz.chart_revenue_ebitda_trend(results["income"], pct_mode=pct_mode), use_container_width=True, config=CHART_CFG)

    st.divider()
    st.subheader("Reverse DCF Solver")
    rc1, rc2 = st.columns(2)
    with rc1:
        st.markdown("**Solve for Implied Beta**")
        target_b = st.number_input("Target VPS (INR)", 100.0, 2000.0, 600.0, 10.0, key="tb")
        if st.button("Solve Beta", use_container_width=True):
            res = solve_implied_beta(st.session_state.assumptions, target_b)
            st.session_state.implied_beta_result = res
        if st.session_state.implied_beta_result:
            r = st.session_state.implied_beta_result
            st.metric("Implied Unlevered Beta", f"{r['beta']:.3f}", f"WACC: {r['implied_wacc']:.2%}")
        else:
            st.caption("Target must be in achievable range [INR 200–900]")
    with rc2:
        st.markdown("**Solve for Implied Terminal Growth**")
        target_g = st.number_input("Target VPS (INR)", 100.0, 2000.0, 600.0, 10.0, key="tg")
        if st.button("Solve g", use_container_width=True):
            res = solve_implied_terminal_growth(st.session_state.assumptions, target_g)
            st.session_state.implied_g_result = res
        if st.session_state.implied_g_result:
            r = st.session_state.implied_g_result
            st.metric("Implied Terminal Growth", f"{r['terminal_growth']:.2%}", f"Achieved: INR {r['achieved_vps']:,.0f}")
        else:
            st.caption("Target must be in achievable range.")


def tab_three_statement(results: Dict):
    st.subheader("Revenue, Cash Flow & Debt Profile")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(viz.chart_revenue_mix(results["revenue"]), use_container_width=True, config=CHART_CFG)
    with c2:
        st.plotly_chart(viz.chart_debt_coverage(results["ratios"], results["balance"]), use_container_width=True, config=CHART_CFG)
    st.plotly_chart(viz.chart_cashflow_build(results["cashflow"]), use_container_width=True, config=CHART_CFG)


def tab_sensitivity(results: Dict):
    st.subheader("Sensitivity & Risk")
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.plotly_chart(viz.chart_wacc_sensitivity(results["sensitivity"], results["dcf"]["wacc"], results["dcf"]["terminal_growth"]), use_container_width=True, config=CHART_CFG)
    with c2:
        with st.spinner("Computing tornado..."):
            tornado = run_tornado(_atuple(st.session_state.assumptions))
        st.plotly_chart(viz.chart_tornado(tornado), use_container_width=True, config=CHART_CFG)

    st.divider()
    st.subheader("Covenant Stress Tester")
    sc1, sc2, sc3 = st.columns([2, 1, 1])
    with sc1:
        driver = st.selectbox("Driver to stress",
                              ["interest_rate", "cogs_pct", "cob2_util_steady"],
                              format_func=lambda k: {"interest_rate": "Interest Rate",
                                                     "cogs_pct": "COGS %",
                                                     "cob2_util_steady": "COB-2 Utilisation"}[k])
    with sc2:
        floor = st.number_input("Covenant floor (DSCR)", 1.0, 2.5, 1.20, 0.05)
    with sc3:
        st.write("")
        if st.button("Run Stress", use_container_width=True):
            with st.spinner("Sweeping..."):
                st.session_state.stress_sweep_result = covenant_stress_sweep(
                    st.session_state.assumptions, driver_key=driver, covenant_floor=floor, steps=30)

    sweep = st.session_state.stress_sweep_result
    if sweep and sweep["driver_key"] == driver:
        st.plotly_chart(viz.chart_covenant_stress(sweep), use_container_width=True, config=CHART_CFG)
        if sweep["breach_value"] is not None:
            st.error(f"Breach at {sweep['breach_value']:.2%} — DSCR drops below {floor:.2f}x in {sweep['breach_year']}")
        else:
            st.success(f"No breach — DSCR stays above {floor:.2f}x across entire range")
    else:
        st.info("Select a driver and click Run Stress.")


def tab_monte_carlo(results: Dict):
    st.subheader("Monte Carlo Simulation")
    mc1, mc2 = st.columns([1, 3])
    with mc1:
        n_sims = st.select_slider("Simulations", [200, 500, 1000, 2000, 5000], value=1000)
        if st.button("Run Simulation", use_container_width=True):
            with st.spinner(f"Running {n_sims} simulations..."):
                st.session_state.monte_carlo_evs = run_monte_carlo(_atuple(st.session_state.assumptions), n_sims)
    with mc2:
        evs = st.session_state.monte_carlo_evs
        if evs is not None and len(evs) > 0:
            st.plotly_chart(viz.chart_monte_carlo(evs, results["dcf"]["enterprise_value"]), use_container_width=True, config=CHART_CFG)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Mean EV", f"INR {float(np.mean(evs)):,.0f} Cr")
            k2.metric("Std Dev", f"INR {float(np.std(evs)):,.0f} Cr")
            k3.metric("P5 (Downside)", f"INR {float(np.percentile(evs, 5)):,.0f} Cr")
            k4.metric("P95 (Upside)", f"INR {float(np.percentile(evs, 95)):,.0f} Cr")
        else:
            st.info("Click Run Simulation to generate the EV distribution.")


def tab_detailed(results: Dict):
    st.subheader("Detailed Statements")
    t1, t2, t3, t4 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow", "Ratios"])
    with t1:
        keep = ["Net_Sales", "COGS", "Gross_Profit", "Employee", "SGA",
                "EBITDA", "Depreciation", "EBIT", "Other_Income", "Interest", "PBT", "Tax", "PAT",
                "EBITDA_Margin", "PAT_Margin"]
        st.dataframe(results["income"][keep].T.style.format("{:,.1f}"), use_container_width=True)
    with t2:
        keep = ["Share_Capital", "Reserves_Surplus", "Total_Equity", "LT_Borrowings",
                "ST_Borrowings", "Trade_Payables", "Net_Fixed_Assets", "CWIP",
                "Inventories", "Trade_Receivables", "Cash", "Total_Assets"]
        st.dataframe(results["balance"][keep].T.style.format("{:,.0f}"), use_container_width=True)
    with t3:
        st.dataframe(results["cashflow"].T.style.format("{:,.1f}"), use_container_width=True)
    with t4:
        pct = ["EBITDA_Margin", "PAT_Margin", "ROE", "ROCE", "Gross_Margin"]
        fmt = {c: "{:.2%}" if c in pct else "{:,.2f}" for c in results["ratios"].columns}
        st.dataframe(results["ratios"].T.style.format(fmt), use_container_width=True)

    st.divider()
    st.subheader("Downloads")
    d1, d2 = st.columns(2)
    with d1:
        buf = io.BytesIO()
        try:
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                results["income"].to_excel(writer, sheet_name="Income")
                results["balance"].to_excel(writer, sheet_name="Balance")
                results["cashflow"].to_excel(writer, sheet_name="CashFlow")
                results["ratios"].to_excel(writer, sheet_name="Ratios")
                results["revenue"].to_excel(writer, sheet_name="Revenue")
                results["sensitivity"].to_excel(writer, sheet_name="WACC_x_g")
                pd.DataFrame([results["assumptions"]]).T.to_excel(writer, sheet_name="Assumptions")
                if "fcff" in results["dcf"]:
                    results["dcf"]["fcff"].to_excel(writer, sheet_name="FCFF_Build")
            buf.seek(0)
            st.download_button("Download Excel Workbook", data=buf,
                               file_name=f"JCL_Model_{st.session_state.scenario}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        except Exception as e:
            st.error(f"Excel error: {e}")
    with d2:
        report = generate_text_report(results, st.session_state.assumptions, st.session_state.scenario)
        st.download_button("Download Analyst Report (.md)", data=report,
                           file_name=f"JCL_Report_{st.session_state.scenario}.md",
                           mime="text/markdown", use_container_width=True)


def tab_smart_analyst(results: Dict, all_scen: Dict):
    st.subheader("Smart Analyst")
    st.caption("Ask questions in plain English. Fully offline, no API.")
    analyst = SmartAnalyst(results, st.session_state.assumptions, st.session_state.scenario, all_scen)

    st.markdown("**Quick prompts**")
    cols1 = st.columns(4)
    prompts1 = [("Walk me through WACC", "Walk me through the WACC build"),
                ("Covenant status", "What is the DSCR and covenant status?"),
                ("Top 3 value drivers", "What are the top 3 sensitivity drivers?"),
                ("Scenario comparison", "Compare Bull, Base and Bear scenarios")]
    pending = None
    for col, (label, q) in zip(cols1, prompts1):
        if col.button(label, use_container_width=True, key=f"qp_{label}"):
            pending = q

    cols2 = st.columns(4)
    prompts2 = [("Margin trajectory", "Why are margins moving from FY25 to FY29?"),
                ("Debt schedule", "Walk me through the debt and deleveraging"),
                ("Cash flow build", "Explain the cash flow trajectory"),
                ("Full report", "Give me a full analyst summary")]
    for col, (label, q) in zip(cols2, prompts2):
        if col.button(label, use_container_width=True, key=f"qp2_{label}"):
            pending = q

    st.divider()
    for entry in st.session_state.analyst_history:
        with st.chat_message("user"):
            st.markdown(entry["q"])
        with st.chat_message("assistant"):
            st.markdown(entry["a"])

    typed = st.chat_input("Ask about WACC, margins, covenants, scenarios...")
    user_query = pending or typed
    if user_query:
        with st.chat_message("user"):
            st.markdown(user_query)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = analyst.answer(user_query)
            st.markdown(response)
        st.session_state.analyst_history.append({"q": user_query, "a": response})
        st.rerun()

    if st.session_state.analyst_history:
        if st.button("Clear conversation"):
            st.session_state.analyst_history = []
            st.rerun()


def tab_scenario_compare():
    st.subheader("Scenario Comparison")
    all_scen = run_all_scenarios_cached()
    c1, c2, c3 = st.columns(3)
    for col, sname in zip([c1, c2, c3], ["Bull", "Base", "Bear"]):
        r = all_scen[sname]
        with col:
            st.markdown(f"### {sname}")
            st.metric("Value / Share", f"INR {r['dcf']['value_per_share']:,.0f}")
            st.metric("Enterprise Value", f"INR {r['dcf']['enterprise_value']:,.0f} Cr")
            st.metric("WACC", f"{r['dcf']['wacc']:.2%}")
            st.metric("FY29E EBITDA Margin", f"{r['income'].loc['FY29E', 'EBITDA_Margin']:.1%}")
            st.metric("Min DSCR", f"{r['ratios']['DSCR'].min():.2f}x")
    st.divider()
    ov1, ov2 = st.columns([1.2, 1])
    with ov1:
        st.plotly_chart(viz.chart_scenario_overlay(all_scen), use_container_width=True, config=CHART_CFG)
    with ov2:
        radar_year = st.selectbox("Radar year", ["FY26E", "FY27E", "FY29E", "FY31E", "FY33E"], index=2)
        st.plotly_chart(viz.chart_health_radar({n: r["ratios"] for n, r in all_scen.items()}, year=radar_year),
                        use_container_width=True, config=CHART_CFG)


def main():
    render_sidebar()
    results = run_model(_atuple(st.session_state.assumptions))
    all_scen = run_all_scenarios_cached()
    render_header(results)
    render_kpi_matrix(results)
    st.divider()
    tabs = st.tabs(["Valuation Bridge", "3-Statement", "Sensitivity & Risk",
                    "Monte Carlo", "Detailed Tables", "Smart Analyst", "Scenario Compare"])
    with tabs[0]: tab_valuation_bridge(results)
    with tabs[1]: tab_three_statement(results)
    with tabs[2]: tab_sensitivity(results)
    with tabs[3]: tab_monte_carlo(results)
    with tabs[4]: tab_detailed(results)
    with tabs[5]: tab_smart_analyst(results, all_scen)
    with tabs[6]: tab_scenario_compare()
    st.divider()
    st.caption("Jindal Coke Ltd. | Illustrative valuation model | For institutional training only.")

if __name__ == "__main__":
    main()
