"""
analyst.py - JCL Smart Analyst (rule-based, offline, free)
============================================================
Routes natural-language queries to template-driven responses populated with
live model numbers. No API keys, no network, no LLM. Pure regex + Python.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional


class SmartAnalyst:
    """Rule-based financial analyst for the JCL model."""

    # Keyword patterns -> handler method names. Patterns use \w* suffix to
    # allow prefix matching (e.g. "compar" matches "compare", "comparison").
    ROUTES = [
        (r"\b(wacc|discount.?rate|cost.?of.?equity|cost.?of.?debt|ke\b|kd\b|beta|hamada)",
         "_ans_wacc"),
        (r"\b(dscr|covenant\w*|debt.?service|coverage|iscr|facr|breach\w*)",
         "_ans_covenants"),
        (r"\b(margin\w*|ebitda|gross.?profit|profitab\w*|operating.?leverage)",
         "_ans_margins"),
        (r"\b(valuation\w*|enterprise.?value|equity.?value|per.?share|vps|bridge|intrinsic|fair.?value)",
         "_ans_valuation"),
        (r"\b(revenue\w*|sales\w*|coke.?realization|realisation|cob.?2|utili[sz]ation\w*|production|volume\w*|by.?product\w*|coal.?tar)",
         "_ans_revenue"),
        (r"\b(debt|leverage\w*|borrowing\w*|net.?debt|deleverag\w*|repay\w*|term.?loan|buyers.?credit|revolver)",
         "_ans_debt"),
        (r"\b(cash.?flow|cfo\b|cfi\b|cff\b|free.?cash|fcff|liquidity|cash.?balanc\w*)",
         "_ans_cashflow"),
        (r"\b(sensitiv\w*|tornado|driver\w*|biggest.?risk|risk\w*|impact\w*|stress\w*|shock\w*|what.?if)",
         "_ans_sensitivity"),
        (r"\b(scenario\w*|bull\w*|bear\w*|compar\w*|versus|differ\w*)",
         "_ans_scenarios"),
        (r"\b(tax\w*|mat\b|cit\b|deferred|provision\w*)",
         "_ans_tax"),
        (r"\b(report|summary|overview|snapshot|brief|tell.?me.?about|status|analyst)",
         "_ans_full_report"),
        (r"\b(depreciation|capex|capital.?expenditure|fixed.?asset\w*|nfa|cwip)",
         "_ans_capex_dep"),
        (r"\b(working.?capital|debtor\w*|inventor\w*|payable\w*|nwc|days)",
         "_ans_working_capital"),
        (r"\b(pref|preference.?share\w*|dividend\w*|buyback\w*|equity)",
         "_ans_equity_structure"),
        (r"\b(help\b|what.?can|how.?do|guide|capabilit\w*|topics)",
         "_ans_help"),
    ]

    def __init__(self, results: dict, assumptions: dict, scenario: str,
                 all_scenario_results: Optional[Dict[str, dict]] = None):
        self.r = results
        self.a = assumptions
        self.scn = scenario
        self.all = all_scenario_results or {}

    def answer(self, query: str) -> str:
        q = query.lower().strip()
        if not q:
            return "Please type a question. Try `help` to see what I can answer."

        for pattern, method in self.ROUTES:
            if re.search(pattern, q):
                try:
                    return getattr(self, method)()
                except Exception as e:
                    return self._fallback(f"(internal error: {e})")
        return self._fallback()

    # ---------- helpers ----------------------------------------------------
    def _inc(self): return self.r["income"]
    def _dcf(self): return self.r["dcf"]
    def _rat(self): return self.r["ratios"]
    def _bs(self):  return self.r["balance"]
    def _cfs(self): return self.r["cashflow"]
    def _rev(self): return self.r["revenue"]

    @staticmethod
    def _cr(v): return f"INR {v:,.1f} Cr"

    @staticmethod
    def _pc(v): return f"{v * 100:.1f}%"

    # ---------- handlers ---------------------------------------------------
    def _ans_help(self) -> str:
        return (
            "I'm a rule-based analyst with live access to your model state.\n\n"
            "**Topics I can answer:**\n"
            "- WACC build, cost of equity / debt, beta\n"
            "- DSCR, ISCR, FACR, covenant breaches\n"
            "- Margins, EBITDA trajectory, profitability\n"
            "- Valuation bridge, EV, equity value, per share\n"
            "- Revenue build, COB-2 ramp, by-products\n"
            "- Debt schedule, deleveraging, net debt path\n"
            "- Cash flow build (CFO / CFI / CFF)\n"
            "- Sensitivity, tornado, top drivers\n"
            "- Scenario comparison (Bull / Base / Bear)\n"
            "- Tax (MAT vs CIT)\n"
            "- Working capital (debtor / inventory / payable days)\n"
            "- Capex, depreciation, fixed assets\n"
            "- Equity structure, preference capital, buyback\n\n"
            "Try: *\"Why is DSCR lowest in FY27?\"* or *\"Walk me through the WACC.\"*"
        )

    def _ans_wacc(self) -> str:
        d = self._dcf()
        w = d["wacc_components"]
        return (
            f"**WACC Breakdown - {self.scn} scenario**\n\n"
            f"- Risk-free Rate (Rf): {self._pc(self.a['rf_rate'])}\n"
            f"- Equity Risk Premium (ERP): {self._pc(self.a['erp'])}\n"
            f"- Unlevered Beta: {self.a['unlevered_beta']:.2f}\n"
            f"- Relevered Beta: {w['Beta_Levered']:.3f} (Hamada with D/E {self.a['target_de']:.2f}x)\n"
            f"- Cost of Equity (Ke): {self._pc(w['Ke'])}\n"
            f"- Pre-tax Cost of Debt: {self._pc(self.a['interest_rate'])}\n"
            f"- After-tax Cost of Debt (Kd): {self._pc(w['Kd_AT'])}\n"
            f"- Cost of Preference (Kp): {self._pc(w['Kp'])}\n\n"
            f"**WACC = {self._pc(d['wacc'])}**\n\n"
            f"Terminal growth g = {self._pc(d['terminal_growth'])} -> "
            f"WACC - g spread = {self._pc(d['wacc'] - d['terminal_growth'])}\n\n"
            f"Book-value weights from FY25A close (E={self._cr(797.6)}, "
            f"D={self._cr(545.82)}, P={self._cr(109.26)})."
        )

    def _ans_covenants(self) -> str:
        rat = self._rat()
        rows = [
            "**Covenant Tracker - Projection Years**\n",
            "| Year | DSCR | Net Debt/EBITDA | Status |",
            "|------|------|-----------------|--------|",
        ]
        for y in rat.index:
            dscr = rat.loc[y, "DSCR"]
            nd_eb = rat.loc[y, "Net_Debt_EBITDA"]
            status = "PASS" if dscr >= 1.20 else "BREACH"
            rows.append(f"| {y} | {dscr:.2f}x | {nd_eb:.2f}x | {status} |")

        min_dscr = rat["DSCR"].min()
        min_year = rat["DSCR"].idxmin()
        rows.append("")
        rows.append(
            f"**Minimum DSCR: {min_dscr:.2f}x in {min_year}** "
            f"(covenant floor 1.20x -> "
            f"{'SAFE' if min_dscr >= 1.20 else 'AT RISK'})\n\n"
            "DSCR = (EBITDA - Tax) / (Interest + Principal). "
            "Falls in early years due to TL drawdown plus Buyers Credit run-off "
            "creating elevated gross debt service even as EBITDA expands."
        )
        return "\n".join(rows)

    def _ans_margins(self) -> str:
        inc = self._inc()
        rows = [
            "**Margin Trajectory (INR Cr)**\n",
            "| Year | Revenue | EBITDA | EBITDA % | PAT | PAT % |",
            "|------|---------|--------|----------|-----|-------|",
        ]
        for y in inc.index:
            rows.append(
                f"| {y} | {inc.loc[y, 'Net_Sales']:,.0f} | "
                f"{inc.loc[y, 'EBITDA']:,.0f} | "
                f"{inc.loc[y, 'EBITDA_Margin'] * 100:.1f}% | "
                f"{inc.loc[y, 'PAT']:,.0f} | "
                f"{inc.loc[y, 'PAT_Margin'] * 100:.1f}% |"
            )
        m25 = inc.loc["FY25A", "EBITDA_Margin"]
        m26 = inc.loc["FY26E", "EBITDA_Margin"]
        m29 = inc.loc["FY29E", "EBITDA_Margin"]
        rows.append("")
        rows.append(
            f"**Key insight:** EBITDA margin moves "
            f"{(m26 - m25) * 100:+.1f} pp in FY26E "
            f"({m25 * 100:.1f}% -> {m26 * 100:.1f}%) driven by COB-2 ramp "
            f"adding ~245,000 MT, coal pricing tailwind, and CDQ heat recovery "
            f"(~INR 40 Cr/yr). Margins normalise to ~{m29 * 100:.1f}% from "
            f"FY27E onwards as costs revert and capacity is fully utilised."
        )
        return "\n".join(rows)

    def _ans_valuation(self) -> str:
        d = self._dcf()
        pct_tv = d["pct_ev_terminal"] * 100
        verdict = (
            "Healthy - explicit period dominates."
            if pct_tv < 50
            else "Moderately dependent on terminal assumptions - stress-test g and WACC."
            if pct_tv < 70
            else "Warning: perpetuity assumptions dominate. Stress-test aggressively."
        )
        return (
            f"**DCF Valuation - {self.scn} Scenario**\n\n"
            f"**Enterprise Value Bridge**\n"
            f"- Sum of PV (FY26-FY33): {self._cr(d['sum_pv_fcff'])}\n"
            f"- PV of Terminal Value (g={self._pc(d['terminal_growth'])}): "
            f"{self._cr(d['pv_terminal'])} ({pct_tv:.1f}% of EV)\n"
            f"- **Enterprise Value: {self._cr(d['enterprise_value'])}**\n\n"
            f"**Equity Bridge**\n"
            f"- EV: {self._cr(d['enterprise_value'])}\n"
            f"- (+) FY25A Cash: {self._cr(d['cash'])}\n"
            f"- (-) Total Debt: {self._cr(d['debt'])}\n"
            f"- (-) Preference Capital: {self._cr(d['preference'])}\n"
            f"- **Equity Value: {self._cr(d['equity_value'])}**\n\n"
            f"Shares outstanding: 3.243 Crore  \n"
            f"**Intrinsic Value per Share: INR {d['value_per_share']:,.2f}**\n\n"
            f"Terminal value is {pct_tv:.1f}% of EV. {verdict}"
        )

    def _ans_revenue(self) -> str:
        rev = self._rev()
        inc = self._inc()
        a = self.a
        cob1_vol = 429_000 * 0.911766
        cob2_vol = 350_000 * a["cob2_util_steady"]
        total_vol = cob1_vol + cob2_vol
        rows = [
            f"**Revenue Build - {self.scn} Scenario**\n",
            "**Production (steady-state FY27E+)**\n",
            f"- COB-1: 429,000 MT x 91.18% util = {cob1_vol:,.0f} MT",
            f"- COB-2: 350,000 MT x {a['cob2_util_steady']:.0%} util = {cob2_vol:,.0f} MT",
            f"- Total: {total_vol:,.0f} MT/year\n",
            "**Realization & By-products**\n",
            f"- Coke: INR {a['coke_realization']:,.0f}/MT",
            "- COG: 222 Nm3/MT x INR 19.44/Nm3 = INR 4,316/MT-equiv",
            "- Coal Tar: 3.78% yield x INR 37,000/MT = INR 1,399/MT-equiv\n",
            "**Revenue by year (INR Cr)**\n",
            "| Year | Coke | COG | Coal Tar | Total |",
            "|------|------|-----|----------|-------|",
        ]
        for y in rev.index:
            rows.append(
                f"| {y} | {rev.loc[y, 'Coke_Revenue']:,.0f} | "
                f"{rev.loc[y, 'COG_Revenue']:,.0f} | "
                f"{rev.loc[y, 'Tar_Revenue']:,.0f} | "
                f"{inc.loc[y, 'Net_Sales']:,.0f} |"
            )
        return "\n".join(rows)

    def _ans_debt(self) -> str:
        rat = self._rat()
        bs = self._bs()
        rows = [
            f"**Debt & Deleveraging - {self.scn} Scenario**\n",
            "| Year | Total Debt | Cash | Net Debt | Net Debt/EBITDA |",
            "|------|-----------|------|----------|-----------------|",
        ]
        for y in rat.index:
            td = rat.loc[y, "Total_Debt"]
            cash = bs.loc[y, "Cash"]
            nd = td - cash
            nd_eb = rat.loc[y, "Net_Debt_EBITDA"]
            rows.append(
                f"| {y} | {td:,.0f} | {cash:,.0f} | {nd:,.0f} | {nd_eb:.2f}x |"
            )

        flip_year = next(
            (y for y in rat.index if rat.loc[y, "Net_Debt"] < 0), None
        )
        rows.append("")
        rows.append(
            "FY25A debt structure: Bank TL ~INR 286 Cr + Buyers Credit ~INR 260 Cr "
            "= ~INR 546 Cr total. FY26E sees a TL drawdown of ~+INR 146 Cr for "
            "refinancing/capex; Buyers Credit runs off (INR 152 Cr in FY26E, "
            "INR 5 Cr FY27E, then 0). TL amortises INR 34-45 Cr/year through FY33E."
        )
        if flip_year:
            rows.append(f"\n**Net Debt turns negative in {flip_year}** "
                        "- cash exceeds total borrowings.")
        return "\n".join(rows)

    def _ans_cashflow(self) -> str:
        cfs = self._cfs()
        rows = [
            f"**Cash Flow Statement - {self.scn} Scenario**\n",
            "| Year | CFO | CFI | CFF | Net Delta | Closing Cash |",
            "|------|-----|-----|-----|-----------|--------------|",
        ]
        for y in cfs.index:
            net = cfs.loc[y, 'CFO'] + cfs.loc[y, 'CFI'] + cfs.loc[y, 'CFF']
            rows.append(
                f"| {y} | {cfs.loc[y, 'CFO']:,.0f} | "
                f"{cfs.loc[y, 'CFI']:,.0f} | "
                f"{cfs.loc[y, 'CFF']:,.0f} | "
                f"{net:,.0f} | "
                f"{cfs.loc[y, 'Closing_Cash']:,.0f} |"
            )

        min_year = cfs["Closing_Cash"].idxmin()
        min_cash = cfs["Closing_Cash"].min()
        rows.append("")
        rows.append(
            f"Minimum cash: INR {min_cash:,.0f} Cr in {min_year}. "
            "A conditional revolver (INR 30 Cr) draws when cash would otherwise "
            "fall below INR 50 Cr in the source model."
        )
        return "\n".join(rows)

    def _ans_sensitivity(self) -> str:
        try:
            from engine import JCLFinancialEngine
            eng = JCLFinancialEngine(assumptions=self.a.copy())
            tornado_df = eng.tornado_analysis()
            top3 = tornado_df.nlargest(3, "Range")
            rows = [
                f"**Sensitivity Analysis - {self.scn} Scenario**\n",
                "**Top 3 Value Drivers (tornado, +/-10-20% shock):**\n",
            ]
            for _, row in top3.iterrows():
                rows.append(
                    f"- **{row['Driver']}**: INR {row['Down']:+.0f}/sh (down) / "
                    f"INR {row['Up']:+.0f}/sh (up) -> range INR {row['Range']:.0f}/sh"
                )
            rows.append("")
            rows.append(
                f"**WACC x Terminal Growth Sensitivity**\n"
                f"Base: WACC {self._pc(self._dcf()['wacc'])}, "
                f"g={self._pc(self._dcf()['terminal_growth'])} -> "
                f"INR {self._dcf()['value_per_share']:,.0f}/sh\n\n"
                "A +100 bps WACC increase typically compresses value by INR 50-70/sh. "
                "See the Sensitivity & Risk tab for the full heatmap and covenant "
                "stress sweep."
            )
            return "\n".join(rows)
        except Exception:
            return "Sensitivity data unavailable. Verify the model builds with current assumptions."

    def _ans_scenarios(self) -> str:
        if not self.all:
            return (
                "Scenario comparison data not loaded in this session. "
                "Switch to the Scenario Compare tab for a full side-by-side view."
            )
        rows = [
            "**Scenario Comparison - Bull / Base / Bear**\n",
            "| Metric | Bull | Base | Bear |",
            "|--------|------|------|------|",
        ]
        metrics = [
            ("Value/Share (INR)", lambda r: f"INR {r['dcf']['value_per_share']:,.0f}"),
            ("EV (INR Cr)",       lambda r: f"INR {r['dcf']['enterprise_value']:,.0f}"),
            ("WACC",              lambda r: f"{r['dcf']['wacc'] * 100:.2f}%"),
            ("FY29E EBITDA %",    lambda r: f"{r['income'].loc['FY29E', 'EBITDA_Margin'] * 100:.1f}%"),
            ("Min DSCR",          lambda r: f"{r['ratios']['DSCR'].min():.2f}x"),
        ]
        for label, fn in metrics:
            try:
                row_vals = " | ".join(fn(self.all.get(s, self.r))
                                      for s in ["Bull", "Base", "Bear"])
                rows.append(f"| {label} | {row_vals} |")
            except Exception:
                continue
        rows.append("")
        rows.append(
            f"**Active scenario: {self.scn}**  "
            f"-> Value/Share INR {self.r['dcf']['value_per_share']:,.0f}"
        )
        return "\n".join(rows)

    def _ans_tax(self) -> str:
        return (
            "**Tax Treatment**\n\n"
            "- **MAT (Minimum Alternate Tax):** 15% + 10% surcharge + 4% cess "
            "= **17.472%**. Applied to explicit-period FCFF (FY26E-FY33E) since "
            "JCL is expected to remain in MAT regime while DTAs unwind.\n\n"
            "- **CIT (Normal Tax):** 22% + surcharge + cess = **25.17%**. "
            "Applied to **terminal FCFF only** - long-run assumption is JCL "
            "exits MAT as book profits catch up to taxable profits.\n\n"
            "- This switch reduces terminal FCFF from ~INR 287 Cr (MAT basis) to "
            "~INR 263 Cr (CIT basis), lowering TV by ~8.5%. Conservative and correct.\n\n"
            "- Opening unabsorbed depreciation: INR 36.26 Cr (mentor benchmark)."
        )

    def _ans_capex_dep(self) -> str:
        inc = self._inc()
        bs = self._bs()
        rows = [
            "**Capex & Depreciation Schedule**\n",
            "- Opening Gross Block (FY24A): NFA INR 461 Cr + CWIP INR 433 Cr = INR 894 Cr",
            "- FY25A: CWIP capitalises -> NFA INR 787 Cr (COB-2 completion)",
            "- Depreciation rate: 5% straight-line on opening gross block\n",
            "| Year | Depreciation | Capex | Net Block (NFA) |",
            "|------|-------------|-------|-----------------|",
        ]
        for y in inc.index:
            try:
                dep = inc.loc[y, "Depreciation"]
                capex = inc.loc[y, "Capex"] if "Capex" in inc.columns else 0
                nfa = bs.loc[y, "Net_Fixed_Assets"]
                rows.append(f"| {y} | {dep:,.1f} | {capex:,.1f} | {nfa:,.0f} |")
            except KeyError:
                continue
        rows.append("")
        rows.append(
            f"Maintenance capex = {self.a['capex_intensity']:.1%} of opening gross block. "
            "No growth capex modelled post-FY25A (COB-2 fully commissioned)."
        )
        return "\n".join(rows)

    def _ans_working_capital(self) -> str:
        return (
            "**Working Capital - Tandon-Style Days Approach**\n\n"
            "| Driver | FY25A | FY26E | FY27E+ steady |\n"
            "|--------|-------|-------|---------------|\n"
            "| Debtor Days | 35 | 34 | 31 |\n"
            "| Inventory Days | 45 | 43 | 40 |\n"
            "| Payable Days | 40 | 40 | 40 |\n\n"
            "NWC = (Debtors + Inventory) - Payables.  \n"
            "FY26E sees a large inventory release (~INR 132 Cr) as COB-2 coal "
            "buffer normalises after commissioning. Delta NWC feeds directly into "
            "the FCFF computation."
        )

    def _ans_equity_structure(self) -> str:
        d = self._dcf()
        return (
            "**Equity & Capital Structure**\n\n"
            "- Equity shares: 3.243 Crore (INR 32.43 Cr paid-up / INR 10 face value)\n"
            "- Preference capital: INR 109.26 Cr (10.926 Cr x INR 10 face, "
            "cumulative redeemable)\n"
            "- Cost of preference: 9.00%\n"
            "- FY26E includes a INR 179.95 Cr share buyback from JSL "
            "(parent group) - compresses cash to ~INR 32 Cr but is "
            "equity-value neutral in DCF.\n\n"
            f"**Current scenario equity value: {self._cr(d['equity_value'])}**  \n"
            f"Value per share: INR {d['value_per_share']:,.2f}  \n"
            f"(Post-pref deduction of {self._cr(d['preference'])} from EV bridge)"
        )

    def _ans_full_report(self) -> str:
        d = self._dcf()
        inc = self._inc()
        rat = self._rat()
        m26 = inc.loc["FY26E", "EBITDA_Margin"]
        m29 = inc.loc["FY29E", "EBITDA_Margin"]
        verdict = ("comfortable." if rat["DSCR"].min() >= 1.5
                   else "watch closely." if rat["DSCR"].min() >= 1.2
                   else "BREACH RISK.")
        return (
            f"**JCL Analyst Summary - {self.scn} Scenario**\n\n"
            f"**Valuation:** EV {self._cr(d['enterprise_value'])} -> "
            f"Equity {self._cr(d['equity_value'])} -> "
            f"**INR {d['value_per_share']:,.0f}/share**  \n"
            f"WACC {self._pc(d['wacc'])}, terminal g {self._pc(d['terminal_growth'])}, "
            f"TV = {d['pct_ev_terminal'] * 100:.0f}% of EV\n\n"
            f"**Revenue:** FY25A {self._cr(inc.loc['FY25A', 'Net_Sales'])} -> "
            f"FY26E {self._cr(inc.loc['FY26E', 'Net_Sales'])} (COB-2 ramp 70% util) "
            f"-> plateau ~{self._cr(inc.loc['FY27E', 'Net_Sales'])} FY27E+\n\n"
            f"**Margins:** EBITDA {m26 * 100:.1f}% FY26E -> {m29 * 100:.1f}% "
            f"FY29E+ (CDQ savings ~INR 46 Cr/yr + operating leverage)\n\n"
            f"**Covenants:** Min DSCR {rat['DSCR'].min():.2f}x "
            f"(floor 1.20x) - {verdict}  Net Debt turns negative by FY29E.\n\n"
            "Ask me about: WACC, covenants, margins, revenue, debt, cash flow, "
            "sensitivity, scenarios, tax, capex, working capital, or equity."
        )

    # ---------- fallback ---------------------------------------------------
    def _fallback(self, hint: str = "") -> str:
        d = self._dcf()
        inc = self._inc()
        rat = self._rat()
        return (
            "I don't have a dedicated template for that question, but here are "
            "the live numbers that might help:\n\n"
            + (f"_{hint}_\n\n" if hint else "")
            + f"- Active scenario: **{self.scn}**\n"
            f"- Value/Share: **INR {d['value_per_share']:,.0f}**\n"
            f"- Enterprise Value: {self._cr(d['enterprise_value'])}\n"
            f"- WACC: {self._pc(d['wacc'])}\n"
            f"- FY29E EBITDA margin: {self._pc(inc.loc['FY29E', 'EBITDA_Margin'])}\n"
            f"- Min DSCR: {rat['DSCR'].min():.2f}x in {rat['DSCR'].idxmin()}\n\n"
            "Try rephrasing with one of these keywords: WACC, DSCR, margin, "
            "valuation, revenue, debt, cash flow, sensitivity, scenarios, "
            "tax, capex, working capital. Or type `help` for the full list."
        )
