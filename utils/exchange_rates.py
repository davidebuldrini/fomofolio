"""
Exchange rate functions for currency conversion.
"""
import streamlit as st
import pandas as pd
import yfinance as yf


@st.cache_data
def get_exchange_rate_history(base_currency, target_currency, period="max"):
    """
    Downloads the historical exchange rate.
    
    Args:
        base_currency: The base currency code (e.g., 'EUR')
        target_currency: The target currency code (e.g., 'USD')
        period: The historical period to fetch (default: 'max')
    
    Returns:
        pandas.Series with Date index and rate values, or None if same currency
    """
    if base_currency == target_currency:
        return None
    
    # Try direct combination (e.g. EURUSD=X)
    pair = f"{base_currency}{target_currency}=X"
    ticker = yf.Ticker(pair)
    hist = ticker.history(period=period)
    
    if not hist.empty:
        return hist['Close']
    
    # Try inverse combination (e.g. USDEUR=X)
    pair_inv = f"{target_currency}{base_currency}=X"
    ticker_inv = yf.Ticker(pair_inv)
    hist_inv = ticker_inv.history(period=period)
    
    if not hist_inv.empty:
        return 1.0 / hist_inv['Close']
        
    return None


def get_rate_at_date(rates_series, date_obj):
    """
    Retrieves the exchange rate for a specific date from the historical series.
    Uses the 'asof' method or the closest value.
    
    Args:
        rates_series: pandas.Series with historical exchange rates
        date_obj: The date to look up
    
    Returns:
        float: The exchange rate at the specified date, or 1.0 if not found
    """
    if rates_series is None:
        return 1.0
        
    # Ensure date_obj is compatible with the index (tz-naive vs tz-aware)
    # yfinance often returns tz-aware (UTC). Convert date_obj to tz-naive timestamp for simplicity or vice versa.
    # Simple approach: convert series index to date (without time/tz)
    
    try:
        # Look for the exact date or the previous available one
        ts = pd.Timestamp(date_obj)
        if ts.tzinfo is None and rates_series.index.tz is not None:
            ts = ts.tz_localize(rates_series.index.tz)
        
        # asof finds the last valid value up to that date
        idx = rates_series.index.get_indexer([ts], method='pad')[0]
        if idx == -1:
            # If the date is before the first data point, take the first
            return rates_series.iloc[0]
        return rates_series.iloc[idx]
    except Exception as e:
        # Fallback in case of error
        return 1.0
