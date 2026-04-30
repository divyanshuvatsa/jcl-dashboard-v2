# Jindal Coke Ltd. — Financial Dashboard

A real-time Streamlit dashboard wrapping the JCL standalone valuation model: 3-statement projections, DCF, scenario analysis, Monte Carlo, covenant stress testing, and an offline rule-based smart analyst. Dark neon theme. Free to deploy. No API keys.

---

## What this is

A modular dashboard around the core JCL valuation model (`JCL_Financial_Model_EXP.xlsx`). It produces:

- 9-year projections (FY25A–FY33E) of Income Statement, Balance Sheet, Cash Flow
- DCF with WACC build, terminal value, EV-to-equity bridge
- Sensitivity (WACC × g heatmap, tornado), Monte Carlo
- Reverse DCF (implied beta, implied terminal growth)
- Covenant stress tester (sweep one driver until DSCR breaches floor)
- Scenario comparison (Bull / Base / Bear)
- Smart analyst — 14 specialist routes plus a fallback that returns live numbers
- Excel sync (drag-drop the source workbook to pull Base assumptions)
- URL state, named snapshots, full Excel + Markdown report download

---

## Project structure

```
jcl_dashboard/
├── app.py                # Streamlit UI — entry point
├── engine.py             # Pure financial logic (no Streamlit, no network)
├── visuals.py            # Plotly charts only (no Streamlit)
├── analyst.py            # Rule-based smart analyst
├── state.py              # URL params + saved snapshot helpers
├── requirements.txt
├── .streamlit/
│   └── config.toml       # Pins dark theme so light/dark toggle can't override
└── README.md
```

The split exists so each module can be unit-tested independently. `engine.py` is the source of truth; nothing else mutates model output.

---

## Quick start (local)

```bash
# 1. Clone or copy this folder to your machine
cd jcl_dashboard

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .\.venv\Scripts\activate         # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
streamlit run app.py
```

The app opens at `http://localhost:8501`. First load takes 5–10 seconds while caches warm; subsequent interactions are sub-second.

**Python version**: 3.10 or higher. Tested on 3.12.

---

## Deploy to Streamlit Community Cloud (free)

