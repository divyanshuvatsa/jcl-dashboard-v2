"""
visuals.py - Jindal Coke Ltd. Visual Gallery (Dark Neon)
=========================================================
Plotly Graph Objects only. All charts dark-mode native, monospace font,
neon accent palette. Zero Streamlit imports.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go


# =============================================================================
# COLOR TOKENS - dark neon
# =============================================================================
PALETTE = {
    "bg_deep":      "#050A18",
    "bg_card":      "#0A0F1E",
    "bg_surface":   "#0F1729",
    "bg_hover":     "#141D30",
    "cyan":         "#00F0FF",
    "neon_green":   "#00FF9D",
    "neon_amber":   "#FFB800",
    "neon_pink":    "#FF2D78",
    "neon_purple":  "#BF5FFF",
    "white":        "#FFFFFF",
    "text_primary": "#E8EDF5",
    "text_muted":   "#6B7FA3",
    "border_dim":   "rgba(0,240,255,0.10)",
    "border_mid":   "rgba(0,240,255,0.20)",
    "grid":         "rgba(255,255,255,0.05)",
}

LAYOUT_DEFAULTS = dict(
    font=dict(
        family="'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        size=12,
        color=PALETTE["text_primary"],
    ),
    plot_bgcolor=PALETTE["bg_card"],
    paper_bgcolor=PALETTE["bg_deep"],
    margin=dict(l=55, r=35, t=85, b=55),
    hoverlabel=dict(
        font=dict(family="'JetBrains Mono', monospace", size=12, color=PALETTE["white"]),
        bgcolor="#1A2540",
        bordercolor=PALETTE["cyan"],
    ),
    title_font=dict(size=15, color=PALETTE["cyan"],
                    family="'JetBrains Mono', monospace"),
)


def _axis(**overrides):
    """Standard axis styling."""
    base = dict(
        showgrid=True,
        gridcolor=PALETTE["grid"],
        gridwidth=1,
        zeroline=False,
        linecolor="rgba(0,240,255,0.15)",
        linewidth=1,
        ticks="outside",
        tickcolor=PALETTE["text_muted"],
        tickfont=dict(size=11, color=PALETTE["text_muted"]),
        title_font=dict(size=12, color=PALETTE["text_primary"]),
    )
    base.update(overrides)
    return base


def _add_projection_separator(fig: go.Figure) -> go.Figure:
    """Subtle vertical line marking FY25A->FY26E boundary on time-series charts.
    Uses add_shape directly (avoids add_vline incompatibility with categorical x)."""
    fig.add_shape(
        type="line",
        x0="FY25A", x1="FY25A",
        y0=0, y1=1,
        xref="x", yref="paper",
        line=dict(color="rgba(0,240,255,0.3)", width=1.5, dash="dot"),
    )
    fig.add_annotation(
        x="FY25A", y=1.02,
        xref="x", yref="paper",
        text="<b>Actual / Projection</b>",
        showarrow=False,
        font=dict(size=9, color="rgba(0,240,255,0.6)"),
        xanchor="center",
    )
    return fig


def _legend(**overrides):
    base = dict(
        font=dict(color=PALETTE["text_primary"], size=11),
        bgcolor="rgba(5,10,24,0.85)",
        bordercolor=PALETTE["border_dim"],
        borderwidth=1,
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
    )
    base.update(overrides)
    return base


# =============================================================================
# 1. VALUATION BRIDGE WATERFALL
# =============================================================================
def chart_valuation_bridge(dcf: Dict) -> go.Figure:
    ev = dcf["enterprise_value"]
    cash = dcf["cash"]
    debt = dcf["debt"]
    pref = dcf["preference"]
    eqv = dcf["equity_value"]

    fig = go.Figure(go.Waterfall(
        name="Valuation Bridge",
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Enterprise<br>Value", "(+) Cash", "(-) Total Debt",
           "(-) Preference<br>Capital", "Equity<br>Value"],
        y=[ev, cash, -debt, -pref, eqv],
        text=[f"{ev:,.0f}", f"+{cash:,.0f}", f"-{debt:,.0f}",
              f"-{pref:,.0f}", f"{eqv:,.0f}"],
        textposition="outside",
        textfont=dict(size=12, color=PALETTE["white"]),
        connector=dict(line=dict(color=PALETTE["border_mid"], width=1.5, dash="dot")),
        increasing=dict(marker=dict(color=PALETTE["neon_green"],
                                    line=dict(color=PALETTE["bg_deep"], width=1))),
        decreasing=dict(marker=dict(color=PALETTE["neon_pink"],
                                    line=dict(color=PALETTE["bg_deep"], width=1))),
        totals=dict(marker=dict(color=PALETTE["cyan"],
                                line=dict(color=PALETTE["bg_deep"], width=1))),
    ))
    fig.update_layout(
        title=dict(text="<b>Enterprise Value to Equity Value Bridge</b><br>"
                        f"<sup style='color:{PALETTE['text_muted']};'>"
                        "FY25A close | INR Crores</sup>",
                   x=0.02, xanchor="left", y=0.96),
        yaxis_title="INR Crores",
        xaxis=_axis(showgrid=False, tickfont=dict(size=11, color=PALETTE["text_primary"])),
        yaxis=_axis(),
        showlegend=False,
        height=440,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 2. DCF COMPONENTS
# =============================================================================
def chart_dcf_components(dcf: Dict) -> go.Figure:
    fcff_df = dcf["fcff"]
    years = list(fcff_df.index) + ["Terminal<br>Value"]
    pv_vals = list(fcff_df["PV_FCFF"]) + [dcf["pv_terminal"]]
    colors = [PALETTE["cyan"]] * len(fcff_df) + [PALETTE["neon_purple"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=pv_vals,
        marker=dict(color=colors,
                    line=dict(color=PALETTE["bg_deep"], width=1.5)),
        text=[f"{v:,.0f}" for v in pv_vals],
        textposition="outside",
        textfont=dict(size=11, color=PALETTE["white"]),
        hovertemplate="<b>%{x}</b><br>PV: INR %{y:,.0f} Cr<extra></extra>",
        name="PV of FCFF",
    ))
    fig.add_hline(y=0, line=dict(color=PALETTE["text_muted"], width=1))

    fig.update_layout(
        title=dict(text="<b>DCF - Present Value Composition</b><br>"
                        f"<sup style='color:{PALETTE['text_muted']};'>"
                        f"Sum PV explicit: INR {dcf['sum_pv_fcff']:,.0f} Cr  |  "
                        f"PV Terminal: INR {dcf['pv_terminal']:,.0f} Cr  |  "
                        f"EV: INR {dcf['enterprise_value']:,.0f} Cr</sup>",
                   x=0.02, xanchor="left", y=0.96),
        xaxis=_axis(showgrid=False, tickfont=dict(size=10, color=PALETTE["text_primary"])),
        yaxis=_axis(title="INR Crores"),
        showlegend=False,
        height=440,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 3. WACC x g SENSITIVITY HEATMAP
# =============================================================================
def chart_wacc_sensitivity(sens_df: pd.DataFrame, current_wacc: float,
                           current_g: float) -> go.Figure:
    z = sens_df.values
    fig = go.Figure(go.Heatmap(
        z=z,
        x=sens_df.columns,
        y=sens_df.index,
        colorscale=[
            [0.0,  "#FF2D78"],
            [0.25, "#BF5FFF"],
            [0.50, "#FFB800"],
            [0.75, "#00FF9D"],
            [1.0,  "#00F0FF"],
        ],
        text=np.round(z, 0),
        texttemplate="%{text:,.0f}",
        textfont=dict(size=10, color=PALETTE["white"]),
        hovertemplate="WACC: %{y}<br>g: %{x}<br>Value/Share: INR %{z:,.0f}<extra></extra>",
        colorbar=dict(
            title=dict(text="INR / Share",
                       font=dict(size=11, color=PALETTE["cyan"])),
            thickness=14, len=0.85,
            tickfont=dict(size=10, color=PALETTE["text_primary"]),
            outlinecolor=PALETTE["border_dim"],
        ),
    ))
    fig.update_layout(
        title=dict(text="<b>Equity Value / Share - WACC x Terminal Growth</b><br>"
                        f"<sup style='color:{PALETTE['text_muted']};'>"
                        f"Current: WACC {current_wacc:.2%} | g {current_g:.2%}</sup>",
                   x=0.02, xanchor="left", y=0.97),
        xaxis=dict(title=dict(text="Terminal Growth Rate (g)",
                              font=dict(size=12, color=PALETTE["text_primary"])),
                   side="top",
                   tickfont=dict(size=10, color=PALETTE["text_muted"])),
        yaxis=dict(title=dict(text="WACC",
                              font=dict(size=12, color=PALETTE["text_primary"])),
                   autorange="reversed",
                   tickfont=dict(size=10, color=PALETTE["text_muted"])),
        height=480,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 4. TORNADO CHART
# =============================================================================
def chart_tornado(tornado_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=tornado_df["Driver"], x=tornado_df["Down"],
        orientation="h", name="Down (-)",
        marker=dict(color=PALETTE["neon_pink"],
                    line=dict(color=PALETTE["bg_deep"], width=1)),
        text=[f"{v:+.0f}" for v in tornado_df["Down"]],
        textposition="outside",
        textfont=dict(size=10, color=PALETTE["text_primary"]),
        hovertemplate="<b>%{y}</b><br>Down: INR %{x:+.0f}/share<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=tornado_df["Driver"], x=tornado_df["Up"],
        orientation="h", name="Up (+)",
        marker=dict(color=PALETTE["neon_green"],
                    line=dict(color=PALETTE["bg_deep"], width=1)),
        text=[f"{v:+.0f}" for v in tornado_df["Up"]],
        textposition="outside",
        textfont=dict(size=10, color=PALETTE["text_primary"]),
        hovertemplate="<b>%{y}</b><br>Up: INR %{x:+.0f}/share<extra></extra>",
    ))
    fig.add_vline(x=0, line=dict(color=PALETTE["text_muted"], width=1))

    fig.update_layout(
        title=dict(text="<b>Tornado - Driver Sensitivity (Value per Share)</b><br>"
                        f"<sup style='color:{PALETTE['text_muted']};'>"
                        "Sorted by impact range | INR per share</sup>",
                   x=0.02, xanchor="left", y=0.96),
        barmode="overlay",
        xaxis=_axis(title="INR / Share Impact"),
        yaxis=_axis(showgrid=False,
                    tickfont=dict(size=11, color=PALETTE["text_primary"])),
        legend=_legend(),
        height=440,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 5. MONTE CARLO HISTOGRAM
# =============================================================================
def chart_monte_carlo(evs: np.ndarray, base_ev: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=evs,
        nbinsx=40,
        marker=dict(color=PALETTE["cyan"],
                    line=dict(color=PALETTE["bg_deep"], width=1)),
        opacity=0.75,
        hovertemplate="EV: INR %{x:,.0f} Cr<br>Count: %{y}<extra></extra>",
    ))
    mean_ev = float(np.mean(evs))
    p5 = float(np.percentile(evs, 5))
    p95 = float(np.percentile(evs, 95))

    fig.add_vline(x=mean_ev, line=dict(color=PALETTE["neon_amber"],
                                       width=2, dash="dash"),
                  annotation_text=f"<b>Mean {mean_ev:,.0f}</b>",
                  annotation_position="top",
                  annotation_font=dict(color=PALETTE["neon_amber"], size=11))
    fig.add_vline(x=p5, line=dict(color=PALETTE["neon_pink"], width=2, dash="dot"),
                  annotation_text=f"P5 {p5:,.0f}",
                  annotation_position="top",
                  annotation_font=dict(color=PALETTE["neon_pink"], size=10))
    fig.add_vline(x=p95, line=dict(color=PALETTE["neon_green"], width=2, dash="dot"),
                  annotation_text=f"P95 {p95:,.0f}",
                  annotation_position="top",
                  annotation_font=dict(color=PALETTE["neon_green"], size=10))

    fig.update_layout(
        title=dict(text="<b>Monte Carlo - Enterprise Value Distribution</b><br>"
                        f"<sup style='color:{PALETTE['text_muted']};'>"
                        f"{len(evs)} simulations | Base EV: INR {base_ev:,.0f} Cr</sup>",
                   x=0.02, xanchor="left", y=0.96),
        xaxis=_axis(title="Enterprise Value (INR Cr)"),
        yaxis=_axis(title="Frequency"),
        showlegend=False,
        height=440,
        bargap=0.05,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 6. REVENUE & EBITDA TREND
# =============================================================================
def chart_revenue_ebitda_trend(income_df: pd.DataFrame,
                               pct_mode: bool = False) -> go.Figure:
    fig = go.Figure()

    if pct_mode:
        # YoY revenue growth bars
        pct = income_df["Net_Sales"].pct_change() * 100
        bar_colors = [PALETTE["neon_green"] if (v >= 0 and not pd.isna(v))
                      else PALETTE["neon_pink"] if not pd.isna(v)
                      else PALETTE["text_muted"]
                      for v in pct]
        fig.add_trace(go.Bar(
            x=income_df.index, y=pct,
            name="YoY Revenue Growth (%)",
            marker=dict(color=bar_colors,
                        line=dict(color=PALETTE["bg_deep"], width=1)),
            text=[f"{v:+.1f}%" if not pd.isna(v) else "" for v in pct],
            textposition="outside",
            textfont=dict(size=10, color=PALETTE["text_primary"]),
            yaxis="y", offsetgroup=1,
            hovertemplate="<b>%{x}</b><br>YoY: %{y:+.1f}%<extra></extra>",
        ))
        y_axis_title = "YoY Growth (%)"
    else:
        fig.add_trace(go.Bar(
            x=income_df.index, y=income_df["Net_Sales"],
            name="Net Sales (INR Cr)",
            marker=dict(color=PALETTE["cyan"],
                        line=dict(color=PALETTE["bg_deep"], width=1)),
            text=[f"{v:,.0f}" for v in income_df["Net_Sales"]],
            textposition="outside",
            textfont=dict(size=10, color=PALETTE["text_muted"]),
            yaxis="y", offsetgroup=1,
            hovertemplate="<b>%{x}</b><br>Revenue: INR %{y:,.0f} Cr<extra></extra>",
        ))
        y_axis_title = "Revenue (INR Cr)"

    fig.add_trace(go.Scatter(
        x=income_df.index, y=income_df["EBITDA_Margin"] * 100,
        name="EBITDA Margin (%)",
        mode="lines+markers+text",
        line=dict(color=PALETTE["neon_amber"], width=3),
        marker=dict(size=10, color=PALETTE["neon_amber"],
                    line=dict(color=PALETTE["bg_card"], width=2)),
        text=[f"{v * 100:.1f}%" for v in income_df["EBITDA_Margin"]],
        textposition="top center",
        textfont=dict(size=10, color=PALETTE["neon_amber"]),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>EBITDA Margin: %{y:.1f}%<extra></extra>",
    ))

    _add_projection_separator(fig)

    fig.update_layout(
        title=dict(
            text=("<b>Revenue & EBITDA Margin</b>" if not pct_mode
                  else "<b>YoY Revenue Growth & EBITDA Margin</b>"),
            x=0.02, xanchor="left", y=0.96),
        xaxis=_axis(showgrid=False,
                    tickfont=dict(size=11, color=PALETTE["text_primary"])),
        yaxis=_axis(title=y_axis_title),
        yaxis2=dict(title=dict(text="EBITDA Margin (%)",
                               font=dict(size=12, color=PALETTE["neon_amber"])),
                    overlaying="y", side="right",
                    showgrid=False, ticksuffix="%",
                    tickfont=dict(color=PALETTE["neon_amber"], size=11)),
        legend=_legend(),
        height=440,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 7. DEBT & COVERAGE
# =============================================================================
def chart_debt_coverage(ratios_df: pd.DataFrame, balance_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ratios_df.index, y=ratios_df["Net_Debt"],
        name="Net Debt (INR Cr)",
        marker=dict(
            color=[PALETTE["neon_pink"] if v > 0 else PALETTE["neon_green"]
                   for v in ratios_df["Net_Debt"]],
            line=dict(color=PALETTE["bg_deep"], width=1),
        ),
        text=[f"{v:,.0f}" for v in ratios_df["Net_Debt"]],
        textposition="outside",
        textfont=dict(size=10, color=PALETTE["text_muted"]),
        yaxis="y",
        hovertemplate="<b>%{x}</b><br>Net Debt: INR %{y:,.0f} Cr<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=ratios_df.index, y=ratios_df["DSCR"],
        name="DSCR (x)",
        mode="lines+markers",
        line=dict(color=PALETTE["cyan"], width=3),
        marker=dict(size=10, color=PALETTE["cyan"],
                    line=dict(color=PALETTE["bg_card"], width=2)),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>DSCR: %{y:.2f}x<extra></extra>",
    ))
    fig.add_hline(y=1.20, line=dict(color=PALETTE["neon_amber"], width=2, dash="dash"),
                  yref="y2",
                  annotation_text="<b>Covenant Floor: 1.20x</b>",
                  annotation_position="bottom right",
                  annotation_font=dict(color=PALETTE["neon_amber"], size=10))
    _add_projection_separator(fig)

    fig.update_layout(
        title=dict(text="<b>Debt Profile & Coverage</b><br>"
                        f"<sup style='color:{PALETTE['text_muted']};'>"
                        "Net Debt trajectory + DSCR vs covenant floor</sup>",
                   x=0.02, xanchor="left", y=0.96),
        xaxis=_axis(showgrid=False,
                    tickfont=dict(size=11, color=PALETTE["text_primary"])),
        yaxis=_axis(title="Net Debt (INR Cr)"),
        yaxis2=dict(title=dict(text="DSCR (x)",
                               font=dict(size=12, color=PALETTE["cyan"])),
                    overlaying="y", side="right",
                    showgrid=False, ticksuffix="x",
                    tickfont=dict(color=PALETTE["cyan"], size=11)),
        legend=_legend(),
        height=440,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 8. CASH FLOW BUILD
# =============================================================================
def chart_cashflow_build(cfs_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cfs_df.index, y=cfs_df["CFO"], name="CFO (Operations)",
        marker=dict(color=PALETTE["neon_green"],
                    line=dict(color=PALETTE["bg_deep"], width=1)),
        hovertemplate="<b>%{x}</b><br>CFO: INR %{y:,.0f} Cr<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=cfs_df.index, y=cfs_df["CFI"], name="CFI (Investing)",
        marker=dict(color=PALETTE["neon_amber"],
                    line=dict(color=PALETTE["bg_deep"], width=1)),
        hovertemplate="<b>%{x}</b><br>CFI: INR %{y:,.0f} Cr<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=cfs_df.index, y=cfs_df["CFF"], name="CFF (Financing)",
        marker=dict(color=PALETTE["neon_pink"],
                    line=dict(color=PALETTE["bg_deep"], width=1)),
        hovertemplate="<b>%{x}</b><br>CFF: INR %{y:,.0f} Cr<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cfs_df.index, y=cfs_df["Closing_Cash"],
        name="Closing Cash",
        mode="lines+markers+text",
        line=dict(color=PALETTE["cyan"], width=3.5),
        marker=dict(size=11, color=PALETTE["cyan"],
                    line=dict(color=PALETTE["bg_card"], width=2)),
        text=[f"{v:,.0f}" for v in cfs_df["Closing_Cash"]],
        textposition="top center",
        textfont=dict(size=10, color=PALETTE["cyan"]),
        hovertemplate="<b>%{x}</b><br>Closing Cash: INR %{y:,.0f} Cr<extra></extra>",
    ))
    _add_projection_separator(fig)

    fig.update_layout(
        title=dict(text="<b>Cash Flow Build & Liquidity</b>",
                   x=0.02, xanchor="left", y=0.96),
        barmode="relative",
        xaxis=_axis(showgrid=False,
                    tickfont=dict(size=11, color=PALETTE["text_primary"])),
        yaxis=_axis(title="INR Crores"),
        legend=_legend(),
        height=460,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 9. REVENUE MIX
# =============================================================================
def chart_revenue_mix(revenue_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=revenue_df.index, y=revenue_df["Coke_Revenue"],
        name="Coke Revenue",
        mode="lines",
        line=dict(width=0.5, color=PALETTE["cyan"]),
        stackgroup="one", fillcolor="rgba(0,240,255,0.65)",
        hovertemplate="<b>%{x}</b><br>Coke: INR %{y:,.0f} Cr<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=revenue_df.index, y=revenue_df["COG_Revenue"],
        name="COG Revenue",
        mode="lines",
        line=dict(width=0.5, color=PALETTE["neon_purple"]),
        stackgroup="one", fillcolor="rgba(191,95,255,0.65)",
        hovertemplate="<b>%{x}</b><br>COG: INR %{y:,.0f} Cr<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=revenue_df.index, y=revenue_df["Tar_Revenue"],
        name="Coal Tar Revenue",
        mode="lines",
        line=dict(width=0.5, color=PALETTE["neon_amber"]),
        stackgroup="one", fillcolor="rgba(255,184,0,0.65)",
        hovertemplate="<b>%{x}</b><br>Coal Tar: INR %{y:,.0f} Cr<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="<b>Revenue Mix by Product</b>",
                   x=0.02, xanchor="left", y=0.96),
        xaxis=_axis(showgrid=False,
                    tickfont=dict(size=11, color=PALETTE["text_primary"])),
        yaxis=_axis(title="INR Crores"),
        legend=_legend(),
        height=400,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 10. COVENANT STRESS SWEEP
# =============================================================================
def chart_covenant_stress(sweep: dict) -> go.Figure:
    x = sweep["driver_values"]
    y = sweep["min_dscr_series"]
    floor = sweep["covenant_floor"]
    breach = sweep["breach_value"]
    key = sweep["driver_key"]

    label_map = {
        "interest_rate":    "Interest Rate",
        "cogs_pct":         "COGS % of Sales",
        "cob2_util_steady": "COB-2 Utilization",
    }
    x_label = label_map.get(key, key)
    x_fmt = [f"{v:.1%}" for v in x]

    fig = go.Figure()

    if breach is not None:
        # Find index of first breach point
        try:
            idx = next(i for i, v in enumerate(x) if v >= breach)
            fig.add_shape(
                type="rect",
                x0=x_fmt[idx], x1=x_fmt[-1],
                y0=0, y1=1,
                xref="x", yref="paper",
                fillcolor="rgba(255,45,120,0.07)",
                line_width=0,
                layer="below",
            )
            fig.add_annotation(
                x=x_fmt[-1], y=0.98,
                xref="x", yref="paper",
                text="<b>Breach Zone</b>",
                showarrow=False,
                font=dict(color=PALETTE["neon_pink"], size=11),
                xanchor="right", yanchor="top",
            )
        except (StopIteration, IndexError):
            pass

    fig.add_trace(go.Scatter(
        x=x_fmt, y=y,
        mode="lines+markers",
        name="Min DSCR",
        line=dict(color=PALETTE["cyan"], width=3),
        marker=dict(size=7, color=PALETTE["cyan"],
                    line=dict(color=PALETTE["bg_card"], width=1.5)),
        hovertemplate="<b>%{x}</b><br>Min DSCR: %{y:.2f}x<extra></extra>",
    ))

    fig.add_hline(y=floor, line=dict(color=PALETTE["neon_amber"], width=2, dash="dash"),
                  annotation_text=f"<b>Covenant Floor {floor:.2f}x</b>",
                  annotation_position="bottom right",
                  annotation_font=dict(color=PALETTE["neon_amber"], size=11))

    if breach is not None:
        breach_label = f"{breach:.1%}"
        fig.add_shape(
            type="line",
            x0=breach_label, x1=breach_label,
            y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color=PALETTE["neon_pink"], width=2, dash="dot"),
        )
        fig.add_annotation(
            x=breach_label, y=0.95,
            xref="x", yref="paper",
            text=f"<b>Breach {breach:.2%}</b><br><sub>{sweep['breach_year']}</sub>",
            showarrow=False,
            font=dict(color=PALETTE["neon_pink"], size=11),
            xanchor="left", yanchor="top",
        )

    breach_msg = (f"Breach at {breach:.2%} ({sweep['breach_year']})"
                  if breach is not None else "No breach in sweep range")
    fig.update_layout(
        title=dict(text=f"<b>Covenant Stress - Min DSCR vs {x_label}</b><br>"
                        f"<sup style='color:{PALETTE['text_muted']};'>"
                        f"{breach_msg}</sup>",
                   x=0.02, xanchor="left", y=0.96),
        xaxis=_axis(title=x_label, showgrid=False,
                    tickfont=dict(size=10, color=PALETTE["text_muted"])),
        yaxis=_axis(title="Minimum DSCR (x)", ticksuffix="x"),
        showlegend=False,
        height=400,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 11. FINANCIAL HEALTH RADAR
# =============================================================================
def chart_health_radar(ratios_dict: Dict[str, pd.DataFrame],
                       year: str = "FY29E") -> go.Figure:
    """Polar/radar chart: 5 financial health axes for one or more scenarios."""
    AXES = [
        ("EBITDA Margin",   "EBITDA_Margin",      0.05,  0.25),
        ("DSCR",            "DSCR",               1.0,   4.0),
        ("ROCE",            "ROCE",               0.08,  0.25),
        ("Interest Cover",  "Interest_Coverage",  3.0,   15.0),
        ("Current Ratio",   "Current_Ratio",      1.0,   3.0),
    ]
    categories = [a[0] for a in AXES] + [AXES[0][0]]

    SCEN_COLORS = {
        "Bull": PALETTE["neon_green"],
        "Base": PALETTE["cyan"],
        "Bear": PALETTE["neon_pink"],
    }
    SCEN_FILLS = {
        "Bull": "rgba(0,255,157,0.18)",
        "Base": "rgba(0,240,255,0.18)",
        "Bear": "rgba(255,45,120,0.18)",
    }

    fig = go.Figure()
    for scn_name, rat_df in ratios_dict.items():
        if year not in rat_df.index:
            continue
        row = rat_df.loc[year]
        scores = []
        for _, col, lo, hi in AXES:
            try:
                raw = float(row[col])
                score = max(0.0, min(10.0, (raw - lo) / (hi - lo) * 10))
            except Exception:
                score = 0.0
            scores.append(round(score, 2))
        scores.append(scores[0])

        color = SCEN_COLORS.get(scn_name, PALETTE["neon_purple"])
        fill = SCEN_FILLS.get(scn_name, "rgba(191,95,255,0.18)")
        fig.add_trace(go.Scatterpolar(
            r=scores,
            theta=categories,
            fill="toself",
            name=scn_name,
            line=dict(color=color, width=2),
            fillcolor=fill,
            marker=dict(size=7, color=color),
            hovertemplate=("<b>" + scn_name + " - " + year + "</b><br>"
                           "%{theta}: %{r:.1f}/10<extra></extra>"),
        ))

    fig.update_layout(
        polar=dict(
            bgcolor=PALETTE["bg_card"],
            radialaxis=dict(
                visible=True, range=[0, 10],
                tickfont=dict(size=9, color=PALETTE["text_muted"]),
                gridcolor=PALETTE["grid"],
                linecolor=PALETTE["border_dim"],
                tickvals=[2, 4, 6, 8, 10],
            ),
            angularaxis=dict(
                tickfont=dict(size=11, color=PALETTE["text_primary"]),
                gridcolor=PALETTE["grid"],
                linecolor=PALETTE["border_dim"],
            ),
        ),
        title=dict(
            text=f"<b>Financial Health Radar - {year}</b><br>"
                 f"<sup style='color:{PALETTE['text_muted']};'>"
                 "0 = weak, 10 = strong (vs JCL benchmarks)</sup>",
            x=0.5, xanchor="center", y=0.97,
        ),
        legend=dict(font=dict(color=PALETTE["text_primary"], size=11),
                    bgcolor="rgba(5,10,24,0.85)",
                    bordercolor=PALETTE["border_dim"]),
        height=450,
        paper_bgcolor=PALETTE["bg_deep"],
        font=dict(family="'JetBrains Mono', monospace",
                  color=PALETTE["text_primary"]),
    )
    return fig


# =============================================================================
# 12. SCENARIO OVERLAY (used in Scenario Compare tab)
# =============================================================================
def chart_scenario_overlay(all_scen_results: Dict[str, dict]) -> go.Figure:
    SCEN_COLORS = {
        "Bull": PALETTE["neon_green"],
        "Base": PALETTE["cyan"],
        "Bear": PALETTE["neon_pink"],
    }
    fig = go.Figure()
    for sname, scol in SCEN_COLORS.items():
        if sname not in all_scen_results:
            continue
        inc = all_scen_results[sname]["income"]
        rat = all_scen_results[sname]["ratios"]
        dash = "solid" if sname == "Base" else "dot"
        fig.add_trace(go.Scatter(
            x=inc.index, y=inc["EBITDA_Margin"] * 100,
            name=f"{sname} EBITDA %",
            mode="lines+markers",
            line=dict(color=scol, width=2.5 if sname == "Base" else 1.8, dash=dash),
            marker=dict(size=8, color=scol,
                        line=dict(color=PALETTE["bg_deep"], width=1.5)),
            hovertemplate=(f"<b>{sname} %{{x}}</b><br>"
                           "EBITDA Margin: %{y:.1f}%<extra></extra>"),
            yaxis="y",
        ))
        fig.add_trace(go.Bar(
            x=rat.index, y=rat["Net_Debt"],
            name=f"{sname} Net Debt",
            marker=dict(color=scol, opacity=0.22,
                        line=dict(color=scol, width=1)),
            hovertemplate=(f"<b>{sname} %{{x}}</b><br>"
                           "Net Debt: INR %{y:,.0f} Cr<extra></extra>"),
            yaxis="y2",
        ))
    _add_projection_separator(fig)

    fig.update_layout(
        title=dict(text="<b>Scenario Overlay - EBITDA Margin & Net Debt</b>",
                   x=0.02, xanchor="left", y=0.96),
        barmode="group",
        yaxis=_axis(title="EBITDA Margin (%)", ticksuffix="%"),
        yaxis2=dict(title=dict(text="Net Debt (INR Cr)",
                               font=dict(size=12, color=PALETTE["text_primary"])),
                    overlaying="y", side="right",
                    showgrid=False,
                    tickfont=dict(color=PALETTE["text_muted"], size=11)),
        xaxis=_axis(showgrid=False,
                    tickfont=dict(size=11, color=PALETTE["text_primary"])),
        legend=_legend(),
        height=440,
        **LAYOUT_DEFAULTS,
    )
    return fig


# =============================================================================
# 13. KPI MINI SPARKLINES (tiny Plotly traces for KPI cards)
# =============================================================================
def chart_kpi_sparkline(values: List[float], color: str = "#00F0FF") -> go.Figure:
    """Tiny line chart for embedding in a KPI card. No axes, no legend."""
    clean = [(i, v) for i, v in enumerate(values)
             if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if len(clean) < 2:
        return go.Figure().update_layout(height=50,
                                         paper_bgcolor="rgba(0,0,0,0)",
                                         plot_bgcolor="rgba(0,0,0,0)")
    xs, ys = zip(*clean)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(xs), y=list(ys),
        mode="lines",
        line=dict(color=color, width=2, shape="spline"),
        fill="tozeroy",
        fillcolor=color.replace(")", ",0.18)").replace("rgb", "rgba")
                  if color.startswith("rgb") else "rgba(0,240,255,0.15)",
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=44,
        margin=dict(l=0, r=0, t=2, b=2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True,
                   range=[min(ys) - abs(min(ys)) * 0.1 - 0.01,
                          max(ys) + abs(max(ys)) * 0.1 + 0.01]),
        showlegend=False,
        hovermode=False,
    )
    return fig
