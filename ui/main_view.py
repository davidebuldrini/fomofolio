"""
Main view UI components for portfolio display.
"""
import streamlit as st
import pandas as pd

from core.portfolio_processor import (
    COST_BASE,
    FOMO_BASE,
    REALIZED_BASE,
    UNREALIZED_BASE,
    VALUE_BASE,
)
from utils.numbers import is_missing


def render_main_view(result, target_currency):
    """
    Renders the main portfolio view with metrics and data tables.

    Args:
        result: PortfolioResult from process_portfolio
        target_currency: Display currency for portfolio totals
    """
    st.title("📈 Stock Portfolio Tracker")

    for message in result.warnings:
        st.warning(message)

    _render_metrics(result, target_currency)
    st.divider()

    tab1, tab2 = st.tabs(["📊 Current Portfolio", "📜 Sales History"])
    with tab1:
        _render_open_positions(result.open_positions, target_currency)
    with tab2:
        _render_sales_history(result.sales, target_currency)


def render_empty_state():
    """Renders the empty state when no transactions are present."""
    st.title("📈 Stock Portfolio Tracker")
    st.info(
        "No transactions present. Use the sidebar to upload a CSV or add transactions manually. "
        "Data is kept only for this browser session: export a CSV to keep it."
    )


def _format_money(value, currency):
    if is_missing(value):
        return f"— {currency}"
    return f"{value:,.2f} {currency}"


def _format_qty(value):
    if is_missing(value):
        return "—"
    return f"{value:,.6f}".rstrip('0').rstrip('.')


def _render_metrics(result, target_currency):
    """Renders the portfolio metrics row. Amounts are in the portfolio currency."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value", _format_money(result.total_value, target_currency))

    pct = result.unrealized_pl_percent
    col2.metric(
        "Unrealized P&L",
        _format_money(result.unrealized_pl, target_currency),
        delta=None if is_missing(pct) else f"{pct:+.2f}%",
        help="Change versus the cost of the open positions included in the total.",
    )
    col3.metric("Realized P&L", _format_money(result.realized_pl, target_currency))
    col4.metric("Total P&L", _format_money(result.total_pl, target_currency))
    st.caption(
        f"Totals are in {target_currency}. "
        "Positions with a missing price or exchange rate are not included. "
        "Data is kept only for this browser session: export a CSV to keep it."
    )


def _color_pl(val):
    if is_missing(val):
        return ''
    number = float(val)
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

    value_label = f"Current Value ({target_currency})"
    pl_label = f"Unrealized P&L ({target_currency})"
    visible = df_pos.drop(columns=[COST_BASE]).rename(columns={
        VALUE_BASE: value_label,
        UNREALIZED_BASE: pl_label,
    })
    money = "{:,.2f}"
    styled_df = visible.style.format({
        "Qty": _format_qty,
        "Avg Price": money,
        "Current Price": money,
        "Initial Value": money,
        "Current Value": money,
        "Unrealized P&L": money,
        "Unrealized P&L %": "{:+.2f}%",
        value_label: money,
        pl_label: money,
    }, na_rep="—").map(_color_pl, subset=['Unrealized P&L', 'Unrealized P&L %', pl_label])

    st.dataframe(styled_df, width="stretch", hide_index=True)
    st.caption(
        "Prices, values and P&L % are in the transaction currency (Currency column). "
        f"Columns marked {target_currency} include the exchange rate effect."
    )


def _render_sales_history(df_hist, target_currency):
    """Renders the sales history table with FOMO analysis."""
    st.subheader("Sales History & FOMO Analysis")
    if df_hist.empty:
        st.info("No sales recorded.")
        return

    realized_label = f"Realized P&L ({target_currency})"
    fomo_base_label = f"FOMO ({target_currency})"
    display_cols = [
        'Date', 'Ticker', 'Qty', 'Avg Buy Price', 'Sell Price', 'Value',
        'Current Price', 'Value Today', 'FOMO', 'Currency', REALIZED_BASE, FOMO_BASE,
    ]
    visible = (
        df_hist[display_cols]
        .rename(columns={REALIZED_BASE: realized_label, FOMO_BASE: fomo_base_label})
        .sort_values(by='Date', ascending=False)
    )

    money = "{:,.2f}"
    styled_hist = visible.style.format({
        "Qty": _format_qty,
        "Avg Buy Price": money,
        "Sell Price": money,
        "Value": money,
        "Current Price": money,
        "Value Today": money,
        "FOMO": money,
        realized_label: money,
        fomo_base_label: money,
    }, na_rep="—").map(_color_pl, subset=['FOMO', realized_label, fomo_base_label])

    st.dataframe(styled_hist, width="stretch", hide_index=True)
    st.caption(
        "Prices, trade value and FOMO are in the transaction currency (Currency column). "
        f"Columns marked {target_currency} are in the portfolio currency. "
        "Positive FOMO means the sale beat today's price."
    )

    _render_fomo_stats(df_hist, target_currency)


def _render_fomo_stats(df_hist, target_currency):
    """Renders FOMO statistics in the portfolio currency."""
    fomo_known = pd.to_numeric(df_hist[FOMO_BASE], errors='coerce').dropna()
    total_fomo = float(fomo_known.sum()) if not fomo_known.empty else float('nan')
    avg_fomo = float(fomo_known.mean()) if not fomo_known.empty else float('nan')

    st.divider()
    col_f1, col_f2 = st.columns(2)
    col_f1.metric(
        f"Total FOMO ({target_currency})",
        _format_money(total_fomo, target_currency),
        help=(
            f"Sale proceeds minus today's value, in {target_currency}. "
            "Positive means the sale beat today's price; negative means the shares are worth more now."
        ),
    )
    col_f2.metric(
        f"Average FOMO ({target_currency})",
        _format_money(avg_fomo, target_currency),
        help=f"Average of that difference per sale, in {target_currency}.",
    )
    if len(fomo_known) < len(df_hist):
        st.caption("FOMO totals exclude sales with a missing price or exchange rate.")
