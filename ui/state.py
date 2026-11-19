"""
Session state for transactions, kept in sync with the saved file.
"""
import streamlit as st

from core.storage import data_file_path, load_transactions, save_transactions


def init_session_state():
    """Load saved transactions once per browser session."""
    if 'df_tx' not in st.session_state:
        df, messages = load_transactions()
        st.session_state.df_tx = df
        st.session_state.load_messages = messages
    if 'refresh_key' not in st.session_state:
        st.session_state.refresh_key = 0
    # Bumped after each save so the transaction editor restarts from saved data.
    if 'editor_version' not in st.session_state:
        st.session_state.editor_version = 0


def set_transactions(df, success, warning=None, notice_key='sidebar_notice'):
    """
    Replace the transactions, save them, and leave a notice for the next run.

    If saving fails the change is kept for this session and the notice says so.
    """
    st.session_state.df_tx = df
    st.session_state.editor_version += 1
    try:
        save_transactions(df)
    except OSError as e:
        failure = f"Changes are not saved to disk ({data_file_path()}): {e}"
        warning = f"{warning}\n\n{failure}" if warning else failure
    st.session_state[notice_key] = {'success': success, 'warning': warning}


def show_notice(notice_key, container=st):
    """Show a notice saved before the last rerun, then clear it."""
    notice = st.session_state.get(notice_key)
    if not notice:
        return
    container.success(notice['success'])
    if notice.get('warning'):
        container.warning(notice['warning'])
    st.session_state[notice_key] = None
