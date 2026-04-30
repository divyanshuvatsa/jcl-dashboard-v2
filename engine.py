"""
engine.py — Jindal Coke Ltd. Financial Engine
==============================================
Class-based 3-statement + DCF + WACC engine. Pure Python/Pandas; no Streamlit
imports. All currency in INR Crores. Calibrated to JCL_Financial_Model_EXP.xlsx.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Dict, List, Optional, Tuple

import math
import numpy as np
import pandas as pd

# =============================================================================
# CONSTANTS - calibrated to JCL_Financial_Model_EXP.xlsx
# =============================================================================

PROJECTION_YEARS: List[str] = [
    "FY25A", "FY26E", "FY27E", "FY28E", "FY29E",
    "FY30E", "FY31E", "FY32E", "FY33E",
]
HISTORICAL_YEAR = "FY24A"
ALL_YEARS = [HISTORICAL_YEAR] + PROJECTION_YEARS

FY24_OPENING = {
    "share_capital":            141.69,
    "reserves_surplus":         699.34,
    "lt_borrowings":            324.01,
    "deferred_tax_liab":         66.16,
    "lt_provisions":              2.27,
    "st_borrowings":              0.81,
    "trade_payables":           620.08,
    "other_cl":                  21.20,
    "net_fixed_assets":         461.01,
    "cwip":                     433.04,
    "lt_investments":             0.53,
    "lt_loans_advances":        268.43,
    "other_lt_assets":            1.25,
    "inventories":              340.02,
    "trade_receivables":         76.88,
    "cash":                      74.80,
    "other_ca":                  28.47,
    "st_loans_adv":             191.13,
}

COB1_CAPACITY_MT = 429_000
COB2_CAPACITY_MT = 350_000
COB1_UTIL_FLAT = 0.911766
COB2_UTIL_PROFILE = {
    "FY25A": 0.35, "FY26E": 0.70, "FY27E": 0.80,
    "FY28E": 0.80, "FY29E": 0.80, "FY30E": 0.80,
    "FY31E": 0.80, "FY32E": 0.80, "FY33E": 0.80,
}

COG_YIELD_PER_MT_COKE = 222
COG_PRICE_INR_NM3     = 19.44
COAL_TAR_YIELD_PCT    = 0.0378
COAL_TAR_PRICE_INR_MT = 37_000

SHARES_OUTSTANDING_CR = 3.243
PREF_SHARE_CAPITAL    = 109.26
DEPRECIATION_RATE     = 0.05
INTEREST_RATE_DEBT    = 0.09
EFFECTIVE_TAX_RATE    = 0.2517
MAT_TAX_RATE          = 0.17472
DIV_FLOOR             = 10.93
DIV_PAYOUT_VAR        = 0.30
MAINT_CAPEX_RATE      = 0.025

TERM_DEBT_REPAYMENT = {
    "FY25A": -38.94, "FY26E": 146.23, "FY27E": -34.40, "FY28E": -45.10,
    "FY29E": -45.30, "FY30E": -45.00, "FY31E": -45.00, "FY32E": -45.00,
    "FY33E": -45.00,
}
OPENING_TERM_DEBT_FY25 = 324.01

DEBTOR_DAYS_BASE   = {"FY25A": 35, "FY26E": 34, "FY27E": 33, "FY28E": 32,
                      "FY29E": 31, "FY30E": 31, "FY31E": 31, "FY32E": 31, "FY33E": 31}
INVENTORY_DAYS_BASE = {"FY25A": 45, "FY26E": 43, "FY27E": 41, "FY28E": 40,
                       "FY29E": 40, "FY30E": 40, "FY31E": 40, "FY32E": 40, "FY33E": 40}
PAYABLE_DAYS_BASE   = {y: 40 for y in PROJECTION_YEARS}

OTHER_INCOME_PROFILE = {"FY25A": 18.7, "FY26E": 27.08,
                        "FY27E": 0, "FY28E": 0, "FY29E": 0,
                        "FY30E": 0, "FY31E": 0, "FY32E": 0, "FY33E": 0}
CDQ_SAVING_PROFILE   = {"FY25A": 19.95, "FY26E": 39.9, "FY27E": 45.6,
                        "FY28E": 45.6, "FY29E": 45.6, "FY30E": 45.6,
                        "FY31E": 45.6, "FY32E": 45.6, "FY33E": 45.6}

COGS_PCT_BASE = {"FY25A": 0.82, "FY26E": 0.79, "FY27E": 0.81,
                 "FY28E": 0.808, "FY29E": 0.806, "FY30E": 0.806,
                 "FY31E": 0.806, "FY32E": 0.806, "FY33E": 0.806}

DCF_DEFAULTS = {
    "risk_free_rate":   0.07,
    "equity_risk_prem": 0.0725,
    "unlevered_beta":   0.85,
    "marginal_tax":     0.2517,
    "target_de":        0.82,
    "cost_of_pref":     0.09,
    "pre_tax_kd":       0.09,
    "terminal_growth":  0.0,
}


# =============================================================================
# SCENARIO PRESETS
# =============================================================================

SCENARIO_PRESETS: Dict[str, Dict] = {
    "Base": {
        "cob2_util_steady": 0.80, "coke_realization": 27_000, "cogs_pct": 0.82,
        "interest_rate": 0.09, "target_de": 0.82, "unlevered_beta": 0.85,
        "terminal_growth": 0.00, "capex_intensity": 0.025,
        "rf_rate": 0.07, "erp": 0.0725,
    },
    "Bull": {
        "cob2_util_steady": 0.85, "coke_realization": 30_000, "cogs_pct": 0.79,
        "interest_rate": 0.085, "target_de": 0.60, "unlevered_beta": 0.80,
        "terminal_growth": 0.02, "capex_intensity": 0.020,
        "rf_rate": 0.065, "erp": 0.07,
    },
    "Bear": {
        "cob2_util_steady": 0.75, "coke_realization": 24_000, "cogs_pct": 0.85,
        "interest_rate": 0.10, "target_de": 1.00, "unlevered_beta": 0.95,
        "terminal_growth": 0.00, "capex_intensity": 0.030,
        "rf_rate": 0.075, "erp": 0.075,
    },
}


# =============================================================================
# THE ENGINE
# =============================================================================

@dataclass
class JCLFinancialEngine:
    """3-statement + DCF + WACC engine for Jindal Coke Ltd."""
    assumptions: Dict = field(default_factory=lambda: dict(SCENARIO_PRESETS["Base"]))

    def build(self) -> Dict:
        revenue_df    = self._build_revenue()
        income_df     = self._build_income_statement(revenue_df)
        bs_df, cfs_df = self._build_balance_sheet_and_cashflow(income_df)
        ratios_df     = self._build_ratios(income_df, bs_df, cfs_df)
        dcf_results   = self._build_dcf(income_df, cfs_df)
        sensitivity   = self._build_sensitivity_grid(income_df, cfs_df)
        return {
            "revenue":     revenue_df,
            "income":      income_df,
            "balance":     bs_df,
            "cashflow":    cfs_df,
            "ratios":      ratios_df,
            "dcf":         dcf_results,
            "sensitivity": sensitivity,
            "assumptions": self.assumptions.copy(),
        }

    def _build_revenue(self) -> pd.DataFrame:
        a = self.assumptions
        cob2_util_steady = a["cob2_util_steady"]
        cob2_util = {
            "FY25A": min(0.50, cob2_util_steady * 0.4375),
            "FY26E": min(0.85, cob2_util_steady * 0.875),
            "FY27E": cob2_util_steady,
            "FY28E": cob2_util_steady, "FY29E": cob2_util_steady,
            "FY30E": cob2_util_steady, "FY31E": cob2_util_steady,
            "FY32E": cob2_util_steady, "FY33E": cob2_util_steady,
        }
        rows: List[Dict] = []
        for y in PROJECTION_YEARS:
            cob1_prod  = COB1_CAPACITY_MT * COB1_UTIL_FLAT
            cob2_prod  = COB2_CAPACITY_MT * cob2_util[y]
            total_coke = cob1_prod + cob2_prod
            coke_rev   = total_coke * a["coke_realization"] / 1e7
            cog_prod   = total_coke * COG_YIELD_PER_MT_COKE
            cog_rev    = cog_prod * COG_PRICE_INR_NM3 / 1e7
            tar_prod   = total_coke * COAL_TAR_YIELD_PCT
            tar_rev    = tar_prod * COAL_TAR_PRICE_INR_MT / 1e7
            rows.append({
                "Year": y, "COB1_Production": cob1_prod, "COB2_Production": cob2_prod,
                "Total_Coke": total_coke, "Coke_Revenue": coke_rev,
                "COG_Revenue": cog_rev, "Tar_Revenue": tar_rev,
                "Total_Revenue": coke_rev + cog_rev + tar_rev,
                "Utilization": total_coke / (COB1_CAPACITY_MT + COB2_CAPACITY_MT),
            })
        return pd.DataFrame(rows).set_index("Year")

    def _build_income_statement(self, revenue_df: pd.DataFrame) -> pd.DataFrame:
        a = self.assumptions
        cogs_slider = a["cogs_pct"]
        cogs_profile = {
            y: COGS_PCT_BASE[y] + (cogs_slider - COGS_PCT_BASE["FY25A"])
            for y in PROJECTION_YEARS
        }
        rows = []
        rows.append({
            "Year": HISTORICAL_YEAR, "Net_Sales": 1572.80, "COGS": 1336.52,
            "Gross_Profit": 236.28, "Employee": 14.62, "SGA": 58.86,
            "EBITDA": 162.80, "Depreciation": 21.11, "EBIT": 141.69,
            "Other_Income": 30.03, "Interest": 39.86, "PBT": 131.86,
            "Tax": 35.97, "PAT": 95.89,
        })
        opening_gross = FY24_OPENING["net_fixed_assets"] + FY24_OPENING["cwip"]
        prior_term_debt = OPENING_TERM_DEBT_FY25

        for y in PROJECTION_YEARS:
            sales = revenue_df.loc[y, "Total_Revenue"]
            cdq   = CDQ_SAVING_PROFILE[y]
            cogs  = sales * cogs_profile[y] - cdq
            gp    = sales - cogs
            emp   = sales * 0.0093
            sga   = sales * 0.0374
            ebitda = sales - cogs - emp - sga
            capex = opening_gross * a["capex_intensity"]
            dep   = opening_gross * DEPRECIATION_RATE
            ebit  = ebitda - dep
            other_inc = OTHER_INCOME_PROFILE[y]
            closing_debt = prior_term_debt - TERM_DEBT_REPAYMENT[y]
            avg_debt = (prior_term_debt + closing_debt) / 2
            interest = avg_debt * a["interest_rate"]
            pbt = ebit + other_inc - interest
            tax = max(pbt, 0) * EFFECTIVE_TAX_RATE
            pat = pbt - tax
            rows.append({
                "Year": y, "Net_Sales": sales, "COGS": cogs, "Gross_Profit": gp,
                "Employee": emp, "SGA": sga, "EBITDA": ebitda,
                "Depreciation": dep, "EBIT": ebit, "Other_Income": other_inc,
                "Interest": interest, "PBT": pbt, "Tax": tax, "PAT": pat,
                "Capex": capex, "Opening_Gross_Block": opening_gross,
                "Closing_Term_Debt": closing_debt,
            })
            opening_gross   = opening_gross + capex
            prior_term_debt = closing_debt

        df = pd.DataFrame(rows).set_index("Year")
        df["EBITDA_Margin"] = df["EBITDA"] / df["Net_Sales"]
        df["PAT_Margin"]    = df["PAT"]    / df["Net_Sales"]
        df["Gross_Margin"]  = df["Gross_Profit"] / df["Net_Sales"]
        return df

    def _build_balance_sheet_and_cashflow(
        self, income_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        bs_rows, cfs_rows = [], []
        retained        = FY24_OPENING["reserves_surplus"]
        share_capital   = FY24_OPENING["share_capital"]
        nfa             = FY24_OPENING["net_fixed_assets"]
        cwip            = FY24_OPENING["cwip"]
        cash            = FY24_OPENING["cash"]
        prior_inv       = FY24_OPENING["inventories"]
        prior_recv      = FY24_OPENING["trade_receivables"]
        prior_pay       = FY24_OPENING["trade_payables"]
        prior_dtl       = FY24_OPENING["deferred_tax_liab"]

        bs_rows.append({
            "Year": HISTORICAL_YEAR, "Share_Capital": share_capital,
            "Reserves_Surplus": retained, "Total_Equity": share_capital + retained,
            "LT_Borrowings": FY24_OPENING["lt_borrowings"],
            "ST_Borrowings": FY24_OPENING["st_borrowings"],
            "Trade_Payables": prior_pay, "Other_CL": FY24_OPENING["other_cl"],
            "Net_Fixed_Assets": nfa, "CWIP": cwip,
            "Inventories": prior_inv, "Trade_Receivables": prior_recv,
            "Cash": cash, "Total_Assets": 1875.56, "Total_Liab_Equity": 1875.56,
        })

        for y in PROJECTION_YEARS:
            r = income_df.loc[y]
            sales = r["Net_Sales"]; cogs = r["COGS"]; pat = r["PAT"]
            dep = r["Depreciation"]; capex = r["Capex"]
            inv = (cogs / 365) * INVENTORY_DAYS_BASE[y]
            ar  = (sales / 365) * DEBTOR_DAYS_BASE[y]
            ap  = (cogs / 365) * PAYABLE_DAYS_BASE[y]
            if y == "FY26E":
                nfa = nfa + cwip + capex - dep
                cwip = 0.0
            else:
                nfa = nfa + capex - dep
            term_debt = r["Closing_Term_Debt"]
            dividend = DIV_FLOOR + max(pat, 0) * DIV_PAYOUT_VAR
            retained = retained + pat - dividend
            d_inv = inv - prior_inv
            d_ar  = ar  - prior_recv
            d_ap  = ap  - prior_pay
            cfo = pat + dep - d_inv - d_ar + d_ap
            cfi = -capex
            cff = -TERM_DEBT_REPAYMENT[y] - dividend
            net_change = cfo + cfi + cff
            cash = cash + net_change

            cfs_rows.append({
                "Year": y, "PAT": pat, "Depreciation": dep,
                "Delta_Inventory": -d_inv, "Delta_Receivables": -d_ar,
                "Delta_Payables": d_ap, "CFO": cfo, "Capex": -capex, "CFI": cfi,
                "Term_Debt_Repay": -TERM_DEBT_REPAYMENT[y], "Dividend": -dividend,
                "CFF": cff, "Net_Change_Cash": net_change, "Closing_Cash": cash,
            })
            total_equity = share_capital + retained
            total_liab   = total_equity + term_debt + ap + prior_dtl
            total_assets = nfa + cwip + inv + ar + cash
            bs_rows.append({
                "Year": y, "Share_Capital": share_capital,
                "Reserves_Surplus": retained, "Total_Equity": total_equity,
                "LT_Borrowings": term_debt, "ST_Borrowings": 0.0,
                "Trade_Payables": ap, "Other_CL": FY24_OPENING["other_cl"],
                "Net_Fixed_Assets": nfa, "CWIP": cwip,
                "Inventories": inv, "Trade_Receivables": ar, "Cash": cash,
                "Total_Assets": total_assets, "Total_Liab_Equity": total_liab,
            })
            prior_inv = inv; prior_recv = ar; prior_pay = ap

        return (pd.DataFrame(bs_rows).set_index("Year"),
                pd.DataFrame(cfs_rows).set_index("Year"))

    def _build_ratios(self, income_df, bs_df, cfs_df) -> pd.DataFrame:
        rows = []
        for y in PROJECTION_YEARS:
            inc, bs = income_df.loc[y], bs_df.loc[y]
            ebitda = inc["EBITDA"]; interest = inc["Interest"]
            principal = max(TERM_DEBT_REPAYMENT[y], 0)
            net_debt = bs["LT_Borrowings"] + bs["ST_Borrowings"] - bs["Cash"]
            dscr = ebitda / (interest + principal) if (interest + principal) > 0 else np.nan
            rows.append({
                "Year": y, "EBITDA_Margin": inc["EBITDA_Margin"],
                "PAT_Margin": inc["PAT_Margin"],
                "ROE": inc["PAT"] / bs["Total_Equity"] if bs["Total_Equity"] else np.nan,
                "ROCE": inc["EBIT"] / (bs["Total_Equity"] + bs["LT_Borrowings"]),
                "Debt_Equity": bs["LT_Borrowings"] / bs["Total_Equity"] if bs["Total_Equity"] else np.nan,
                "Net_Debt": net_debt,
                "Net_Debt_EBITDA": net_debt / ebitda if ebitda else np.nan,
                "DSCR": dscr,
                "Interest_Coverage": ebitda / interest if interest else np.nan,
                "Current_Ratio": (bs["Inventories"] + bs["Trade_Receivables"] + bs["Cash"])
                                 / (bs["Trade_Payables"] + bs["ST_Borrowings"] + bs["Other_CL"]),
                "Total_Debt": bs["LT_Borrowings"] + bs["ST_Borrowings"],
                "Gross_Margin": inc["Gross_Margin"],
            })
        return pd.DataFrame(rows).set_index("Year")

    def _compute_wacc(self) -> Dict:
        a = self.assumptions
        de = a["target_de"]
        beta_l = a["unlevered_beta"] * (1 + (1 - DCF_DEFAULTS["marginal_tax"]) * de)
        ke = a["rf_rate"] + beta_l * a["erp"]
        kd_at = a["interest_rate"] * (1 - DCF_DEFAULTS["marginal_tax"])
        kp = DCF_DEFAULTS["cost_of_pref"]
        equity, debt, pref = 797.6, 545.82, PREF_SHARE_CAPITAL
        total = equity + debt + pref
        we, wd, wp = equity / total, debt / total, pref / total
        wacc = we * ke + wd * kd_at + wp * kp
        return {"WACC": wacc, "Ke": ke, "Kd_AT": kd_at, "Kp": kp,
                "Beta_Levered": beta_l, "We": we, "Wd": wd, "Wp": wp}

    def _build_dcf(self, income_df, cfs_df) -> Dict:
        wacc_pkg = self._compute_wacc()
        wacc = wacc_pkg["WACC"]
        g = self.assumptions["terminal_growth"]
        years_valued = ["FY26E", "FY27E", "FY28E", "FY29E",
                        "FY30E", "FY31E", "FY32E", "FY33E"]
        fcff_rows = []
        for i, y in enumerate(years_valued, start=1):
            inc = income_df.loc[y]
            ebit_taxed = inc["EBIT"] * (1 - MAT_TAX_RATE)
            d_nwc = (cfs_df.loc[y, "Delta_Inventory"]
                     + cfs_df.loc[y, "Delta_Receivables"]
                     + cfs_df.loc[y, "Delta_Payables"])
            fcff = ebit_taxed + inc["Depreciation"] - inc["Capex"] + d_nwc
            disc = (1 + wacc) ** i
            fcff_rows.append({
                "Year": y, "T": i, "EBIT": inc["EBIT"], "NOPAT": ebit_taxed,
                "Depreciation": inc["Depreciation"], "Capex": inc["Capex"],
                "Delta_NWC": d_nwc, "FCFF": fcff,
                "Discount_Factor": disc, "PV_FCFF": fcff / disc,
            })
        fcff_df = pd.DataFrame(fcff_rows).set_index("Year")
        terminal_fcff_cit = (fcff_df.loc["FY33E", "EBIT"] * (1 - EFFECTIVE_TAX_RATE)
                             + fcff_df.loc["FY33E", "Depreciation"]
                             - fcff_df.loc["FY33E", "Capex"])
        terminal_value = (terminal_fcff_cit * (1 + g)) / (wacc - g) if wacc > g else np.nan
        pv_terminal = terminal_value / ((1 + wacc) ** len(years_valued)) if not np.isnan(terminal_value) else np.nan
        sum_pv_fcff = fcff_df["PV_FCFF"].sum()
        ev = sum_pv_fcff + pv_terminal
        cash_fy25, debt_fy25 = 210.18, 545.82
        equity_value = ev + cash_fy25 - debt_fy25 - PREF_SHARE_CAPITAL
        value_per_share = equity_value / SHARES_OUTSTANDING_CR
        pct_ev_terminal = pv_terminal / ev if ev and not np.isnan(ev) else np.nan
        return {
            "wacc_components": wacc_pkg, "fcff": fcff_df,
            "terminal_value": terminal_value, "pv_terminal": pv_terminal,
            "sum_pv_fcff": sum_pv_fcff, "enterprise_value": ev,
            "cash": cash_fy25, "debt": debt_fy25,
            "preference": PREF_SHARE_CAPITAL, "equity_value": equity_value,
            "value_per_share": value_per_share, "pct_ev_terminal": pct_ev_terminal,
            "wacc": wacc, "terminal_growth": g,
        }

    def _build_sensitivity_grid(self, income_df, cfs_df) -> pd.DataFrame:
        wacc_grid = np.arange(0.105, 0.166, 0.01)
        g_grid = np.arange(0.020, 0.051, 0.005)
        years_valued = ["FY26E", "FY27E", "FY28E", "FY29E",
                        "FY30E", "FY31E", "FY32E", "FY33E"]
        fcffs = []
        for y in years_valued:
            inc = income_df.loc[y]
            d_nwc = (cfs_df.loc[y, "Delta_Inventory"]
                     + cfs_df.loc[y, "Delta_Receivables"]
                     + cfs_df.loc[y, "Delta_Payables"])
            fcff = inc["EBIT"] * (1 - MAT_TAX_RATE) + inc["Depreciation"] - inc["Capex"] + d_nwc
            fcffs.append(fcff)
        terminal_fcff_cit = (income_df.loc["FY33E", "EBIT"] * (1 - EFFECTIVE_TAX_RATE)
                             + income_df.loc["FY33E", "Depreciation"]
                             - income_df.loc["FY33E", "Capex"])
        grid = np.zeros((len(wacc_grid), len(g_grid)))
        for i, w in enumerate(wacc_grid):
            for j, g in enumerate(g_grid):
                if w <= g:
                    grid[i, j] = np.nan
                    continue
                pv_fcff = sum(f / ((1 + w) ** (k + 1)) for k, f in enumerate(fcffs))
                tv = terminal_fcff_cit * (1 + g) / (w - g)
                pv_tv = tv / ((1 + w) ** len(fcffs))
                ev = pv_fcff + pv_tv
                eqv = ev + 210.18 - 545.82 - PREF_SHARE_CAPITAL
                grid[i, j] = eqv / SHARES_OUTSTANDING_CR
        return pd.DataFrame(grid, index=[f"{w:.2%}" for w in wacc_grid],
                            columns=[f"{g:.2%}" for g in g_grid])

    def tornado_analysis(self) -> pd.DataFrame:
        baseline = self.build()
        base_vps = baseline["dcf"]["value_per_share"]
        drivers = {
            "Coke Realization": ("coke_realization", 0.10),
            "COGS %": ("cogs_pct", 0.05),
            "Capex Intensity": ("capex_intensity", 0.20),
            "Interest Rate": ("interest_rate", 0.10),
            "Unlevered Beta": ("unlevered_beta", 0.10),
            "Risk-Free Rate": ("rf_rate", 0.10),
            "COB-2 Utilization": ("cob2_util_steady", 0.10),
            "Target D/E": ("target_de", 0.20),
        }
        rows = []
        original = self.assumptions.copy()
        for label, (key, pct) in drivers.items():
            base_val = original[key]
            self.assumptions = original.copy()
            self.assumptions[key] = base_val * (1 + pct)
            up_vps = self.build()["dcf"]["value_per_share"]
            self.assumptions = original.copy()
            self.assumptions[key] = base_val * (1 - pct)
            dn_vps = self.build()["dcf"]["value_per_share"]
            rows.append({"Driver": label, "Down": dn_vps - base_vps,
                         "Up": up_vps - base_vps,
                         "Range": abs(up_vps - dn_vps)})
        self.assumptions = original
        return pd.DataFrame(rows).sort_values("Range", ascending=True)

    def monte_carlo(self, n: int = 1_000, seed: int = 42) -> np.ndarray:
        rng = np.random.default_rng(seed)
        original = self.assumptions.copy()
        evs = np.zeros(n)
        keys_vol = {
            "coke_realization": 0.10, "cogs_pct": 0.05,
            "cob2_util_steady": 0.07, "interest_rate": 0.10,
            "capex_intensity": 0.15,
        }
        for i in range(n):
            self.assumptions = original.copy()
            for k, v in keys_vol.items():
                shock = rng.normal(0, v / 1.96)
                self.assumptions[k] = original[k] * (1 + shock)
            try:
                evs[i] = self.build()["dcf"]["enterprise_value"]
            except Exception:
                evs[i] = np.nan
        self.assumptions = original
        return evs[~np.isnan(evs)]


# =============================================================================
# INSIGHTS ENGINE
# =============================================================================

def generate_insights(results: Dict) -> List[Dict]:
    """Threshold-driven analyst alerts. Returns list of {level, icon, text}."""
    out: List[Dict] = []
    dcf, ratios, income = results["dcf"], results["ratios"], results["income"]

    pct_tv = dcf["pct_ev_terminal"]
    if pct_tv > 0.80:
        out.append({"level": "warning", "icon": "WARN",
                    "text": f"{pct_tv:.0%} of EV from Terminal Value - perpetuity assumptions dominate. Stress-test g and WACC."})
    elif pct_tv > 0.60:
        out.append({"level": "caution", "icon": "INFO",
                    "text": f"{pct_tv:.0%} of EV from Terminal Value - moderately dependent on long-run assumptions."})
    else:
        out.append({"level": "good", "icon": "OK",
                    "text": f"Healthy: only {pct_tv:.0%} of EV from Terminal Value - explicit-period cash flows do most of the lifting."})

    min_dscr = ratios["DSCR"].min()
    min_dscr_year = ratios["DSCR"].idxmin()
    if min_dscr < 1.20:
        out.append({"level": "alert", "icon": "ALERT",
                    "text": f"DSCR drops to {min_dscr:.2f}x in {min_dscr_year} - covenant breach. Review debt-service capacity."})
    elif min_dscr < 1.50:
        out.append({"level": "caution", "icon": "WATCH",
                    "text": f"Min DSCR of {min_dscr:.2f}x in {min_dscr_year} - acceptable but tight."})
    else:
        out.append({"level": "good", "icon": "OK",
                    "text": f"Strong: min DSCR of {min_dscr:.2f}x in {min_dscr_year} - comfortable debt-service coverage."})

    max_nd = ratios["Net_Debt_EBITDA"].max()
    if max_nd > 3.0:
        out.append({"level": "warning", "icon": "WARN",
                    "text": f"Leverage warning: peak Net Debt/EBITDA of {max_nd:.2f}x - above prudent threshold."})
    elif max_nd > 2.0:
        out.append({"level": "caution", "icon": "INFO",
                    "text": f"Moderate leverage: peak Net Debt/EBITDA of {max_nd:.2f}x - manageable."})
    else:
        out.append({"level": "good", "icon": "OK",
                    "text": f"Deleveraged: peak Net Debt/EBITDA of {max_nd:.2f}x - strong balance sheet."})

    wacc = dcf["wacc"]
    if wacc < 0.10:
        out.append({"level": "warning", "icon": "WARN",
                    "text": f"Low WACC: {wacc:.2%} - verify capital-structure assumptions; appears aggressive."})
    elif wacc > 0.16:
        out.append({"level": "caution", "icon": "INFO",
                    "text": f"High WACC: {wacc:.2%} - conservative discount rate compresses valuation."})

    margin_25 = income.loc["FY25A", "EBITDA_Margin"]
    margin_29 = income.loc["FY29E", "EBITDA_Margin"]
    delta = margin_29 - margin_25
    if delta > 0.05:
        out.append({"level": "good", "icon": "OK",
                    "text": f"Margin expansion: EBITDA grows {delta * 100:.1f} pp from FY25A to FY29E - operating leverage from COB-2 ramp + CDQ savings."})
    elif delta < -0.02:
        out.append({"level": "warning", "icon": "WARN",
                    "text": f"Margin compression: EBITDA contracts {abs(delta) * 100:.1f} pp from FY25A to FY29E - cost pressure not offset by realization."})

    return out


# =============================================================================
# EXCEL SYNC - defensive label-search parser
# =============================================================================

def parse_excel_assumptions(file_buffer) -> dict:
    """
    Parse JCL_Financial_Model_EXP.xlsx Scenario Engine sheet.
    Uses LABEL SEARCH (column A and B) to find rows, then reads Base column
    (typically D). Robust to row insertions/deletions in the source workbook.
    Returns {} on any failure - never raises.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_buffer, data_only=True, read_only=True)
    except Exception:
        return {}

    # Try common variations of the sheet name
    candidate_sheets = ["Scenario Engine", "Scenario_Engine", "Scenarios",
                        "Drivers", "Assumptions"]
    sheet_name = next((s for s in candidate_sheets if s in wb.sheetnames), None)
    if sheet_name is None:
        try:
            wb.close()
        except Exception:
            pass
        return {}

    ws = wb[sheet_name]

    # Find which column holds "Base" values by scanning for header row
    # In the JCL Scenario Engine sheet, header row has labels like:
    #   col A = "Driver" / category, col B = "Bull", col C = "Base", col D = "Bear"
    # But layouts vary; we search the first 30 rows for a cell whose value is "Base"
    base_col = None
    for r in range(1, 30):
        for c in range(1, 8):
            try:
                v = ws.cell(row=r, column=c).value
                if isinstance(v, str) and v.strip().lower() == "base":
                    # Verify by checking neighbor cells contain "Bull" or "Bear"
                    neighbors = []
                    for dc in (-1, 1):
                        try:
                            nv = ws.cell(row=r, column=c + dc).value
                            if isinstance(nv, str):
                                neighbors.append(nv.strip().lower())
                        except Exception:
                            pass
                    if any(n in ("bull", "bear") for n in neighbors):
                        base_col = c
                        break
            except Exception:
                continue
        if base_col is not None:
            break

    # Fallback: if no explicit "Base" header found, default to column C (3)
    # which is the most common layout in the JCL workbook
    if base_col is None:
        base_col = 3

    # Label patterns -> (assumption key, plausibility bounds, value transformer)
    # Patterns are matched case-insensitively against text in columns A or B
    LABEL_MAP = [
        # (search_substrings, assumption_key, lo_bound, hi_bound)
        (["cogs (% of net sales)", "cogs %", "cogs % of net sales"],
         "cogs_pct", 0.50, 0.98),
        (["interest rate on debt", "interest rate (%)", "cost of debt"],
         "interest_rate", 0.04, 0.20),
        (["terminal growth rate"],
         "terminal_growth", -0.01, 0.08),
        (["unlevered beta"],
         "unlevered_beta", 0.40, 2.00),
        (["coke realization", "coke realisation"],
         "coke_realization", 10_000, 60_000),
        (["cob-2 util fy28", "cob2 util fy28", "steady-state util", "cob-2 utilization"],
         "cob2_util_steady", 0.20, 1.00),
        (["risk-free rate", "rf rate", "rf,", "risk free"],
         "rf_rate", 0.02, 0.15),
        (["equity risk premium", "erp"],
         "erp", 0.03, 0.15),
        (["target debt-to-equity", "target d/e"],
         "target_de", 0.10, 3.00),
    ]

    def _get_label(row_idx: int) -> str:
        try:
            a = ws.cell(row=row_idx, column=1).value
            b = ws.cell(row=row_idx, column=2).value
        except Exception:
            return ""
        parts = [str(p).strip().lower() for p in (a, b) if p is not None]
        return " | ".join(parts)

    def _find_row(substrings) -> Optional[int]:
        # Scan first 200 rows looking for any row whose label contains
        # ALL words of any substring (case-insensitive)
        for r in range(1, 201):
            label = _get_label(r)
            if not label:
                continue
            for needle in substrings:
                if all(tok in label for tok in needle.split()):
                    return r
        return None

    def _read_base_value(row_idx: int) -> Optional[float]:
        # Try detected base_col first, then C, D, E as fallbacks
        cols_to_try = [base_col] + [c for c in (3, 4, 5) if c != base_col]
        for col in cols_to_try:
            try:
                v = ws.cell(row=row_idx, column=col).value
                if v is None:
                    continue
                return float(v)
            except (TypeError, ValueError):
                continue
        return None

    result: Dict[str, float] = {}
    for substrings, key, lo, hi in LABEL_MAP:
        row = _find_row(substrings)
        if row is None:
            continue
        v = _read_base_value(row)
        if v is None:
            continue
        if not (lo <= v <= hi):
            continue
        result[key] = v

    try:
        wb.close()
    except Exception:
        pass
    return result


