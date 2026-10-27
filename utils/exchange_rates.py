"""
Exchange rate functions for currency conversion.
"""
import math

import streamlit as st
import pandas as pd
import yfinance as yf
from config import PRICE_CACHE_TTL


@st.cache_data(ttl=PRICE_CACHE_TTL)
def get_exchange_rate_history(base_currency, target_currency, period="max", refresh_key=0):
    """
    Downloads the historical exchange rate.

    Args:
        base_currency: The base currency code (e.g., 'EUR')
        target_currency: The target currency code (e.g., 'USD')
        period: The historical period to fetch (default: 'max')
        refresh_key: Change this to bypass the cache, same as price refresh

    Returns:
        pandas.Series with Date index and rate values, or None if unavailable
    """
    del refresh_key  # Part of the cache key; not used in the function body.

    if base_currency == target_currency:
        return None

    try:
        pair = f"{base_currency}{target_currency}=X"
        hist = yf.Ticker(pair).history(period=period)

        if not hist.empty and 'Close' in hist.columns:
            close = hist['Close'].dropna()
            if not close.empty:
                return close

        pair_inv = f"{target_currency}{base_currency}=X"
        hist_inv = yf.Ticker(pair_inv).history(period=period)

        if not hist_inv.empty and 'Close' in hist_inv.columns:
            close_inv = hist_inv['Close'].dropna()
            close_inv = close_inv[close_inv != 0]
            if not close_inv.empty:
                return 1.0 / close_inv
    except Exception as e:
        print(f"Error downloading {base_currency}/{target_currency}: {e}")

    return None


def get_rate_at_date(rates_series, date_obj):
    """
    Retrieves the exchange rate for a specific date from the historical series.
    Uses the last available rate on or before that date.

    Args:
        rates_series: pandas.Series with historical exchange rates
        date_obj: The date to look up

    Returns:
        float: The exchange rate at the specified date, or None if not found
    """
    if rates_series is None or len(rates_series) == 0:
        return None

    try:
        ts = pd.Timestamp(date_obj)
        index_tz = getattr(rates_series.index, "tz", None)
        if ts.tzinfo is None and index_tz is not None:
            ts = ts.tz_localize(index_tz, nonexistent="shift_forward", ambiguous="NaT")
        elif ts.tzinfo is not None and index_tz is None:
            ts = ts.tz_convert(None)

        idx = rates_series.index.get_indexer([ts], method='pad')[0]
        if idx == -1:
            value = rates_series.iloc[0]
        else:
            value = rates_series.iloc[idx]

        if pd.isna(value):
            return None
        rate = float(value)
        if not math.isfinite(rate) or rate <= 0:
            return None
        return rate
    except Exception:
        return None
