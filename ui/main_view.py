"""
Main view UI components for portfolio display.
"""
import math

import streamlit as st
import pandas as pd


def render_main_view(df_pos, df_hist, val_tot, pl_real, pl_unreal, target_currency, warnings=None):
    """
    Renders the main portfolio view with metrics and data tables.

    Args:
        df_pos: DataFrame with open positions
        df_hist: DataFrame with sales history
        val_tot: Total portfolio value in the portfolio currency
        pl_real: Total realized P&L in the portfolio currency
        pl_unreal: Total unrealized P&L in the portfolio currency
        target_currency: Display currency for portfolio totals
        warnings: Calculation warnings to show above the tables
    """
    st.title("📈 Stock Portfolio Tracker")

    for message in warnings or []:
        st.warning(message)

    _render_london_note(df_pos, df_hist)

    _render_metrics(val_tot, pl_unreal, pl_real, target_currency)
    st.divider()

    tab1, tab2 = st.tabs(["📊 Current Portfolio", "📜 Sales History"])

    with tab1:
        _render_open_positions(df_pos, target_currency)

    with tab2:
        _render_sales_history(df_hist, target_currency)


def render_empty_state():
    """Renders the empty state when no transactions are present."""
    st.title("📈 Stock Portfolio Tracker")
    st.info("No transactions present. Use the sidebar to upload a CSV or add transactions manually.")


def _is_missing(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        return False
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return True


def _format_money(value, currency):
    if _is_missing(value):
        return f"— {currency}"
    return f"{value:,.2f} {currency}"


def _render_metrics(val_tot, pl_unreal, pl_real, target_currency):
    """Renders the portfolio metrics row. Amounts are in the portfolio currency."""
    if _is_missing(pl_real) or _is_missing(pl_unreal):
        pl_total = float('nan')
    else:
        pl_total = pl_real + pl_unreal

    col1, col2, col3, col4 = st.columns(4)
    _metric(col1, "Total Value", val_tot, target_currency)
    _metric(col2, "Unrealized P&L", pl_unreal, target_currency)
    _metric(col3, "Realized P&L", pl_real, target_currency)
    _metric(col4, "Total P&L", pl_total, target_currency)
    st.caption(f"Totals are in {target_currency}. Positions with a missing price or exchange rate are not included.")


def _metric(column, label, value, currency):
    text = _format_money(value, currency)
    if _is_missing(value):
        column.metric(label, text)
    else:
        column.metric(label, text, delta=f"{value:,.2f}")


def _render_london_note(df_pos, df_hist):
    tickers = []
    if df_pos is not None and not df_pos.empty and 'Ticker' in df_pos.columns:
        tickers.extend(df_pos['Ticker'].tolist())
    if df_hist is not None and not df_hist.empty and 'Ticker' in df_hist.columns:
        tickers.extend(df_hist['Ticker'].tolist())
    london = sorted({str(t).upper() for t in tickers if str(t).upper().endswith('.L')})
    if not london:
        return
    names = ", ".join(london)
    st.info(
        f"London prices for {names} are converted from pence to pounds. "
        "Record those transactions in GBP."
    )


def _color_pl(val):
    if pd.isna(val):
        return ''
    try:
        number = float(val)
    except (TypeError, ValueError):
        return ''
    if number > 0:
        return 'color: green'
    if number < 0:
        return 'color: red'
    return 'color: gray'


def _render_open_positions(df_pos, target_currency):
    """Renders the open positions table."""
    st.subheader("Open Positions")
    if df_pos.empty:
        st.info("No open positions at the moment.")
        return

    hidden = [col for col in df_pos.columns if str(col).startswith('_')]
    visible = df_pos.drop(columns=hidden)
    styled_df = visible.style.format({
        "Qty": "{:.2f}",
        "Avg Price": "{:.2f}",
        "Current Price": "{:.2f}",
        "Initial Value": "{:.2f}",
        "Current Value": "{:.2f}",
        "Unrealized P&L": "{:.2f}",
        "Unrealized P&L %": "{:.2f}",
    }, na_rep="—").map(_color_pl, subset=['Unrealized P&L', 'Unrealized P&L %'])

    st.dataframe(styled_df, width="stretch", hide_index=True)
    st.caption(
        "Prices and P&L in this table are in the instrument currency. "
        f"The totals above are in {target_currency}."
    )


def _render_sales_history(df_hist, target_currency):
    """Renders the sales history table with FOMO analysis."""
    st.subheader("Sales History & FOMO Analysis")
    if df_hist.empty:
        st.info("No sales recorded.")
        return

    realized_label = f"Realized P&L ({target_currency})"
    display_cols = [
        'Date', 'Ticker', 'Qty', 'Avg Buy Price', 'Sell Price', 'Value',
        'Current Price', 'Value Today', 'Realized P&L', 'FOMO', 'Currency',
    ]
    visible = (
        df_hist[display_cols]
        .rename(columns={'Realized P&L': realized_label})
        .sort_values(by='Date', ascending=False)
    )

    styled_hist = visible.style.format({
        "Qty": "{:.2f}",
        "Avg Buy Price": "{:.2f}",
        "Sell Price": "{:.2f}",
        "Value": "{:.2f}",
        "Current Price": "{:.2f}",
        "Value Today": "{:.2f}",
        realized_label: "{:.2f}",
        "FOMO": "{:.2f}",
    }, na_rep="—").map(_color_pl, subset=[realized_label, 'FOMO'])

    st.dataframe(styled_hist, width="stretch", hide_index=True)
    st.caption(
        f"{realized_label} is in the portfolio currency. "
        "Prices, trade value, and FOMO in the table are in the instrument currency. "
        "Positive FOMO means the sale beat today's price."
    )

    if '_FOMO Conv' in df_hist.columns:
        _render_fomo_stats(df_hist, target_currency)


def _render_fomo_stats(df_hist, target_currency):
    """Renders FOMO statistics in the portfolio currency."""
    fomo_known = pd.to_numeric(df_hist['_FOMO Conv'], errors='coerce').dropna()
    total_fomo = float(fomo_known.sum()) if not fomo_known.empty else float('nan')
    avg_fomo = float(fomo_known.mean()) if not fomo_known.empty else float('nan')

    st.divider()
    col_f1, col_f2 = st.columns(2)
    help_total = (
        f"Sale proceeds minus today's value, in {target_currency}. "
        "Positive means the sale beat today's price; negative means the shares are worth more now."
    )
    help_avg = (
        f"Average of that difference per sale, in {target_currency}. "
        "Sales with a missing price or exchange rate are excluded."
    )
    if _is_missing(total_fomo):
        col_f1.metric(f"Total FOMO ({target_currency})", f"— {target_currency}", help=help_total)
    else:
        col_f1.metric(
            f"Total FOMO ({target_currency})",
            _format_money(total_fomo, target_currency),
            delta=f"{total_fomo:,.2f}",
            help=help_total,
        )
    if _is_missing(avg_fomo):
        col_f2.metric(f"Average FOMO ({target_currency})", f"— {target_currency}", help=help_avg)
    else:
        col_f2.metric(
            f"Average FOMO ({target_currency})",
            _format_money(avg_fomo, target_currency),
            delta=f"{avg_fomo:,.2f}",
            help=help_avg,
        )
    if len(fomo_known) < len(df_hist):
        st.caption("FOMO totals exclude sales with a missing price or exchange rate.")
