"""
Editable transaction table: change, add or delete rows, then save.
"""
import pandas as pd
import streamlit as st

from config import CURRENCIES
from core.storage import data_file_path
from core.transactions import REQUIRED_COLUMNS, TX_TYPES, normalize_transactions
from ui.state import set_transactions, show_notice

_NOTICE_KEY = 'editor_notice'


def _editor_frame(df):
    """Transactions sorted by date (stable), with dates as datetimes for the editor."""
    view = df[REQUIRED_COLUMNS].copy()
    view['Date'] = pd.to_datetime(view['Date'])
    return view.sort_values('Date', kind='mergesort').reset_index(drop=True)


def _same(a, b):
    if len(a) != len(b):
        return False
    left = a.reset_index(drop=True).astype(object).where(a.notna().values, None)
    right = b.reset_index(drop=True).astype(object).where(b.notna().values, None)
    return left.equals(right)


def render_transactions_editor():
    """Renders the editor tab."""
    st.subheader("Transactions")
    show_notice(_NOTICE_KEY)

    original = _editor_frame(st.session_state.df_tx)
    edited = st.data_editor(
        original,
        key=f"tx_editor_{st.session_state.editor_version}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            'Date': st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            'Ticker': st.column_config.TextColumn("Ticker"),
            'Type': st.column_config.SelectboxColumn("Type", options=list(TX_TYPES)),
            'Qty': st.column_config.NumberColumn("Qty", min_value=0.0, format="%.6g"),
            'Price': st.column_config.NumberColumn("Price", min_value=0.0, format="%.4f"),
            'Currency': st.column_config.SelectboxColumn("Currency", options=CURRENCIES),
        },
    )
    st.caption(
        "Edit cells directly, add rows at the bottom, or select rows and press Delete to remove them. "
        f"Changes take effect when you save. Saved to {data_file_path()}."
    )

    if _same(edited, original):
        return

    with st.container(horizontal=True):
        save = st.button("💾 Save changes", type="primary")
        discard = st.button("Discard changes")

    if discard:
        st.session_state.editor_version += 1
        st.rerun()
    if not save:
        st.info("You have unsaved changes.")
        return

    cleaned, messages = normalize_transactions(edited, first_line=1)
    errors = [m for m in messages if m.startswith("Row ")]
    if errors:
        st.error(
            "Nothing was saved. Fix these rows first (row numbers count from the top of the table):\n\n"
            + "\n".join(f"- {line}" for line in errors)
        )
        return

    removed = len(original) - len(cleaned)
    if removed > 0:
        summary = f"Saved. {len(cleaned)} transaction(s), {removed} removed."
    elif removed < 0:
        summary = f"Saved. {len(cleaned)} transaction(s), {-removed} added."
    else:
        summary = f"Saved. {len(cleaned)} transaction(s)."
    set_transactions(cleaned, summary, notice_key=_NOTICE_KEY)
    st.rerun()
