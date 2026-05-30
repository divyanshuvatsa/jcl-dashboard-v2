"""smoke_test.py — exercise every dashboard code path without Streamlit."""
import sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, io

import engine as E
import visuals as viz
from analyst import SmartAnalyst

fails = []
def ok(label):
    print(f"  PASS  {label}")
def fail(label, e):
    fails.append((label, e)); print(f"  FAIL  {label}: {type(e).__name__}: {e}")

# 1) build all three scenarios
results = {}
for sc in ("Base", "Bull", "Bear"):
    try:
        results[sc] = E.JCLFinancialEngine(assumptions=dict(E.SCENARIO_PRESETS[sc])).build()
        ok(f"engine.build [{sc}]")
    except Exception as e:
        fail(f"engine.build [{sc}]", e)

base = results.get("Base")

# 2) a custom what-if (sliders moved off Base)
try:
    custom = dict(E.SCENARIO_PRESETS["Base"])
    custom.update(coke_realization=29500, cogs_pct=0.80, target_de=0.65,
                  interest_rate=0.095, terminal_growth=0.015, cob2_util_steady=0.83)
    E.JCLFinancialEngine(assumptions=custom).build()
    ok("engine.build [custom what-if]")
except Exception as e:
    fail("engine.build [custom what-if]", e)

# 3) tornado / monte carlo / stress sweep / solvers
try:
    eng = E.JCLFinancialEngine(assumptions=dict(E.SCENARIO_PRESETS["Base"]))
    tornado = eng.tornado_analysis(); assert len(tornado) > 0; ok("tornado_analysis")
except Exception as e:
    fail("tornado_analysis", e); tornado = pd.DataFrame()
try:
    evs = E.JCLFinancialEngine(assumptions=dict(E.SCENARIO_PRESETS["Base"])).monte_carlo(300)
    assert len(evs) > 0; ok("monte_carlo")
except Exception as e:
    fail("monte_carlo", e); evs = np.array([2000.0, 2100.0, 2200.0])
try:
    sweep = E.covenant_stress_sweep(dict(E.SCENARIO_PRESETS["Base"]), "interest_rate")
    ok(f"covenant_stress_sweep (breach={sweep['breach_value']})")
except Exception as e:
    fail("covenant_stress_sweep", e); sweep = {}
try:
    r = E.solve_implied_beta(dict(E.SCENARIO_PRESETS["Base"]), 600.0); ok(f"solve_implied_beta -> {r}")
except Exception as e:
    fail("solve_implied_beta", e)
try:
    r = E.solve_implied_terminal_growth(dict(E.SCENARIO_PRESETS["Base"]), 600.0); ok(f"solve_implied_terminal_growth -> {r}")
except Exception as e:
    fail("solve_implied_terminal_growth", e)

# 4) insights + report
try:
    ins = E.generate_insights(base); assert len(ins) > 0; ok(f"generate_insights ({len(ins)} cards)")
except Exception as e:
    fail("generate_insights", e)
try:
    rep = E.generate_text_report(base, dict(E.SCENARIO_PRESETS["Base"]), "Base"); assert len(rep) > 200; ok("generate_text_report")
except Exception as e:
    fail("generate_text_report", e)

