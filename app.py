"""
InvestTrack - Stock Portfolio Tracker
Main application entry point.
"""
import streamlit as st
import pandas as pd

from config import PAGE_TITLE, PAGE_LAYOUT
from core.portfolio_processor import process_portfolio
from ui.sidebar import render_sidebar
from ui.main_view import render_main_view, render_empty_state


# --- Page Configuration ---
st.set_page_config(page_title=PAGE_TITLE, layout=PAGE_LAYOUT)


# --- Initialize Session State ---
def init_session_state():
    """Initialize session state variables if they don't exist."""
    if 'df_tx' not in st.session_state:
        st.session_state.df_tx = pd.DataFrame(
            columns=['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency']
        )
    
    if 'refresh_key' not in st.session_state:
        st.session_state.refresh_key = 0


def main():
    """Main application function."""
    # Initialize session state
    init_session_state()
    
    # Render sidebar and get target currency
    target_currency = render_sidebar()
    
    # Process and display portfolio
    if not st.session_state.df_tx.empty:
        # Ensure Date is datetime.date for correct sorting
        st.session_state.df_tx['Date'] = pd.to_datetime(
            st.session_state.df_tx['Date']
        ).dt.date
        
        with st.spinner('Processing data and exchange rates...'):
            df_pos, df_hist, val_tot, pl_real, pl_unreal, warnings = process_portfolio(
                st.session_state.df_tx, 
                target_currency, 
                refresh_key=st.session_state.refresh_key
            )
        
        render_main_view(
            df_pos, df_hist, val_tot, pl_real, pl_unreal, target_currency, warnings
        )
    else:
        render_empty_state()


if __name__ == "__main__":
    main()
