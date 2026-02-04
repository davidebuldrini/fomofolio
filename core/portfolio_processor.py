"""
Portfolio processing logic for calculating positions, P&L, and FOMO metrics.
"""
import pandas as pd
from utils.exchange_rates import get_exchange_rate_history, get_rate_at_date
from utils.price_fetcher import get_current_prices


def process_portfolio(df, target_currency, refresh_key=0):
    """
    Calculates portfolio metrics, average cost, P&L, FOMO.
    Separates open positions from sales history.
    
    Args:
        df: DataFrame with transaction data
        target_currency: The base currency for portfolio calculations
        refresh_key: Parameter to force price refresh
    
    Returns:
        tuple: (df_open, df_closed, total_value, total_realized_pl, total_unrealized_pl)
            - df_open: DataFrame with open positions
            - df_closed: DataFrame with sales history
            - total_value: Total portfolio value
            - total_realized_pl: Total realized profit/loss
            - total_unrealized_pl: Total unrealized profit/loss
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0, 0.0

    df = df.sort_values(by='Date')
    
    holdings = {}  # {ticker: {'qty': 0, 'total_cost': 0, 'pmc': 0, 'currency': ''}}
    closed_positions = []  # List for sales history
    
    # Pre-fetch exchange rates for currencies involved
    currencies_in_use = df['Currency'].unique()
    rates_cache = {}
    for curr in currencies_in_use:
        if curr != target_currency:
            rates_cache[curr] = get_exchange_rate_history(curr, target_currency)
    
    total_realized_pl = 0.0
    
    # Process all transactions
    for index, row in df.iterrows():
        t = row['Ticker']
        qty = row['Qty']
        price_orig = row['Price']
        curr_orig = row['Currency']
        date_tx = row['Date']  # datetime.date
        
        # Setup holdings if new
        if t not in holdings:
            holdings[t] = {'qty': 0, 'total_cost': 0.0, 'pmc': 0.0}
            
        # Get Exchange Rate
        if curr_orig == target_currency:
            rate = 1.0
        else:
            rate_series = rates_cache.get(curr_orig)
            rate = get_rate_at_date(rate_series, date_tx)
            
        price_conv = price_orig * rate
        
        if row['Type'] == 'BUY':
            # Update weighted average cost
            prev_qty = holdings[t]['qty']
            prev_cost = holdings[t]['total_cost']
            
            # Additional cost
            add_cost = qty * price_conv
            
            new_qty = prev_qty + qty
            new_total_cost = prev_cost + add_cost
            
            holdings[t]['qty'] = new_qty
            holdings[t]['total_cost'] = new_total_cost
            holdings[t]['currency'] = curr_orig
            if new_qty > 0:
                holdings[t]['pmc'] = new_total_cost / new_qty
            
        elif row['Type'] == 'SELL':
            # Calculate Realized P&L using the average cost at time of sale
            pmc_at_sale = holdings[t]['pmc']
            proceeds = qty * price_conv
            cost_basis = qty * pmc_at_sale
            
            realized_pl = proceeds - cost_basis
            total_realized_pl += realized_pl
            
            # Record the sale in history
            closed_positions.append({
                'Date': date_tx,
                'Ticker': t,
                'Qty': qty,
                'Avg Price': price_orig,
                'Cost_Basis': pmc_at_sale,  # Average cost at time of sale
                'Proceeds': proceeds,  # Proceeds in base currency
                'Proceeds_Orig': price_orig * qty,  # Proceeds in original currency
                'Realized_PL': realized_pl,
                'Currency': curr_orig
            })
            
            # Update holding (reduce quantity and total cost proportionally)
            holdings[t]['qty'] -= qty
            holdings[t]['total_cost'] -= cost_basis
            
            # If qty goes to 0, reset total_cost
            if holdings[t]['qty'] <= 1e-9:
                holdings[t]['qty'] = 0
                holdings[t]['total_cost'] = 0.0
                holdings[t]['pmc'] = 0.0

    # --- Live Data ---
    active_tickers = [t for t, data in holdings.items() if data['qty'] > 0]
    sold_tickers = list(set([pos['Ticker'] for pos in closed_positions]))
    all_tickers_needed = list(set(active_tickers + sold_tickers))
    
    current_prices = get_current_prices(all_tickers_needed, _refresh_key=refresh_key)
    
    # Prepare exchange rates for live prices
    ticker_currencies = {}
    for t, data in holdings.items():
        if data.get('currency'):
            ticker_currencies[t] = data['currency']
    
    # Add currencies from sold tickers
    for pos in closed_positions:
        if pos['Ticker'] not in ticker_currencies:
            ticker_currencies[pos['Ticker']] = pos['Currency']
        
    rates_live_cache = {}
    for curr in set(ticker_currencies.values()):
        if curr != target_currency:
            rates_live_cache[curr] = get_exchange_rate_history(curr, target_currency, period="5d")
            
    # --- Build Open Positions Table ---
    df_open = _build_open_positions(
        active_tickers, holdings, current_prices, 
        ticker_currencies, rates_live_cache, target_currency
    )
    
    # --- Build Sales History Table ---
    df_closed = _build_sales_history(
        closed_positions, current_prices, 
        rates_live_cache, target_currency
    )
    
    # Calculate totals
    total_value = df_open['Current Value'].sum() if not df_open.empty else 0.0
    total_unrealized_pl = df_open['Unrealized P&L'].sum() if not df_open.empty else 0.0

    return df_open, df_closed, total_value, total_realized_pl, total_unrealized_pl


def _build_open_positions(active_tickers, holdings, current_prices, 
                          ticker_currencies, rates_live_cache, target_currency):
    """
    Build DataFrame for open positions.
    
    Args:
        active_tickers: List of tickers with open positions
        holdings: Dictionary of holdings data
        current_prices: Dictionary of current prices
        ticker_currencies: Dictionary mapping tickers to currencies
        rates_live_cache: Cache of live exchange rates
        target_currency: Base currency for calculations
    
    Returns:
        pandas.DataFrame: Open positions with P&L calculations
    """
    open_positions = []
    
    for t in active_tickers:
        qty = holdings[t]['qty']
        pmc = holdings[t]['pmc']
        curr_t = holdings[t]['currency']
        
        # Live price in original currency
        live_price_orig = current_prices.get(t, 0.0)
        
        # Conversion for totals
        if curr_t == target_currency:
            rate_live = 1.0
        else:
            rs = rates_live_cache.get(curr_t)
            rate_live = rs.iloc[-1] if rs is not None and not rs.empty else 1.0
             
        live_price_conv = live_price_orig * rate_live
        pmc_orig = pmc / rate_live  # Average cost in original currency
        
        market_value_conv = qty * live_price_conv
        unrealized_pl_conv = (live_price_conv - pmc) * qty
        
        # Values in original currency for display
        market_value_orig = qty * live_price_orig
        unrealized_pl_orig = (live_price_orig - pmc_orig) * qty
        pl_percent = ((live_price_orig - pmc_orig) / pmc_orig * 100) if pmc_orig > 0 else 0
        
        open_positions.append({
            'Ticker': t,
            'Qty': qty,
            'Avg Price': round(pmc_orig, 2),
            'Current Price': round(live_price_orig, 2),
            'Initial Value': round(pmc_orig * qty, 2),
            'Current Value': round(market_value_orig, 2),
            'Unrealized P&L': round(unrealized_pl_orig, 2),
            'Unrealized P&L %': round(pl_percent, 2),
            'Currency': curr_t
        })
        
    return pd.DataFrame(open_positions)


def _build_sales_history(closed_positions, current_prices, 
                         rates_live_cache, target_currency):
    """
    Build DataFrame for sales history with FOMO analysis.
    
    Args:
        closed_positions: List of closed position data
        current_prices: Dictionary of current prices
        rates_live_cache: Cache of live exchange rates
        target_currency: Base currency for calculations
    
    Returns:
        pandas.DataFrame: Sales history with FOMO calculations
    """
    for pos in closed_positions:
        t = pos['Ticker']
        qty = pos['Qty']
        curr_t = pos['Currency']
        proceeds_base = pos['Proceeds']
        
        # Live price
        live_price_orig = current_prices.get(t, 0.0)
        
        # Conversion for FOMO
        if curr_t == target_currency:
            rate_live = 1.0
        else:
            rs = rates_live_cache.get(curr_t)
            rate_live = rs.iloc[-1] if rs is not None and not rs.empty else 1.0
        
        # Value today in base currency
        value_today_conv = live_price_orig * rate_live * qty
        
        # Value today in original currency
        value_today_orig = live_price_orig * qty
        
        # FOMO: difference between today's value and original proceeds (in base currency)
        fomo = value_today_conv - proceeds_base
        
        pos['Current Price'] = round(live_price_orig, 2)
        pos['Value Today'] = round(value_today_orig, 2)
        pos['FOMO'] = round(fomo, 2)

    return pd.DataFrame(closed_positions)
