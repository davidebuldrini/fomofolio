"""
Sidebar UI components for portfolio management.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from config import CURRENCIES


def render_sidebar():
    """
    Renders the sidebar with portfolio management controls.
    
    Returns:
        str: Selected target currency
    """
    with st.sidebar:
        st.title("Portfolio Management")
        
        # 1. Currency Settings
        target_currency = st.selectbox("Portfolio Currency", CURRENCIES, index=0)  # Default EUR
        st.divider()
        
        # 1.5 Manual Refresh
        if st.button("🔄 Refresh Prices"):
            st.session_state.refresh_key += 1
            st.rerun()
            
        st.divider()
        
        # 2. Upload
        _render_upload_section()
        st.divider()
        
        # 3. Export
        _render_export_section()
        st.divider()
        
        # 4. Manual Form
        _render_transaction_form()
    
    return target_currency


def _render_upload_section():
    """Renders the CSV upload section."""
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


def _render_export_section():
    """Renders the CSV export section."""
    st.header("Export Data")
    csv_data = st.session_state.df_tx.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Current CSV",
        csv_data,
        "portfolio_data.csv",
        "text/csv",
        key='download-csv'
    )


def _render_transaction_form():
    """Renders the manual transaction entry form."""
    st.header("New Transaction")
    with st.form("add_tx_form"):
        date_in = st.date_input("Date", datetime.today())
        ticker_in = st.text_input("Ticker (e.g. AAPL)", "").upper()
        type_in = st.selectbox("Type", ["BUY", "SELL"])
        qty_in = st.number_input("Quantity", min_value=0.0, step=1.0)
        price_in = st.number_input("Unit Price", min_value=0.0, step=0.01)
        curr_in = st.selectbox("Original Currency", CURRENCIES, index=1)  # Default USD
        
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
                st.session_state.df_tx = pd.concat(
                    [st.session_state.df_tx, pd.DataFrame([new_row])], 
                    ignore_index=True
                )
                # Increment refresh_key to update prices
                st.session_state.refresh_key += 1
                st.success("Transaction added!")
                st.rerun()
            else:
                st.error("Missing or invalid data.")
