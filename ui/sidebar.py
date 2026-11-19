"""
Sidebar UI components for portfolio management.
"""
import streamlit as st
import pandas as pd
from datetime import date

from config import CURRENCIES
from core.storage import to_csv_bytes
from core.transactions import (
    MissingColumnsError,
    append_transaction,
    normalize_transactions,
)
from ui.state import set_transactions, show_notice

_MAX_LISTED_ROWS = 15


def render_sidebar():
    """
    Renders the sidebar with portfolio management controls.

    Returns:
        str: Selected target currency
    """
    with st.sidebar:
        st.title("Portfolio Management")

        target_currency = st.selectbox("Portfolio Currency", CURRENCIES, index=0)  # Default EUR
        st.divider()

        # The only control that bypasses the price and FX caches.
        if st.button("🔄 Refresh Prices"):
            st.session_state.refresh_key += 1
            st.rerun()

        st.divider()
        show_notice('sidebar_notice')
        _render_upload_section()
        st.divider()
        _render_export_section()
        st.divider()
        _render_transaction_form()

    return target_currency


def _bullet_list(lines):
    preview = lines[:_MAX_LISTED_ROWS]
    text = "\n".join(f"- {line}" for line in preview)
    extra = len(lines) - len(preview)
    if extra > 0:
        text += f"\n- …and {extra} more."
    return text


def _render_upload_section():
    """Renders the CSV upload section."""
    st.header("Import Data")
    uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
    if uploaded_file is None:
        return
    has_data = not st.session_state.df_tx.empty
    mode = st.radio(
        "Imported rows",
        ["Add to existing", "Replace all"],
        disabled=not has_data,
        help="Replace all deletes the saved transactions and keeps only the file's rows.",
    )
    if not st.button("Load from CSV"):
        return

    try:
        # Keep blank lines so reported row numbers match the file.
        df_loaded = pd.read_csv(uploaded_file, encoding="utf-8-sig", skip_blank_lines=False)
        cleaned, messages = normalize_transactions(df_loaded)
    except MissingColumnsError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"Loading error: {e}")
        return

    if cleaned.empty:
        detail = _bullet_list(messages) if messages else "The file has no data rows."
        st.error("No valid transactions could be loaded.\n\n" + detail)
        return

    if has_data and mode == "Add to existing":
        combined = pd.concat([st.session_state.df_tx, cleaned], ignore_index=True)
        success = f"Added {len(cleaned)} transaction(s) to the existing {len(st.session_state.df_tx)}."
    else:
        combined = cleaned
        success = f"Loaded {len(cleaned)} transaction(s)."
    set_transactions(
        combined,
        success,
        warning=("Notes on the import:\n\n" + _bullet_list(messages)) if messages else None,
    )
    st.rerun()


def _render_export_section():
    """Renders the CSV export section."""
    st.header("Export Data")
    st.download_button(
        "Download Current CSV",
        to_csv_bytes(st.session_state.df_tx),
        "portfolio_data.csv",
        "text/csv",
        key='download-csv'
    )


def _render_transaction_form():
    """Renders the manual transaction entry form."""
    st.header("New Transaction")
    with st.form("add_tx_form"):
        date_in = st.date_input("Date", date.today())
        ticker_in = st.text_input("Ticker (e.g. AAPL)", "")
        type_in = st.selectbox("Type", ["BUY", "SELL"])
        qty_in = st.number_input("Quantity", min_value=0.0, step=1.0, format="%.6g")
        price_in = st.number_input("Unit Price", min_value=0.0, step=0.01, format="%.4f")
        curr_in = st.selectbox("Original Currency", CURRENCIES, index=1)  # Default USD

        if not st.form_submit_button("Add Transaction"):
            return

    new_df, errors = append_transaction(st.session_state.df_tx, {
        'Date': date_in,
        'Ticker': ticker_in,
        'Type': type_in,
        'Qty': qty_in,
        'Price': price_in,
        'Currency': curr_in,
    })
    if errors:
        st.error("Invalid transaction: " + "; ".join(errors))
        return

    set_transactions(new_df, f"Added {type_in} {ticker_in.strip().upper()}.")
    st.rerun()
