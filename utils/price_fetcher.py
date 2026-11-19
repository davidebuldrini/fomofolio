"""
Price fetching functions for stock data.
"""
import logging
import math

import streamlit as st
import pandas as pd
import yfinance as yf
from config import (
    CACHE_MAX_ENTRIES,
    MINOR_UNIT_CURRENCIES,
    PRICE_CACHE_TTL,
    QUOTE_CURRENCY_CACHE_TTL,
)

logger = logging.getLogger(__name__)


def to_major_units(price, quote_currency):
    """
    Convert a raw Yahoo quote to the major currency unit.

    Returns:
        tuple: (price or None, major currency code or None)
    """
    if price is None or pd.isna(price):
        return None, None
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(value) or value <= 0:
        return None, None
    if not quote_currency:
        return value, None
    if quote_currency in MINOR_UNIT_CURRENCIES:
        major, divisor = MINOR_UNIT_CURRENCIES[quote_currency]
        return value / divisor, major
    return value, str(quote_currency).upper()


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


@st.cache_data(ttl=QUOTE_CURRENCY_CACHE_TTL, max_entries=CACHE_MAX_ENTRIES)
def get_quote_currency(ticker):
    """
    The currency Yahoo uses to quote `ticker`, as reported (e.g. 'USD', 'GBp').

    Returns None when Yahoo does not report it.
    """
    try:
        currency = yf.Ticker(ticker).fast_info['currency']
    except Exception:
        logger.warning("Could not read the quote currency of %s", ticker, exc_info=True)
        return None
    return str(currency) if currency else None


@st.cache_data(ttl=PRICE_CACHE_TTL, max_entries=CACHE_MAX_ENTRIES)
def _download_last_closes(tickers, refresh_key=0):
    del refresh_key  # Part of the cache key; not used in the function body.
    try:
        data = yf.download(list(tickers), period="5d", group_by='ticker', progress=False)
    except Exception:
        logger.warning("Price download failed for %s", ", ".join(tickers), exc_info=True)
        return {}

    closes = {}
    single = len(tickers) == 1
    for ticker in tickers:
        try:
            raw = _extract_close(data, ticker, single)
        except Exception:
            raw = None
        if raw is not None and not pd.isna(raw):
            closes[ticker] = float(raw)
    return closes


def get_current_prices(tickers, refresh_key=0):
    """
    Latest price for each ticker, in the major unit of its listing currency.

    Uses a 5-day window to cover weekends and holidays. Missing quotes are
    omitted: callers must treat a missing ticker as unavailable, not zero.

    Args:
        tickers: List of ticker symbols
        refresh_key: Change this to bypass the price cache

    Returns:
        dict: ticker -> {'price': float, 'currency': str or None}
            `currency` is the major currency code (pence quotes become GBP),
            or None when Yahoo does not report it.
    """
    tickers = tuple(sorted(set(tickers)))
    if not tickers:
        return {}

    closes = _download_last_closes(tickers, refresh_key=refresh_key)
    quotes = {}
    for ticker, raw in closes.items():
        quote_currency = get_quote_currency(ticker)
        if quote_currency is None and ticker.upper().endswith('.L'):
            # Most London listings are quoted in pence; assume so when Yahoo is silent.
            quote_currency = 'GBp'
        price, currency = to_major_units(raw, quote_currency)
        if price is not None:
            quotes[ticker] = {'price': price, 'currency': currency}
    return quotes
