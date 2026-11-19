"""
Numeric helpers shared by the core and the UI.
"""
import math

import pandas as pd


def is_missing(value):
    """True for None, NaN, infinities and anything that is not a finite number."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        # pd.isna on a list-like returns an array: not a usable scalar.
        return True
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return True
