"""
FOMOfolio - Stock Portfolio Tracker
Main application entry point.
"""
import streamlit as st

from config import PAGE_TITLE, PAGE_LAYOUT
from core.portfolio_processor import process_portfolio
from ui.state import init_session_state
from ui.sidebar import render_sidebar
from ui.main_view import render_main_view, render_empty_state


# --- Page Configuration ---
st.set_page_config(page_title=PAGE_TITLE, layout=PAGE_LAYOUT)


def main():
    """Main application function."""
    init_session_state()
    target_currency = render_sidebar()

    for message in st.session_state.get('load_messages') or []:
        st.error(message)

    # Transactions are normalized when they enter session state.
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