# =============================================================================
# REVERSE DCF - implied beta solver
# =============================================================================

def solve_implied_beta(
    assumptions: dict,
    target_vps: float,
    lo: float = 0.30,
    hi: float = 2.50,
    tol: float = 1e-4,
    max_iter: int = 60,
) -> Optional[Dict]:
    """
    Bisection search: find unlevered_beta that makes value_per_share == target_vps.
    Holding all other drivers constant.
    Returns {"beta": float, "implied_wacc": float} or None if target outside range.
    """
    def _vps_for_beta(beta: float) -> float:
        tmp = assumptions.copy()
        tmp["unlevered_beta"] = beta
        try:
            return JCLFinancialEngine(assumptions=tmp).build()["dcf"]["value_per_share"]
        except Exception:
            return float("nan")

    lo_vps = _vps_for_beta(lo)
    hi_vps = _vps_for_beta(hi)
    # Higher beta -> higher WACC -> lower VPS
    if math.isnan(lo_vps) or math.isnan(hi_vps):
        return None
    if target_vps > lo_vps or target_vps < hi_vps:
        return None

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        mid_vps = _vps_for_beta(mid)
        if math.isnan(mid_vps):
            return None
        if abs(mid_vps - target_vps) < tol * max(target_vps, 1.0):
            break
        if mid_vps > target_vps:
            lo = mid
        else:
            hi = mid

    final_beta = (lo + hi) / 2
    tmp = assumptions.copy()
    tmp["unlevered_beta"] = final_beta
    try:
        result = JCLFinancialEngine(assumptions=tmp).build()
        return {"beta": final_beta,
                "implied_wacc": result["dcf"]["wacc"],
                "achieved_vps": result["dcf"]["value_per_share"]}
    except Exception:
        return None


