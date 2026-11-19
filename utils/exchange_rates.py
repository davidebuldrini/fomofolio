"""
Exchange rate functions for currency conversion.
"""
import logging
import math

import streamlit as st
import pandas as pd
import yfinance as yf
from config import CACHE_MAX_ENTRIES, FX_MAX_GAP_DAYS, PRICE_CACHE_TTL

logger = logging.getLogger(__name__)


def _clean_close(hist):
    if hist is None or hist.empty or 'Close' not in hist.columns:
        return None
    close = pd.to_numeric(hist['Close'], errors='coerce').dropna()
    close = close[close > 0]
    if close.empty:
        return None
    # Daily FX bars: keep only the date so lookups never depend on time zones.
    index = close.index
    if getattr(index, 'tz', None) is not None:
        index = index.tz_localize(None)
    close.index = pd.DatetimeIndex(index).normalize()
    close = close[~close.index.duplicated(keep='last')].sort_index()
    return close


@st.cache_data(ttl=PRICE_CACHE_TTL, max_entries=CACHE_MAX_ENTRIES)
def get_exchange_rate_history(base_currency, target_currency, refresh_key=0):
    """
    Downloads the full daily exchange rate history (base -> target).

    The same series serves historical lookups and the live rate (its last
    value), so each currency pair is downloaded once per refresh.

    Args:
        base_currency: The base currency code (e.g., 'EUR')
        target_currency: The target currency code (e.g., 'USD')
        refresh_key: Change this to bypass the cache

    Returns:
        pandas.Series indexed by naive dates, or None if unavailable
    """
    del refresh_key  # Part of the cache key; not used in the function body.

    if base_currency == target_currency:
        return None

    try:
        direct = _clean_close(yf.Ticker(f"{base_currency}{target_currency}=X").history(period="max"))
        if direct is not None:
            return direct

        inverse = _clean_close(yf.Ticker(f"{target_currency}{base_currency}=X").history(period="max"))
        if inverse is not None:
            return 1.0 / inverse
    except Exception:
        logger.warning("Could not download %s/%s", base_currency, target_currency, exc_info=True)

    return None


def _valid_rate(value):
    if value is None or pd.isna(value):
        return None
    rate = float(value)
    if not math.isfinite(rate) or rate <= 0:
        return None
    return rate


def get_rate_at_date(rates_series, date_obj, max_gap_days=FX_MAX_GAP_DAYS):
    """
    Returns the rate on `date_obj`, or the last one before it.

    Returns None when the date is before the start of the series, or when the
    closest earlier quote is more than `max_gap_days` old, instead of
    silently using a rate from a very different date.
    """
    if rates_series is None or len(rates_series) == 0:
        return None

    try:
        ts = pd.Timestamp(date_obj)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        ts = ts.normalize()

        pos = rates_series.index.searchsorted(ts, side='right') - 1
        if pos < 0:
            return None
        if (ts - rates_series.index[pos]).days > max_gap_days:
            return None
        return _valid_rate(rates_series.iloc[pos])
    except Exception:
        logger.warning("Rate lookup failed for %s", date_obj, exc_info=True)
        return None


def get_latest_rate(rates_series):
    """The most recent valid rate in the series, or None."""
    if rates_series is None or len(rates_series) == 0:
        return None
    cleaned = rates_series.dropna()
    if cleaned.empty:
        return None
    return _valid_rate(cleaned.iloc[-1])
