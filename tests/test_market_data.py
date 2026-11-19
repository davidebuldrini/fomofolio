import datetime as dt

import pandas as pd

from utils.exchange_rates import get_latest_rate, get_rate_at_date
from utils.price_fetcher import to_major_units


def _series(start, values):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq='D'), dtype='float64')


def test_rate_on_or_before_date():
    s = _series('2024-01-01', [1.0, 2.0, 3.0])
    assert get_rate_at_date(s, dt.date(2024, 1, 2)) == 2.0
    assert get_rate_at_date(s, dt.date(2024, 1, 5)) == 3.0


def test_rate_before_series_start_is_none():
    s = _series('2024-01-01', [1.0, 2.0])
    assert get_rate_at_date(s, dt.date(2023, 12, 31)) is None


def test_rate_too_far_after_last_quote_is_none():
    s = _series('2024-01-01', [1.0])
    assert get_rate_at_date(s, dt.date(2024, 3, 1)) is None


def test_latest_rate():
    assert get_latest_rate(_series('2024-01-01', [1.0, float('nan')])) == 1.0
    assert get_latest_rate(None) is None


def test_minor_units():
    assert to_major_units(1234.0, 'GBp') == (12.34, 'GBP')
    assert to_major_units(50.0, 'USD') == (50.0, 'USD')
    assert to_major_units(50.0, None) == (50.0, None)
    assert to_major_units(-1, 'USD') == (None, None)
