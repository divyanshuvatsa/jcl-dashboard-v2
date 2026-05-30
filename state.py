"""
state.py - Session-state utilities for the JCL dashboard
=========================================================
URL query-param round-tripping and named scenario snapshot management.
Pure Streamlit + Python stdlib. No external dependencies.
"""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

from engine import SCENARIO_PRESETS


# =============================================================================
# URL query param helpers
# =============================================================================
def encode_assumptions_to_url(assumptions: Dict, scenario: str) -> None:
    """Write non-default assumptions and scenario name to URL query params."""
    base = SCENARIO_PRESETS["Base"]
    params: Dict[str, str] = {"scenario": scenario}
    for k, v in assumptions.items():
        bv = base.get(k)
        try:
            if bv is not None and abs(float(v) - float(bv)) > 1e-8:
                params[k] = f"{float(v):.8g}"
        except (TypeError, ValueError):
            continue
    try:
        st.query_params.clear()
        for k, v in params.items():
            st.query_params[k] = v
    except Exception:
        # Fail silently if Streamlit version doesn't support full API
        pass


def restore_assumptions_from_url() -> bool:
    """Restore scenario + assumptions from URL params on first load.
    Returns True if anything was applied."""
    try:
        params = dict(st.query_params)
    except Exception:
        return False
    if not params:
        return False

    changed = False
    base = SCENARIO_PRESETS["Base"].copy()

    if "scenario" in params:
        scn = params["scenario"]
        if scn in SCENARIO_PRESETS:
            st.session_state.scenario = scn
            st.session_state.assumptions = SCENARIO_PRESETS[scn].copy()
            changed = True
        elif scn == "Custom":
            st.session_state.scenario = "Custom"
            changed = True

    for k in base:
        if k in params:
            try:
                st.session_state.assumptions[k] = float(params[k])
                changed = True
            except (ValueError, TypeError):
                continue

    return changed


# =============================================================================
# Saved snapshot slots
# =============================================================================
MAX_SLOTS = 5


def save_snapshot(name: str, assumptions: Dict) -> str:
    """Save current assumptions under a name. Returns the actual saved name."""
    safe = (name or "").strip() or f"Slot {len(st.session_state.saved_slots) + 1}"
    if len(st.session_state.saved_slots) >= MAX_SLOTS \
            and safe not in st.session_state.saved_slots:
        # FIFO eviction
        oldest = next(iter(st.session_state.saved_slots))
        del st.session_state.saved_slots[oldest]
    st.session_state.saved_slots[safe] = assumptions.copy()
    return safe


def load_snapshot(name: str) -> Optional[Dict]:
    """Restore a saved snapshot. Returns the loaded dict or None."""
    snap = st.session_state.saved_slots.get(name)
    if snap is None:
        return None
    st.session_state.assumptions = snap.copy()
    st.session_state.scenario = "Custom"
    return snap


def delete_snapshot(name: str) -> None:
    if name in st.session_state.saved_slots:
        del st.session_state.saved_slots[name]
