"""
Price fetching functions for stock data.
"""
import math

import streamlit as st
import pandas as pd
import yfinance as yf
from config import PRICE_CACHE_TTL


def _quote_to_major_units(ticker, price):
    """
    Yahoo quotes London listings (.L) in pence. The portfolio records GBP in pounds.
    """
    if price is None or pd.isna(price):
        return None
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    if str(ticker).upper().endswith('.L'):
        value = value / 100.0
    return value


def _last_close(series):
    if series is None:
        return None
    if isinstance(series, pd.DataFrame):
        if series.empty:
            return None
        series = series.iloc[:, 0]
    cleaned = series.dropna()
    if cleaned.empty:
        return None
    return cleaned.iloc[-1]


def _extract_close(data, ticker, single):
    """Read the latest Close whether yfinance used flat or multi-level columns."""
    if data is None or getattr(data, "empty", True):
        return None
    columns = data.columns
    candidates = []
    if single and 'Close' in columns:
        candidates.append(data['Close'])
    if isinstance(columns, pd.MultiIndex):
        for key in ((ticker, 'Close'), ('Close', ticker)):
            if key in columns:
                candidates.append(data[key])
    if not single and ticker in columns:
        block = data[ticker]
        if isinstance(block, pd.DataFrame) and 'Close' in block.columns:
            candidates.append(block['Close'])
        elif isinstance(block, pd.Series):
            candidates.append(block)
    for series in candidates:
        raw = _last_close(series)
        if raw is not None:
            return raw
    return None


@st.cache_data(ttl=PRICE_CACHE_TTL)
def get_current_prices(tickers, refresh_key=0):
    """
    Downloads current prices for a list of tickers.
    Uses a 5-day period to avoid weekend/holiday issues.

    Missing quotes are omitted. Callers must treat a missing ticker as
    unavailable, not as a price of zero.

    Args:
        tickers: List of ticker symbols
        refresh_key: Change this to bypass the cache

    Returns:
        dict: Ticker symbols mapped to the latest price, in major currency units
    """
    del refresh_key  # Part of the cache key; not used in the function body.

    if not tickers:
        return {}

    try:
        data = yf.download(tickers, period="5d", group_by='ticker', progress=False)
    except Exception as e:
        print(f"Error downloading prices: {e}")
        return {}

    prices = {}
    single = len(tickers) == 1
    for ticker in tickers:
        try:
            raw = _extract_close(data, ticker, single)
        except Exception:
            raw = None
        normalized = _quote_to_major_units(ticker, raw)
        if normalized is not None:
            prices[ticker] = normalized
    return prices
