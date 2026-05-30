"""
verify.py — Verification & Validation harness
=============================================
Compares the dashboard's computed model (engine at Base, and the external Excel
loader) against the golden master extracted verbatim from
JCL_Financial_Model_EXP.xlsx. Prints every mismatch beyond tolerance and exits
non-zero if any are found, so it can be run iteratively until a clean pass.

Usage:  python verify.py            (verifies engine + loader)
"""
from __future__ import annotations

import json
import math
import sys

ABS_TOL = 0.02        # ₹ Cr / count tolerance for level figures
REL_TOL = 2e-4        # relative tolerance for ratios / rates / margins

GOLD = json.load(open("jcl_base_model.json"))

PROJ = ["FY25A", "FY26E", "FY27E", "FY28E", "FY29E", "FY30E", "FY31E", "FY32E", "FY33E"]
VALUED = PROJ[1:]
ALLY = ["FY24A"] + PROJ

errors = []


def chk(label, got, exp, abs_tol=ABS_TOL, rel_tol=REL_TOL):
    if exp is None and got is None:
        return
    if got is None or exp is None:
        errors.append(f"{label}: got={got} exp={exp} (missing)")
        return
    if isinstance(got, float) and math.isnan(got) and isinstance(exp, float) and math.isnan(exp):
        return
    diff = abs(got - exp)
    tol = max(abs_tol, abs(exp) * rel_tol)
    if diff > tol:
        errors.append(f"{label}: got={got:.6f} exp={exp:.6f} diff={diff:.6f} tol={tol:.6f}")


