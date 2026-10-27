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
    notice = st.session_state.get('import_notice')
    if notice:
        st.success(notice['loaded'])
        if notice.get('skipped'):
            st.warning(notice['skipped'])
        st.session_state.import_notice = None

    uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
    if uploaded_file is not None:
        if st.button("Load from CSV"):
            try:
                df_loaded = pd.read_csv(uploaded_file, encoding="utf-8-sig")
                cleaned, skipped = _validate_transactions(df_loaded)
                if cleaned is None:
                    st.error(skipped)
                elif cleaned.empty:
                    detail = "\n".join(f"- {line}" for line in skipped) if skipped else "The file has no data rows."
                    st.error("No valid transactions could be loaded.\n\n" + detail)
                else:
                    st.session_state.df_tx = cleaned
                    st.session_state.refresh_key += 1
                    loaded_text = f"Loaded {len(cleaned)} transaction(s)."
                    skipped_text = None
                    if skipped:
                        preview = skipped[:15]
                        extra = len(skipped) - len(preview)
                        skipped_text = "Skipped invalid rows:\n\n" + "\n".join(
                            f"- {line}" for line in preview
                        )
                        if extra > 0:
                            skipped_text += f"\n- …and {extra} more."
                    st.session_state.import_notice = {
                        'loaded': loaded_text,
                        'skipped': skipped_text,
                    }
                    st.rerun()
            except Exception as e:
                st.error(f"Loading error: {e}")


def _validate_transactions(df):
    """
    Keep rows that can be calculated. Returns (dataframe or None, messages).

    A missing required column rejects the whole file. Invalid rows are dropped
    and described individually so the remaining data can still be loaded.
    """
    required = ['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency']
    renamed = df.copy()
    renamed.columns = [str(col).strip().lstrip("\ufeff") for col in renamed.columns]
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    missing = [col for col in required if col not in renamed.columns]
    if missing:
        return None, f"Missing columns: {', '.join(missing)}. Expected {', '.join(required)}."

    kept_rows = []
    skipped = []
    subset = renamed[required]
    for offset in range(len(subset)):
        line_no = offset + 2
        raw = subset.iloc[offset]
        reasons = []

        parsed_date = pd.to_datetime(raw['Date'], errors='coerce')
        if pd.isna(parsed_date):
            reasons.append("invalid date")

        ticker = '' if pd.isna(raw['Ticker']) else str(raw['Ticker']).strip().upper()
        if not ticker or ticker == 'NAN':
            reasons.append("missing ticker")

        tx_type = '' if pd.isna(raw['Type']) else str(raw['Type']).strip().upper()
        if tx_type not in ('BUY', 'SELL'):
            reasons.append("type must be BUY or SELL")

        qty = pd.to_numeric(raw['Qty'], errors='coerce')
        if pd.isna(qty) or float(qty) <= 0:
            reasons.append("quantity must be positive")

        price = pd.to_numeric(raw['Price'], errors='coerce')
        if pd.isna(price) or float(price) <= 0:
            reasons.append("price must be positive")

        currency = '' if pd.isna(raw['Currency']) else str(raw['Currency']).strip().upper()
        if currency not in CURRENCIES:
            reasons.append(f"currency must be one of {', '.join(CURRENCIES)}")

        if reasons:
            skipped.append(f"Row {line_no}: {', '.join(reasons)}.")
            continue

        kept_rows.append({
            'Date': parsed_date.date(),
            'Ticker': ticker,
            'Type': tx_type,
            'Qty': float(qty),
            'Price': float(price),
            'Currency': currency,
        })

    cleaned = pd.DataFrame(kept_rows, columns=required)
    return cleaned, skipped


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