def solve_implied_terminal_growth(
    assumptions: dict,
    target_vps: float,
    lo: float = -0.01,
    hi: float = 0.07,
    tol: float = 1e-4,
    max_iter: int = 60,
) -> Optional[Dict]:
    """Find terminal growth that makes VPS == target. Returns dict or None."""
    def _vps(g: float) -> float:
        tmp = assumptions.copy()
        tmp["terminal_growth"] = g
        try:
            return JCLFinancialEngine(assumptions=tmp).build()["dcf"]["value_per_share"]
        except Exception:
            return float("nan")

    lo_vps = _vps(lo)
    hi_vps = _vps(hi)
    if math.isnan(lo_vps) or math.isnan(hi_vps):
        return None
    if target_vps < lo_vps or target_vps > hi_vps:
        return None

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        mid_vps = _vps(mid)
        if math.isnan(mid_vps):
            return None
        if abs(mid_vps - target_vps) < tol * max(target_vps, 1.0):
            break
        if mid_vps < target_vps:
            lo = mid
        else:
            hi = mid

    final_g = (lo + hi) / 2
    return {"terminal_growth": final_g, "achieved_vps": _vps(final_g)}


# =============================================================================
# COVENANT STRESS TESTER
# =============================================================================

def covenant_stress_sweep(
    assumptions: dict,
    driver_key: str = "interest_rate",
    lo_override: Optional[float] = None,
    hi_override: Optional[float] = None,
    steps: int = 40,
    covenant_floor: float = 1.20,
) -> dict:
    """Sweep one driver, compute min DSCR at each value, return breach point."""
    DEFAULT_RANGES = {
        "interest_rate":    (0.04, 0.25),
        "cogs_pct":         (0.70, 0.98),
        "cob2_util_steady": (0.20, max(0.20, assumptions.get("cob2_util_steady", 0.80))),
    }
    lo = lo_override if lo_override is not None else DEFAULT_RANGES.get(driver_key, (0.0, 1.0))[0]
    hi = hi_override if hi_override is not None else DEFAULT_RANGES.get(driver_key, (0.0, 1.0))[1]
    if hi <= lo:
        hi = lo + 0.05

    driver_vals = np.linspace(lo, hi, steps)
    min_dscr_series: List[float] = []
    breach_value: Optional[float] = None
    breach_year: Optional[str] = None

    for v in driver_vals:
        tmp = assumptions.copy()
        tmp[driver_key] = float(v)
        try:
            res = JCLFinancialEngine(assumptions=tmp).build()
            rat = res["ratios"]
            min_d = rat["DSCR"].min()
            min_y = rat["DSCR"].idxmin()
            min_dscr_series.append(float(min_d))
            if breach_value is None and min_d < covenant_floor:
                breach_value = float(v)
                breach_year = str(min_y)
        except Exception:
            min_dscr_series.append(float("nan"))

    return {
        "driver_values": [float(v) for v in driver_vals],
        "min_dscr_series": min_dscr_series,
        "breach_value": breach_value,
        "breach_year": breach_year,
        "driver_key": driver_key,
        "covenant_floor": covenant_floor,
    }


