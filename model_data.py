"""
model_data.py — calibration data for the JCL engine.

Loads the Base-scenario "golden" model (jcl_base_model.json) that was extracted
verbatim from JCL_Financial_Model_EXP.xlsx. The engine uses these series as the
exogenous schedule inputs (depreciation, interest cascade, debt schedule,
working-capital days base, FY24A/FY25A actuals, balance-sheet schedule items,
dividend/buyback profile) so that, at the Base preset, every line the dashboard
displays reproduces the Excel to full precision.

A single JSON keeps the package self-contained for Streamlit Cloud while letting
`excel_loader.regenerate_base_model()` refresh it from any updated workbook.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_JSON = os.path.join(_HERE, "jcl_base_model.json")

PROJECTION_YEARS: List[str] = [
    "FY25A", "FY26E", "FY27E", "FY28E", "FY29E",
    "FY30E", "FY31E", "FY32E", "FY33E",
]
VALUED_YEARS: List[str] = PROJECTION_YEARS[1:]  # FY26E..FY33E
HISTORICAL_YEAR = "FY24A"
ALL_YEARS: List[str] = [HISTORICAL_YEAR] + PROJECTION_YEARS


@lru_cache(maxsize=1)
def base_model() -> Dict:
    """The full Base-scenario golden model, exactly as in the source workbook."""
    with open(_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def series(section: str, line: str) -> Dict[str, float]:
    """Return a {year: value} dict for one line of the golden Base model."""
    return dict(base_model()[section][line])


def scalar(section: str, key: str) -> float:
    return base_model()[section][key]
