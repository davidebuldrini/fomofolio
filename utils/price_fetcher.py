"""
Price fetching functions for stock data.
"""
import streamlit as st
import pandas as pd
import yfinance as yf
from config import PRICE_CACHE_TTL


@st.cache_data(ttl=PRICE_CACHE_TTL)
def get_current_prices(tickers, _refresh_key=None):
    """
    Downloads current prices for a list of tickers.
    Uses a 5-day period to avoid weekend/holiday issues.
    
    Args:
        tickers: List of ticker symbols
        _refresh_key: Dummy parameter to force cache refresh
    
    Returns:
        dict: Dictionary mapping ticker symbols to current prices
    """
    if not tickers:
        return {}
    
    try:
        # Batch download
        # period="5d" to have margin if today has no data
        data = yf.download(tickers, period="5d", group_by='ticker', progress=False)
        prices = {}
        
        # Handle single ticker vs multiple
        if len(tickers) == 1:
            t = tickers[0]
            try:
                # yfinance returns DataFrame if MultiIndex or Series/DF depending on version
                # Safe access: data['Close']
                series = data['Close']
                
                # Handling multi-level column if necessary (usually not for single ticker standard download)
                # If series is DF for some reason
                if isinstance(series, pd.DataFrame):
                    # Fallback
                    series = series.iloc[:, 0]
                
                # Take last non-NA value
                last_valid = series.dropna()
                if not last_valid.empty:
                    prices[t] = last_valid.iloc[-1]
                else:
                    prices[t] = 0.0
            except:
                prices[t] = 0.0
        else:
            for t in tickers:
                try:
                    if t in data.columns:  # Top level ticker check
                        series = data[t]['Close']
                    else:
                        # Fallback if different structure, but with group_by='ticker' it should be like this
                        prices[t] = 0.0
                        continue
                        
                    last_valid = series.dropna()
                    if not last_valid.empty:
                        prices[t] = last_valid.iloc[-1]
                    else:
                        prices[t] = 0.0
                except:
                    prices[t] = 0.0
        return prices
    except Exception as e:
        # Log the error but don't block everything
        print(f"Error downloading prices: {e}")
        return {}