# =============================================================================
# TEXT REPORT GENERATOR
# =============================================================================

def generate_text_report(results: dict, assumptions: dict, scenario: str) -> str:
    """Generate one-page markdown analyst report. Never raises."""
    try:
        inc = results["income"]
        dcf = results["dcf"]
        rat = results["ratios"]
        wcc = dcf["wacc_components"]
    except Exception:
        return "# Report generation failed - results dict missing required keys.\n"

    def cr(v): return f"INR {v:,.1f} Cr"
    def pc(v): return f"{v * 100:.1f}%"

    sep = "-" * 60
    lines = [
        "# JINDAL COKE LTD - ANALYST REPORT",
        f"Scenario: {scenario.upper()}  |  Generated: {_date.today().isoformat()}",
        "Model: JCL EXP v2.0  |  Currency: INR Crores",
        "",
        sep,
        "## 1. VALUATION SUMMARY",
        sep,
        f"Enterprise Value         : {cr(dcf['enterprise_value'])}",
        f"(+) FY25A Cash           : {cr(dcf['cash'])}",
        f"(-) Total Debt           : {cr(dcf['debt'])}",
        f"(-) Preference Capital   : {cr(dcf['preference'])}",
        f"Equity Value             : {cr(dcf['equity_value'])}",
        "Shares Outstanding       : 3.243 Crore",
        f"Intrinsic Value/Share    : INR {dcf['value_per_share']:,.2f}",
        "",
        f"WACC                     : {pc(dcf['wacc'])}",
        f"Terminal Growth (g)      : {pc(dcf['terminal_growth'])}",
        f"% EV from Terminal Value : {dcf['pct_ev_terminal'] * 100:.1f}%",
        "",
        sep,
        "## 2. WACC BUILD",
        sep,
        f"Risk-free Rate (Rf)      : {pc(assumptions['rf_rate'])}",
        f"Equity Risk Premium      : {pc(assumptions['erp'])}",
        f"Unlevered Beta (bu)      : {assumptions['unlevered_beta']:.3f}",
        f"Relevered Beta (bL)      : {wcc['Beta_Levered']:.3f}",
        f"Cost of Equity (Ke)      : {pc(wcc['Ke'])}",
        f"After-tax Cost of Debt   : {pc(wcc['Kd_AT'])}",
        f"Cost of Preference (Kp)  : {pc(wcc['Kp'])}",
        f"Target D/E               : {assumptions['target_de']:.2f}x",
        "",
        sep,
        "## 3. INCOME STATEMENT (INR Cr)",
        sep,
        f"{'Year':<10}{'Revenue':>10}{'EBITDA':>10}{'EBITDA%':>9}{'PAT':>10}{'PAT%':>8}",
        "-" * 57,
    ]
    for y in inc.index:
        lines.append(
            f"{y:<10}"
            f"{inc.loc[y, 'Net_Sales']:>10,.0f}"
            f"{inc.loc[y, 'EBITDA']:>10,.0f}"
            f"{inc.loc[y, 'EBITDA_Margin'] * 100:>8.1f}%"
            f"{inc.loc[y, 'PAT']:>10,.0f}"
            f"{inc.loc[y, 'PAT_Margin'] * 100:>7.1f}%"
        )
    lines += [
        "",
        sep,
        "## 4. COVENANT METRICS",
        sep,
        f"{'Year':<10}{'DSCR':>8}{'ND/EBITDA':>12}{'Status':>12}",
        "-" * 42,
    ]
    for y in rat.index:
        d = rat.loc[y, "DSCR"]
        nd = rat.loc[y, "Net_Debt_EBITDA"]
        flag = "PASS" if d >= 1.20 else "BREACH"
        lines.append(f"{y:<10}{d:>7.2f}x{nd:>11.2f}x{flag:>12}")

    lines += [
        "",
        sep,
        "## 5. KEY ASSUMPTIONS",
        sep,
        f"Coke Realization         : INR {assumptions['coke_realization']:,.0f}/MT",
        f"COB-2 Steady-state Util  : {pc(assumptions['cob2_util_steady'])}",
        f"COGS % (FY25A anchor)    : {pc(assumptions['cogs_pct'])}",
        f"Interest Rate on Debt    : {pc(assumptions['interest_rate'])}",
        f"Capex Intensity          : {pc(assumptions['capex_intensity'])}",
        "",
        sep,
        "## 6. RISK FLAGS",
        sep,
    ]
    try:
        for ins in generate_insights(results):
            lines.append(f"[{ins['icon']:5}] {ins['text']}")
    except Exception:
        lines.append("(Insights unavailable.)")

    lines += [
        "",
        sep,
        "DISCLAIMER: Illustrative model for institutional valuation training.",
        "Independent verification required for any investment decision.",
        sep,
    ]
    return "\n".join(lines)
