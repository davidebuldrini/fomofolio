"""
InvestTrack - Stock Portfolio Tracker
Main application entry point.
"""
import streamlit as st

from config import PAGE_TITLE, PAGE_LAYOUT
from core.portfolio_processor import process_portfolio
from core.transactions import empty_transactions
from ui.sidebar import render_sidebar
from ui.main_view import render_main_view, render_empty_state


# --- Page Configuration ---
st.set_page_config(page_title=PAGE_TITLE, layout=PAGE_LAYOUT)


def init_session_state():
    """Initialize session state variables if they don't exist."""
    if 'df_tx' not in st.session_state:
        st.session_state.df_tx = empty_transactions()
    if 'refresh_key' not in st.session_state:
        st.session_state.refresh_key = 0


def main():
    """Main application function."""
    init_session_state()
    target_currency = render_sidebar()

    # Transactions are normalized when they enter session state (CSV or form).
    if st.session_state.df_tx.empty:
        render_empty_state()
        return

    with st.spinner('Processing data and exchange rates...'):
        result = process_portfolio(
            st.session_state.df_tx,
            target_currency,
            refresh_key=st.session_state.refresh_key,
        )

    render_main_view(result, target_currency)


if __name__ == "__main__":
    main()