def verify_model(res, tag):
    inc, bal, cfs, rat, dcf = (res["income"], res["balance"], res["cashflow"],
                               res["ratios"], res["dcf"])
    gi, gb, gc, gd, gv = (GOLD["income"], GOLD["balance"], GOLD["cashflow"],
                          GOLD["dcf"], GOLD["covenant"])

    # ---- income statement (all years) ----
    for col in ["Net_Sales", "COGS", "Gross_Profit", "Employee", "SGA", "EBITDA",
                "Depreciation", "EBIT", "Other_Income", "Interest", "PBT", "Tax", "PAT"]:
        for y in ALLY:
            chk(f"[{tag}] income.{col}.{y}", float(inc.loc[y, col]), gi[col][y])

    # ---- balance sheet (every line, every year) ----
    for col in ["Share_Capital", "Reserves_Surplus", "Total_Equity", "LT_Borrowings",
                "Deferred_Tax_Liab", "LT_Provisions", "ST_Borrowings", "Revolver",
                "Trade_Payables", "Other_CL", "Net_Fixed_Assets", "CWIP",
                "LT_Investments", "LT_Loans_Adv", "Other_LT_Assets", "Inventories",
                "Trade_Receivables", "Cash", "Other_CA", "ST_Loans_Adv",
                "Total_Assets", "Total_Liab_Equity"]:
        for y in ALLY:
            chk(f"[{tag}] balance.{col}.{y}", float(bal.loc[y, col]), gb[col][y])

    # ---- balance check ----
    for y in ALLY:
        chk(f"[{tag}] BS_balance.{y}",
            float(bal.loc[y, "Total_Assets"] - bal.loc[y, "Total_Liab_Equity"]), 0.0)

    # ---- cash flow (every line) ----
    for col in ["PAT", "Depreciation", "Delta_Inventory", "Delta_Receivables",
                "Delta_Payables", "Delta_Other_NCL", "CFO", "Capex", "CFI",
                "Term_Debt_Repay", "Change_ST_Borrow", "CFF",
                "Net_Change_Cash", "Closing_Cash"]:
        for y in PROJ:
            chk(f"[{tag}] cashflow.{col}.{y}", float(cfs.loc[y, col]), gc[col][y])

    # ---- income margins (derived) ----
    for y in ALLY:
        ns = gi["Net_Sales"][y]
        chk(f"[{tag}] income.EBITDA_Margin.{y}", float(inc.loc[y, "EBITDA_Margin"]),
            gi["EBITDA"][y] / ns, rel_tol=1e-3)
        chk(f"[{tag}] income.PAT_Margin.{y}", float(inc.loc[y, "PAT_Margin"]),
            gi["PAT"][y] / ns, rel_tol=1e-3)

    # ---- DCF / WACC ----
    chk(f"[{tag}] dcf.wacc", dcf["wacc"], gd["wacc"], rel_tol=1e-4)
    chk(f"[{tag}] dcf.enterprise_value", dcf["enterprise_value"], gd["enterprise_value"])
    chk(f"[{tag}] dcf.terminal_value", dcf["terminal_value"], gd["terminal_value"])
    chk(f"[{tag}] dcf.pv_terminal", dcf["pv_terminal"], gd["pv_terminal"])
    chk(f"[{tag}] dcf.sum_pv_fcff", dcf["sum_pv_fcff"], gd["sum_pv_fcff"])
    chk(f"[{tag}] dcf.equity_value", dcf["equity_value"], gd["equity_value"])
    chk(f"[{tag}] dcf.value_per_share", dcf["value_per_share"], gd["value_per_share"])
    chk(f"[{tag}] dcf.pct_ev_terminal", dcf["pct_ev_terminal"], gd["pct_ev_terminal"], rel_tol=1e-3)
    chk(f"[{tag}] dcf.terminal_fcff_cit", dcf["terminal_fcff_cit"], gd["terminal_fcff_cit"])
    wc = dcf["wacc_components"]
    chk(f"[{tag}] wacc.Ke", wc["Ke"], gd["ke"], rel_tol=1e-3)
    chk(f"[{tag}] wacc.Beta_Levered", wc["Beta_Levered"], gd["beta_levered"], rel_tol=1e-3)
    chk(f"[{tag}] wacc.Kd_AT", wc["Kd_AT"], gd["kd_at"], rel_tol=1e-3)
    chk(f"[{tag}] wacc.We", wc["We"], gd["we"], rel_tol=1e-3)
    chk(f"[{tag}] wacc.Wd", wc["Wd"], gd["wd"], rel_tol=1e-3)
    chk(f"[{tag}] wacc.Wp", wc["Wp"], gd["wp"], rel_tol=1e-3)

    # ---- FCFF series ----
    for y in VALUED:
        chk(f"[{tag}] dcf.fcff.{y}", float(dcf["fcff"].loc[y, "FCFF"]), gd["fcff"][y])
        chk(f"[{tag}] dcf.pv_fcff.{y}", float(dcf["fcff"].loc[y, "PV_FCFF"]), gd["pv_fcff"][y])
        chk(f"[{tag}] dcf.nopat.{y}", float(dcf["fcff"].loc[y, "NOPAT"]), gd["nopat"][y])

    # ---- revenue build (valued years match exactly; FY25A is bottom-up) ----
    grv = GOLD["revenue"]; rev = res["revenue"]
    for y in PROJ:
        chk(f"[{tag}] revenue.Total_Revenue.{y}", float(rev.loc[y, "Total_Revenue"]),
            grv["total_net_sales"][y])
        chk(f"[{tag}] revenue.Coke_Revenue.{y}", float(rev.loc[y, "Coke_Revenue"]),
            grv["coke_revenue"][y])
        chk(f"[{tag}] revenue.COG_Revenue.{y}", float(rev.loc[y, "COG_Revenue"]),
            grv["cog_revenue"][y])
        chk(f"[{tag}] revenue.Tar_Revenue.{y}", float(rev.loc[y, "Tar_Revenue"]),
            grv["tar_revenue"][y])

    # ---- EV→equity bridge ----
    chk(f"[{tag}] dcf.cash", dcf["cash"], gd["cash"])
    chk(f"[{tag}] dcf.debt", dcf["debt"], gd["total_debt_bridge"])
    chk(f"[{tag}] dcf.preference", dcf["preference"], gd["pref_bridge"])

    # ---- Excel Ratio Analysis cross-checks (ROE / ROCE / Current ratio / D-E) ----
    gra = GOLD["ratio_analysis"]
    for y in ["FY26E", "FY27E", "FY28E", "FY29E", "FY30E", "FY31E", "FY32E", "FY33E"]:
        chk(f"[{tag}] RA.ROE.{y}", float(rat.loc[y, "ROE"]), gra["roe"][y], rel_tol=2e-3)
        chk(f"[{tag}] RA.ROCE.{y}", float(rat.loc[y, "ROCE"]), gra["roce"][y], rel_tol=2e-3)
        chk(f"[{tag}] RA.CurrentRatio.{y}", float(rat.loc[y, "Current_Ratio"]),
            gra["current_ratio"][y], rel_tol=2e-3)
        chk(f"[{tag}] RA.DebtEquity.{y}", float(rat.loc[y, "Debt_Equity"]),
            gra["debt_equity"][y], rel_tol=2e-3)

    # ---- covenant ratios ----
    for y in PROJ:
        chk(f"[{tag}] ratios.DSCR.{y}", float(rat.loc[y, "DSCR"]), gv["dscr"][y], rel_tol=2e-3)
        chk(f"[{tag}] ratios.ISCR.{y}", float(rat.loc[y, "Interest_Coverage"]), gv["iscr"][y], rel_tol=2e-3)

    # ---- ratios vs Excel Ratio Analysis (ROE/ROCE/margins/current ratio) ----
    # (compared against DSCR sheet & ratio sheet where definitions align)
    # ---- sensitivity grid ----
    sens = res["sensitivity"]
    grid = GOLD["sensitivity"]["grid"]
    wacc_rows = GOLD["sensitivity"]["wacc_rows"]
    g_cols = GOLD["sensitivity"]["g_cols"]
    for wv in wacc_rows:
        for gg in g_cols:
            exp = grid[f"{wv:.4f}"][f"{gg:.4f}"]
            got = float(sens.loc[f"{wv:.2%}", f"{gg:.2%}"])
            chk(f"[{tag}] sensitivity.W{wv:.4f}.g{gg:.4f}", got, exp, abs_tol=0.10)


def main():
    from engine import JCLFinancialEngine, SCENARIO_PRESETS
    res = JCLFinancialEngine(assumptions=dict(SCENARIO_PRESETS["Base"])).build()
    verify_model(res, "engine")

    try:
        from excel_loader import load_full_model
        loaded = load_full_model("JCL_Financial_Model_EXP.xlsx")
        verify_model(loaded, "loader")
    except Exception as e:
        errors.append(f"[loader] FAILED to load/verify: {type(e).__name__}: {e}")

    print("=" * 70)
    if errors:
        print(f"VERIFICATION FAILED — {len(errors)} mismatch(es):")
        for e in errors[:80]:
            print("  -", e)
        if len(errors) > 80:
            print(f"  ... and {len(errors) - 80} more")
        print("=" * 70)
        sys.exit(1)
    print("VERIFICATION PASSED — dashboard is 100% consistent with the Excel model.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