# 5) every visuals.py chart
charts = [
    ("chart_valuation_bridge", lambda: viz.chart_valuation_bridge(base["dcf"])),
    ("chart_dcf_components", lambda: viz.chart_dcf_components(base["dcf"])),
    ("chart_wacc_sensitivity", lambda: viz.chart_wacc_sensitivity(base["sensitivity"], base["dcf"]["wacc"], base["dcf"]["terminal_growth"])),
    ("chart_tornado", lambda: viz.chart_tornado(tornado)),
    ("chart_monte_carlo", lambda: viz.chart_monte_carlo(evs, base["dcf"]["enterprise_value"])),
    ("chart_revenue_ebitda_trend", lambda: viz.chart_revenue_ebitda_trend(base["income"])),
    ("chart_debt_coverage", lambda: viz.chart_debt_coverage(base["ratios"], base["balance"])),
    ("chart_cashflow_build", lambda: viz.chart_cashflow_build(base["cashflow"])),
    ("chart_revenue_mix", lambda: viz.chart_revenue_mix(base["revenue"])),
    ("chart_covenant_stress", lambda: viz.chart_covenant_stress(sweep) if sweep else None),
    ("chart_health_radar", lambda: viz.chart_health_radar({k: v["ratios"] for k, v in results.items()})),
    ("chart_scenario_overlay", lambda: viz.chart_scenario_overlay(results)),
    ("chart_kpi_sparkline", lambda: viz.chart_kpi_sparkline(list(base["income"]["EBITDA"].values))),
]
for name, fn in charts:
    try:
        fn(); ok(f"visuals.{name}")
    except Exception as e:
        fail(f"visuals.{name}", e)

# 6) SmartAnalyst across all intents
try:
    sa = SmartAnalyst(base, dict(E.SCENARIO_PRESETS["Base"]), "Base", all_scenario_results=results)
    for q in ["help", "what is the wacc?", "covenant / dscr risk", "margins",
              "valuation summary", "revenue drivers", "debt profile", "cash flow",
              "sensitivity to wacc", "compare scenarios", "tax", "capex and depreciation",
              "working capital", "equity structure", "full report"]:
        ans = sa.answer(q); assert isinstance(ans, str) and len(ans) > 0
    ok("SmartAnalyst (15 intents)")
except Exception as e:
    fail("SmartAnalyst", e)

# 7) detailed-tables keep-column slices + Excel export
try:
    keep_inc = ["Net_Sales","COGS","Gross_Profit","Employee","SGA","EBITDA","Depreciation",
                "EBIT","Other_Income","Interest","PBT","Tax","PAT","EBITDA_Margin","PAT_Margin"]
    base["income"][keep_inc].T
    keep_bs = ["Share_Capital","Reserves_Surplus","Total_Equity","LT_Borrowings","ST_Borrowings",
               "Trade_Payables","Net_Fixed_Assets","CWIP","Inventories","Trade_Receivables","Cash","Total_Assets"]
    base["balance"][keep_bs].T
    ok("detailed-table column slices")
except Exception as e:
    fail("detailed-table column slices", e)
try:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        base["income"].to_excel(w, sheet_name="Income")
        base["balance"].to_excel(w, sheet_name="Balance")
        base["cashflow"].to_excel(w, sheet_name="CashFlow")
        base["ratios"].to_excel(w, sheet_name="Ratios")
        base["revenue"].to_excel(w, sheet_name="Revenue")
        base["sensitivity"].to_excel(w, sheet_name="WACC_x_g")
        pd.DataFrame([base["assumptions"]]).T.to_excel(w, sheet_name="Assumptions")
        base["dcf"]["fcff"].to_excel(w, sheet_name="FCFF_Build")
    ok("Excel workbook export")
except Exception as e:
    fail("Excel workbook export", e)

# 8) external loader path + parse_excel_assumptions
try:
    from excel_loader import load_full_model
    m = load_full_model("JCL_Financial_Model_EXP.xlsx")
    viz.chart_valuation_bridge(m["dcf"]); viz.chart_debt_coverage(m["ratios"], m["balance"])
    ok("excel_loader full-model render")
except Exception as e:
    fail("excel_loader full-model render", e)
try:
    with open("JCL_Financial_Model_EXP.xlsx", "rb") as fh:
        pa = E.parse_excel_assumptions(fh)
    assert isinstance(pa, dict) and len(pa) >= 5; ok(f"parse_excel_assumptions ({len(pa)} keys)")
except Exception as e:
    fail("parse_excel_assumptions", e)

print("=" * 60)
if fails:
    print(f"SMOKE TEST FAILED — {len(fails)} failure(s)")
    sys.exit(1)
print("SMOKE TEST PASSED — full dashboard pipeline works end-to-end.")
sys.exit(0)