1. **Push to GitHub.** Create a public or private repo containing the `jcl_dashboard/` folder (must include `requirements.txt` at the project root).
2. **Sign in** at [share.streamlit.io](https://share.streamlit.io) with your GitHub account.
3. **New app** → pick the repo and branch → **main file path: `app.py`** → Deploy.
4. The build takes ~2 minutes. The dark theme is pinned via `.streamlit/config.toml` so it survives Streamlit's light/dark toggle.

**Resource limits.** Community Cloud gives ~1 GB RAM. The model fits comfortably; Monte Carlo at 5,000 sims uses ~80 MB peak. If you ever see an OOM, drop Monte Carlo to 2,000 sims.

**Custom domain or Snowflake/Enterprise.** Same `app.py` works on Snowflake Streamlit and any container host. No vendor lock-in.

---

## Tab-by-tab user guide

### 1. Valuation Bridge
Three views: the EV-to-Equity waterfall, the per-year PV composition (showing how much of EV comes from terminal value), and the revenue × EBITDA margin trend with an optional YoY-growth toggle.

**Below that — the Reverse DCF solver.** Type a target value-per-share, click "Solve Implied Beta," and the bisection routine returns the unlevered beta the market would need to imply to justify your target (holding other drivers constant). Same for terminal growth `g`. Useful for: *"At ₹600/share, what's the market saying about JCL's risk premium?"*

### 2. 3-Statement
Revenue mix by product (stacked area), debt profile + DSCR vs covenant floor (1.20×), and the cash flow build (CFO + CFI + CFF stacked, closing cash overlaid).

### 3. Sensitivity & Risk
WACC × terminal-growth heatmap (left) and a tornado chart (right) showing the eight largest value drivers ranked by ±10% impact range.

**Below that — the Covenant Stress Tester.** Pick a driver (interest rate, COGS %, COB-2 utilisation), set a covenant floor, hit Run. The chart sweeps the driver across a plausible range and marks the breach point in red. The KPI card below tells you exactly where DSCR drops below the floor and in which year.

### 4. Monte Carlo
Probabilistic EV distribution. Five drivers shocked simultaneously with calibrated standard deviations. Default 1,000 sims; max 5,000. Output: histogram with mean/P5/P95 markers and KPI cards summarising the distribution.

### 5. Detailed Tables
Income Statement, Balance Sheet, Cash Flow, and Ratios in dark-themed HTML tables (no `st.dataframe` — those don't theme well). Plus two download buttons:

- **Excel workbook** (.xlsx) — multi-sheet export of all tables plus assumptions and FCFF build
- **Analyst report** (.md) — formatted one-pager suitable for IC memos

### 6. Smart Analyst
Type a question. The router checks 14 keyword patterns (WACC, DSCR, margins, valuation, revenue, debt, cash flow, sensitivity, scenarios, tax, capex, working capital, equity, help) and answers with a structured response populated from live model state. If no pattern matches, the fallback returns the headline numbers and suggests rephrasings — no hallucinated answers.

Eight quick-prompt buttons cover the common asks. Conversation history persists within the session.

### 7. Scenario Compare
Three KPI cards (Bull/Base/Bear) showing VPS, EV, WACC, EBITDA margin, and min DSCR side-by-side. Below: a two-axis overlay of EBITDA % (lines) and Net Debt (bars) across all three scenarios, plus a polar radar chart normalising five health metrics to a 0–10 scale for the year you select.

---

## Sidebar — Control Deck

- **Scenario picker** — Bull / Base / Bear / Custom. Custom appears automatically if you tweak any slider.
- **Reset to Base** — wipes all changes back to Base preset.
- **Share URL** — encodes current assumptions into the address bar. Send the link to a colleague to reproduce your scenario exactly.
- **Diff tracker** — counts and lists every assumption that differs from Base. Catches accidental changes.
- **Driver sliders** — grouped into Operations, Financing, and Cost of Capital. Every slider re-runs the whole engine in <100 ms (cached).
- **Saved Snapshots** — name and store up to 5 assumption sets within the session. Useful for: *"Bear with refi"*, *"Base + 100 bps Rf shock"*. (FIFO eviction past 5.)
- **Sync from Excel** — upload `JCL_Financial_Model_EXP.xlsx` to pull the current Base column from the Scenario Engine sheet. The parser does label-based search (case-insensitive) so it survives row insertions.

---

## Key modelling assumptions

| Block | Driver | Base | Bull | Bear |
|---|---|---|---|---|
| Operations | COB-2 steady utilisation | 80% | 85% | 75% |
| Operations | Coke realisation (₹/MT) | 27,000 | 30,000 | 24,000 |
| Operations | COGS % (FY25A anchor) | 82.0% | 79.0% | 85.0% |
| Operations | Maintenance capex % | 2.5% | 2.0% | 3.0% |
| Financing | Interest rate on debt | 9.0% | 8.5% | 10.0% |
| Financing | Target D/E | 0.82× | 0.60× | 1.00× |
| Cost of capital | Unlevered β | 0.85 | 0.80 | 0.95 |
| Cost of capital | Risk-free rate | 7.0% | 6.5% | 7.5% |
| Cost of capital | ERP | 7.25% | 7.0% | 7.5% |
| Cost of capital | Terminal g | 0.0% | 2.0% | 0.0% |

**Tax**: MAT (17.472%) on explicit-period FCFF, CIT (25.17%) on terminal — JCL is expected to exit MAT regime by FY33E. **Shares**: 3.243 Cr. **Preference capital**: ₹109.26 Cr at 9% Kp.

---

## Validation vs source workbook

| Metric | Engine (Base) | Source Excel | Note |
|---|---|---|---|
| Value per share | ₹545.87 | ₹514.75 | +6.0% — engine uses streamlined interest cascade (no buyers-credit run-off detail), this is intentional |
| WACC | 12.51% | 12.51% | exact match |
| Enterprise value | ₹2,215 Cr | ₹2,114 Cr | +4.8% |
| Terminal value | ₹2,099 Cr (CIT-taxed) | ₹2,099 Cr | exact — uses CIT 25.17% |
| % EV from TV | 36.9% | ~37% | match |
| FY26E revenue | ₹2,081 Cr | ₹2,081 Cr | exact — bottom-up build |
| BS balance | balances all 10 years | balances | match |

The +6% VPS gap is the sole material divergence and is documented above. If you need exact-to-the-rupee parity with the source Excel, use the source — this dashboard prioritises responsiveness and what-if speed over the last 6%.

---

## Troubleshooting

**"Module not found: streamlit/plotly/openpyxl"**
Make sure your virtual environment is active and `pip install -r requirements.txt` completed cleanly.

**Theme appears light despite the config**
Hit Ctrl-Shift-R / Cmd-Shift-R to force-reload. Streamlit caches CSS aggressively across sessions. If it persists, check `.streamlit/config.toml` exists at the project root (not inside `jcl_dashboard/`'s parent).

**Excel sync says "Could not parse the Scenario Engine sheet"**
The parser looks for a sheet named "Scenario Engine" (or "Scenario_Engine", "Scenarios", "Drivers", "Assumptions") with a header row containing the words "Bull", "Base", "Bear" in adjacent cells. If you renamed the sheet or column structure, rename it back or edit `LABEL_MAP` in `engine.py`.

**Monte Carlo button doesn't show a chart**
The result is computed and cached when you click Run Simulation — the chart appears below. If the histogram is blank, check the log for shock values producing NaN (very aggressive parameters can crash the engine; results are filtered before plotting).

**Reverse DCF says "outside achievable range"**
Beta is bounded [0.30, 2.50] and `g` to [-1%, 7%]. Targets requiring values outside those bounds aren't reachable holding other drivers constant. Try changing other drivers first.

**Streamlit Cloud build fails**
Check the build logs for the exact error. Most common: `requirements.txt` not at project root, or pinned package versions conflict. The minimum versions in `requirements.txt` are tested with Python 3.10–3.12.

---

## Architecture notes

- `engine.py` has zero Streamlit imports and zero network calls. Unit-test it standalone.
- `visuals.py` imports only `plotly`, `pandas`, `numpy`. Same standalone-testable.
- All cached functions take **tuples**, not dicts (dicts aren't hashable — Streamlit will raise).
- Sparklines use mini Plotly charts, not SVG markdown — Firefox sanitises complex SVG inside `unsafe_allow_html=True` differently from Chrome, and we want consistent rendering.
- Reverse DCF uses bisection on `unlevered_beta` (not "scale all WACC components proportionally") because changing one lever is more interpretable for IC discussion: *"the implied beta is 0.70."*

---

## Disclaimer

Illustrative model for institutional valuation training. Independent verification required for any investment decision. The dashboard is not investment advice.
