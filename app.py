import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="InvestTrack - Portfolio Tracker", layout="wide")

# --- Constants ---
CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY"]

# --- Helper Functions ---

@st.cache_data
def get_exchange_rate_history(base_currency, target_currency, period="max"):
    """
    Downloads the historical exchange rate.
    Returns a Series with Date index and rate values.
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

@st.cache_data(ttl=3600)
def get_current_prices(tickers, _refresh_key=None):
    """
    Downloads current prices for a list of tickers.
    Uses a 5-day period to avoid weekend/holiday issues.
    _refresh_key: dummy parameter to force cache refresh
    """
    if not tickers:
        return {}
    
    try:
        # batch download
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
                    if t in data.columns: # Top level ticker check
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

# --- Core Logic ---

def process_portfolio(df, target_currency, refresh_key=0):
    """
    Calculates portfolio metrics, average cost, P&L, FOMO.
    Separates open positions from sales history.
    refresh_key: parameter to force price refresh
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0, 0.0

    df = df.sort_values(by='Date')
    
    holdings = {} # {ticker: {'qty': 0, 'total_cost': 0, 'pmc': 0, 'currency': ''}}
    closed_positions = []  # List for sales history
    
    # Pre-fetch exchange rates for currencies involved
    currencies_in_use = df['Currency'].unique()
    rates_cache = {}
    for curr in currencies_in_use:
        if curr != target_currency:
            rates_cache[curr] = get_exchange_rate_history(curr, target_currency)
    
    total_realized_pl = 0.0
    
    for index, row in df.iterrows():
        t = row['Ticker']
        qty = row['Qty']
        price_orig = row['Price']
        curr_orig = row['Currency']
        date_tx = row['Date'] # datetime.date
        
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
        if data['currency']:
            ticker_currencies[t] = data['currency']
    
    # Add currencies from sold tickers
    for pos in closed_positions:
        if pos['Ticker'] not in ticker_currencies:
            ticker_currencies[pos['Ticker']] = pos['Currency']
        
    rates_live_cache = {}
    for curr in set(ticker_currencies.values()):
        if curr != target_currency:
            rates_live_cache[curr] = get_exchange_rate_history(curr, target_currency, period="5d")
            
    # --- Build Open Positions Table (df_open) ---
    open_positions = []
    total_unrealized_pl = 0.0
    total_value = 0.0
    
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
        
        total_value += market_value_conv
        total_unrealized_pl += unrealized_pl_conv
        
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
        
    # --- Build Sales History Table (df_closed) ---
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

    df_open = pd.DataFrame(open_positions)
    df_closed = pd.DataFrame(closed_positions)

    return df_open, df_closed, total_value, total_realized_pl, total_unrealized_pl

# --- Init Session State ---
if 'df_tx' not in st.session_state:
    st.session_state.df_tx = pd.DataFrame(columns=['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency'])
    
if 'refresh_key' not in st.session_state:
    st.session_state.refresh_key = 0

# --- Sidebar ---
with st.sidebar:
    st.title("Portfolio Management")
    
    # 1. Currency Settings
    target_currency = st.selectbox("Portfolio Currency", CURRENCIES, index=0) # Default EUR
    st.divider()
    
    # 1.5 Manual Refresh
    if st.button("🔄 Refresh Prices"):
        st.session_state.refresh_key += 1
        st.rerun()
        
    st.divider()
    
    # 2. Upload
    st.header("Import Data")
    uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
    if uploaded_file is not None:
        if st.button("Load from CSV"):
            try:
                df_loaded = pd.read_csv(uploaded_file)
                # Date conversion needed
                df_loaded['Date'] = pd.to_datetime(df_loaded['Date']).dt.date
                st.session_state.df_tx = df_loaded
                # Increment refresh_key to force price update
                st.session_state.refresh_key += 1
                st.success("Data loaded! Prices updated.")
                st.rerun()
            except Exception as e:
                st.error(f"Loading error: {e}")
                
    st.divider()
    
    # 3. Export
    st.header("Export Data")
    csv_data = st.session_state.df_tx.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Current CSV",
        csv_data,
        "portfolio_data.csv",
        "text/csv",
        key='download-csv'
    )
    
    st.divider()
    
    # 4. Manual Form
    st.header("New Transaction")
    with st.form("add_tx_form"):
        date_in = st.date_input("Date", datetime.today())
        ticker_in = st.text_input("Ticker (e.g. AAPL)", "").upper()
        type_in = st.selectbox("Type", ["BUY", "SELL"])
        qty_in = st.number_input("Quantity", min_value=0.0, step=1.0)
        price_in = st.number_input("Unit Price", min_value=0.0, step=0.01)
        curr_in = st.selectbox("Original Currency", CURRENCIES, index=1) # Default USD
        
        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if ticker_in and qty_in > 0 and price_in > 0:
                new_row = {
                    'Date': date_in,
                    'Ticker': ticker_in,
                    'Type': type_in,
                    'Qty': qty_in,
                    'Price': price_in,
                    'Currency': curr_in
                }
                st.session_state.df_tx = pd.concat([st.session_state.df_tx, pd.DataFrame([new_row])], ignore_index=True)
                # Increment refresh_key to update prices
                st.session_state.refresh_key += 1
                st.success("Transaction added!")
                st.rerun()
            else:
                st.error("Missing or invalid data.")

