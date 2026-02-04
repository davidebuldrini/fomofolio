"""
Main view UI components for portfolio display.
"""
import streamlit as st
import pandas as pd


def render_main_view(df_pos, df_hist, val_tot, pl_real, pl_unreal, target_currency):
    """
    Renders the main portfolio view with metrics and data tables.
    
    Args:
        df_pos: DataFrame with open positions
        df_hist: DataFrame with sales history
        val_tot: Total portfolio value
        pl_real: Total realized P&L
        pl_unreal: Total unrealized P&L
        target_currency: Display currency for values
    """
    st.title("📈 Stock Portfolio Tracker")
    
    # Header Metrics
    _render_metrics(val_tot, pl_unreal, pl_real, target_currency)
    st.divider()
    
    # Tabs to separate Open Positions and Sales History
    tab1, tab2 = st.tabs(["📊 Current Portfolio", "📜 Sales History"])
    
    with tab1:
        _render_open_positions(df_pos)
    
    with tab2:
        _render_sales_history(df_hist, target_currency)


def render_empty_state():
    """Renders the empty state when no transactions are present."""
    st.title("📈 Stock Portfolio Tracker")
    st.info("No transactions present. Use the sidebar to upload a CSV or add transactions manually.")


def _render_metrics(val_tot, pl_unreal, pl_real, target_currency):
    """Renders the portfolio metrics row."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value", f"{val_tot:,.2f} {target_currency}")
    col2.metric("Unrealized P&L", f"{pl_unreal:,.2f} {target_currency}", delta=f"{pl_unreal:,.2f}")
    col3.metric("Realized P&L", f"{pl_real:,.2f} {target_currency}", delta=f"{pl_real:,.2f}")
    
    # Total P&L
    pl_total = pl_real + pl_unreal
    col4.metric("Total P&L", f"{pl_total:,.2f} {target_currency}", delta=f"{pl_total:,.2f}")


def _render_open_positions(df_pos):
    """Renders the open positions table."""
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
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("No open positions at the moment.")


def _render_sales_history(df_hist, target_currency):
    """Renders the sales history table with FOMO analysis."""
    st.subheader("Sales History & FOMO Analysis")
    if not df_hist.empty:
        # Select and order columns for sales history in the exact order requested
        display_cols = ['Date', 'Ticker', 'Qty', 'Avg Buy Price', 'Sell Price', 'Value', 
                       'Current Price', 'Value Today', 'Realized P&L', 'FOMO', 'Currency']
        
        # Function to color values
        def color_values(val):
            if pd.isna(val):
                return ''
            color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
            return f'color: {color}'
        
        styled_hist = df_hist[display_cols].sort_values(by='Date', ascending=False).style.format({
            "Qty": "{:.2f}",
            "Avg Buy Price": "{:.2f}",
            "Sell Price": "{:.2f}",
            "Value": "{:.2f}",
            "Current Price": "{:.2f}",
            "Value Today": "{:.2f}",
            "Realized P&L": "{:.2f}",
            "FOMO": "{:.2f}"
        }).applymap(color_values, subset=['Realized P&L', 'FOMO'])
        
        st.dataframe(styled_hist, use_container_width=True, hide_index=True)
        
        # FOMO Statistics
        if 'FOMO' in df_hist.columns:
            _render_fomo_stats(df_hist, target_currency)
    else:
        st.info("No sales recorded.")


def _render_fomo_stats(df_hist, target_currency):
    """Renders FOMO statistics."""
    # Use the converted FOMO column for totals (in target currency)
    # IMPORTANTE: Non sommare valori FOMO in valute diverse!
    total_fomo = df_hist['_FOMO Conv'].sum()
    avg_fomo = df_hist['_FOMO Conv'].mean()
    
    st.divider()
    col_f1, col_f2 = st.columns(2)
    col_f1.metric("Total FOMO", f"{total_fomo:,.2f} {target_currency}", 
                 help="Total difference between current value of sold stocks and actual proceeds")
    col_f2.metric("Average FOMO", f"{avg_fomo:,.2f} {target_currency}",
                 help="Average FOMO per sales transaction")