# --- Main Page ---
st.title("📈 Stock Portfolio Tracker")

# Processing
if not st.session_state.df_tx.empty:
    # Ensure Date is datetime.date for correct sorting
    st.session_state.df_tx['Date'] = pd.to_datetime(st.session_state.df_tx['Date']).dt.date
    
    with st.spinner('Processing data and exchange rates...'):
        df_pos, df_hist, val_tot, pl_real, pl_unreal = process_portfolio(
            st.session_state.df_tx, 
            target_currency, 
            refresh_key=st.session_state.refresh_key
        )
    
    # Header Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value", f"{val_tot:,.2f} {target_currency}")
    col2.metric("Unrealized P&L", f"{pl_unreal:,.2f} {target_currency}", delta=f"{pl_unreal:,.2f}")
    col3.metric("Realized P&L", f"{pl_real:,.2f} {target_currency}", delta=f"{pl_real:,.2f}")
    
    # Total P&L
    pl_total = pl_real + pl_unreal
    col4.metric("Total P&L", f"{pl_total:,.2f} {target_currency}", delta=f"{pl_total:,.2f}")
    
    st.divider()
    
    # Tabs to separate Open Positions and Sales History
    tab1, tab2 = st.tabs(["📊 Current Portfolio", "📜 Sales History"])
    
    with tab1:
        st.subheader("Open Positions")
        if not df_pos.empty:
            # Function to color P&L
            def color_pl(val):
                if pd.isna(val):
                    return ''
                color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
                return f'color: {color}'
            
            styled_df = df_pos.style.format({
                "Qty": "{:.2f}",
                "Avg Price": "{:.2f}", 
                "Current Price": "{:.2f}",
                "Initial Value": "{:.2f}",
                "Current Value": "{:.2f}",
                "Unrealized P&L": "{:.2f}",
                "Unrealized P&L %": "{:.2f}"
            }).applymap(color_pl, subset=['Unrealized P&L', 'Unrealized P&L %'])
            
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("No open positions at the moment.")
    
    with tab2:
        st.subheader("Sales History & FOMO Analysis")
        if not df_hist.empty:
            # Select and order columns for sales history
            display_cols = ['Date', 'Ticker', 'Qty', 'Avg Price', 'Current Price', 'Value Today', 'Realized_PL', 'FOMO', 'Currency']
            
            # Function to color values
            def color_values(val):
                if pd.isna(val):
                    return ''
                color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
                return f'color: {color}'
            
            styled_hist = df_hist[display_cols].sort_values(by='Date', ascending=False).style.format({
                "Qty": "{:.2f}",
                "Avg Price": "{:.2f}",
                "Current Price": "{:.2f}",
                "Value Today": "{:.2f}",
                "Realized_PL": "{:.2f}",
                "FOMO": "{:.2f}"
            }).applymap(color_values, subset=['Realized_PL', 'FOMO'])
            
            st.dataframe(styled_hist, use_container_width=True)
            
            # FOMO Statistics
            if 'FOMO' in df_hist.columns:
                total_fomo = df_hist['FOMO'].sum()
                avg_fomo = df_hist['FOMO'].mean()
                
                st.divider()
                col_f1, col_f2 = st.columns(2)
                col_f1.metric("Total FOMO", f"{total_fomo:,.2f} {target_currency}", 
                             help="Total difference between current value of sold stocks and actual proceeds")
                col_f2.metric("Average FOMO", f"{avg_fomo:,.2f} {target_currency}",
                             help="Average FOMO per sales transaction")
        else:
            st.info("No sales recorded.")
    
else:
    st.info("No transactions present. Use the sidebar to upload a CSV or add transactions manually.")
