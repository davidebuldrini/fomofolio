"""
Portfolio processing logic for calculating positions, P&L, and FOMO metrics.
"""
import math

import pandas as pd
from utils.exchange_rates import get_exchange_rate_history, get_rate_at_date
from utils.price_fetcher import get_current_prices


_QTY_EPSILON = 1e-9


def average_cost(shares, prices, commissions=0):
    """
    Calculate the average cost (cost basis) of a stock position.

    Formula: (sum of (shares * price) + commissions) / total shares

    Args:
        shares: list of number of shares bought
        prices: list of prices per share
        commissions: total commissions paid (optional)

    Returns:
        float: Average cost per share

    Example:
        shares = [100, 50]
        prices = [10, 12]
        avg_cost = average_cost(shares, prices)
        # Returns: 10.67 = ((100*10) + (50*12)) / 150
    """
    total_cost = sum(s * p for s, p in zip(shares, prices)) + commissions
    total_shares = sum(shares)
    return total_cost / total_shares if total_shares > 0 else 0


def _empty_holding():
    return {
        'qty': 0.0,
        'total_cost_orig': 0.0,
        'total_cost_conv': 0.0,
        'pmc_orig': 0.0,
        'pmc_conv': 0.0,
        'currency': '',
        # False when any buy could not be converted, so blended PMC in
        # portfolio currency would be incomplete.
        'fx_ok': True,
    }


def _is_missing(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return True


def _sum_known(series):
    """Sum finite values. Empty input is 0. All-missing input is NaN."""
    if series is None or len(series) == 0:
        return 0.0
    known = pd.to_numeric(series, errors='coerce').dropna()
    if known.empty:
        return float('nan')
    return float(known.sum())


def _lookup_rate(curr_orig, target_currency, rates_cache, date_tx):
    if curr_orig == target_currency:
        return 1.0
    rate_series = rates_cache.get(curr_orig)
    return get_rate_at_date(rate_series, date_tx)


def _live_rate(currency, target_currency, rates_live_cache):
    if currency == target_currency:
        return 1.0
    series = rates_live_cache.get(currency)
    if series is None or len(series) == 0:
        return None
    cleaned = series.dropna()
    if cleaned.empty:
        return None
    rate = float(cleaned.iloc[-1])
    if not math.isfinite(rate) or rate <= 0:
        return None
    return rate


def process_portfolio(df, target_currency, refresh_key=0):
    """
    Calculates portfolio metrics, average cost, P&L, FOMO.
    Separates open positions from sales history.

    Buys are applied before sells on the same date. A sell larger than the
    open quantity realizes P&L only on the shares actually held. Each ticker
    keeps the currency of its first buy; later rows in another currency are
    ignored. Missing prices and exchange rates stay unknown and are left out
    of the totals.

    Args:
        df: DataFrame with transaction data
        target_currency: The base currency for portfolio calculations
        refresh_key: Parameter to force price and FX refresh

    Returns:
        tuple: (df_open, df_closed, total_value, total_realized_pl,
                total_unrealized_pl, warnings)
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0, 0.0, []

    df = df.copy()
    df['_sort_type'] = (
        df['Type'].astype(str).str.strip().str.upper()
        .map({'BUY': 0, 'SELL': 1})
        .fillna(2)
    )
    # mergesort is stable, so two buys on the same day keep their entry order.
    df = df.sort_values(by=['Date', '_sort_type'], kind='mergesort')

    holdings = {}
    closed_positions = []
    warnings = []

    currencies_in_use = df['Currency'].dropna().astype(str).str.strip().str.upper().unique()
    rates_cache = {}
    for curr in currencies_in_use:
        if curr != target_currency:
            rates_cache[curr] = get_exchange_rate_history(
                curr, target_currency, period="max", refresh_key=refresh_key
            )

    realized_amounts = []
    realized_incomplete = False

    for _, row in df.iterrows():
        tx_type = str(row['Type']).strip().upper()
        ticker = str(row['Ticker']).strip().upper()
        if not ticker or ticker == 'NAN':
            warnings.append("A transaction without a ticker was ignored.")
            continue
        if tx_type not in ('BUY', 'SELL'):
            warnings.append(
                f"{ticker} on {row['Date']}: type '{row['Type']}' was ignored. Use BUY or SELL."
            )
            continue

        try:
            qty = float(row['Qty'])
            price_orig = float(row['Price'])
        except (TypeError, ValueError):
            warnings.append(f"{ticker} on {row['Date']}: quantity or price is not a number. Row ignored.")
            continue
        if qty <= 0 or price_orig <= 0 or not math.isfinite(qty) or not math.isfinite(price_orig):
            warnings.append(f"{ticker} on {row['Date']}: quantity and price must be positive. Row ignored.")
            continue

        curr_orig = str(row['Currency']).strip().upper()
        date_tx = row['Date']

        if ticker not in holdings:
            holdings[ticker] = _empty_holding()

        position = holdings[ticker]
        rate = _lookup_rate(curr_orig, target_currency, rates_cache, date_tx)

        if tx_type == 'BUY':
            if position['currency'] and curr_orig != position['currency']:
                warnings.append(
                    f"BUY {ticker} on {date_tx} in {curr_orig} was ignored. "
                    f"This ticker is already tracked in {position['currency']}."
                )
                continue

            position['currency'] = curr_orig
            add_cost_orig = qty * price_orig
            position['qty'] += qty
            position['total_cost_orig'] += add_cost_orig

            if _is_missing(rate):
                position['fx_ok'] = False
                warnings.append(
                    f"No exchange rate for {curr_orig} to {target_currency} on {date_tx} ({ticker}). "
                    "That buy is excluded from portfolio-currency P&L."
                )
            elif position['fx_ok']:
                position['total_cost_conv'] += qty * price_orig * rate

            if position['qty'] > 0:
                position['pmc_orig'] = position['total_cost_orig'] / position['qty']
                if position['fx_ok']:
                    position['pmc_conv'] = position['total_cost_conv'] / position['qty']

        elif tx_type == 'SELL':
            if position['currency'] and curr_orig != position['currency']:
                warnings.append(
                    f"SELL {ticker} on {date_tx} in {curr_orig} was ignored. "
                    f"This ticker is tracked in {position['currency']}."
                )
                continue

            available = position['qty']
            if available <= _QTY_EPSILON:
                warnings.append(
                    f"SELL {ticker} on {date_tx} for {qty:g} shares was ignored because there was no open position."
                )
                continue

            if qty > available + _QTY_EPSILON:
                excess = qty - available
                warnings.append(
                    f"SELL {ticker} on {date_tx} for {qty:g} shares exceeds the {available:g} shares held. "
                    f"The extra {excess:g} shares were excluded from P&L."
                )
                qty = available

            pmc_orig_at_sale = position['pmc_orig']
            pmc_conv_at_sale = position['pmc_conv']
            sell_converted = position['fx_ok'] and not _is_missing(rate)

            if not sell_converted:
                realized_pl = float('nan')
                proceeds = float('nan')
                realized_incomplete = True
                if _is_missing(rate):
                    warnings.append(
                        f"No exchange rate for {curr_orig} to {target_currency} on {date_tx} ({ticker}). "
                        "That sale is excluded from realized P&L."
                    )
                elif not position['fx_ok']:
                    warnings.append(
                        f"Realized P&L for {ticker} on {date_tx} is excluded because an earlier "
                        "exchange rate was missing."
                    )
            else:
                proceeds = qty * price_orig * rate
                cost_basis = qty * pmc_conv_at_sale
                realized_pl = proceeds - cost_basis
                realized_amounts.append(realized_pl)

            closed_positions.append({
                'Date': date_tx,
                'Ticker': ticker,
                'Qty': qty,
                'Avg Buy Price': pmc_orig_at_sale,
                'Sell Price': price_orig,
                'Value': price_orig * qty,
                'Proceeds': proceeds,
                'Realized P&L': realized_pl,
                'Currency': position['currency'] or curr_orig,
            })

            position['qty'] -= qty
            position['total_cost_orig'] -= qty * pmc_orig_at_sale
            if position['fx_ok']:
                position['total_cost_conv'] -= qty * pmc_conv_at_sale

            if position['qty'] <= _QTY_EPSILON:
                currency = position['currency']
                position.update(_empty_holding())
                # Keep the listing currency so a later buy in another currency is still rejected.
                # A new lot after a flat position starts its converted cost from scratch.
                position['currency'] = currency

    if realized_amounts:
        total_realized_pl = float(sum(realized_amounts))
    elif realized_incomplete:
        total_realized_pl = float('nan')
    else:
        total_realized_pl = 0.0

    active_tickers = [t for t, data in holdings.items() if data['qty'] > _QTY_EPSILON]
    sold_tickers = list({pos['Ticker'] for pos in closed_positions})
    all_tickers_needed = sorted(set(active_tickers + sold_tickers))

    current_prices = get_current_prices(all_tickers_needed, refresh_key=refresh_key)

    ticker_currencies = {}
    for t, data in holdings.items():
        if data.get('currency'):
            ticker_currencies[t] = data['currency']
    for pos in closed_positions:
        ticker_currencies.setdefault(pos['Ticker'], pos['Currency'])

    rates_live_cache = {}
    for curr in set(ticker_currencies.values()):
        if curr != target_currency:
            rates_live_cache[curr] = get_exchange_rate_history(
                curr, target_currency, period="5d", refresh_key=refresh_key
            )

    df_open = _build_open_positions(
        active_tickers, holdings, current_prices,
        rates_live_cache, target_currency, warnings
    )
    df_closed = _build_sales_history(
        closed_positions, current_prices,
        rates_live_cache, target_currency, warnings
    )

    total_value = _sum_known(df_open['_Current Value Conv']) if not df_open.empty else 0.0
    total_unrealized_pl = _sum_known(df_open['_Unrealized P&L Conv']) if not df_open.empty else 0.0

    return df_open, df_closed, total_value, total_realized_pl, total_unrealized_pl, _unique_warnings(warnings)


def _unique_warnings(warnings):
    seen = set()
    unique = []
    for message in warnings:
        if message not in seen:
            seen.add(message)
            unique.append(message)
    return unique


def _build_open_positions(active_tickers, holdings, current_prices,
                          rates_live_cache, target_currency, warnings):
    """
    Build DataFrame for open positions.

    Display amounts stay in the instrument currency. Columns prefixed with
    '_' are full-precision values in the portfolio currency and are only
    used for totals.
    """
    open_positions = []
    missing_prices = []
    missing_fx = []

    for t in active_tickers:
        qty = holdings[t]['qty']
        pmc_orig = holdings[t]['pmc_orig']
        pmc_conv = holdings[t]['pmc_conv']
        curr_t = holdings[t]['currency']
        fx_ok = holdings[t]['fx_ok']

        live_price_orig = current_prices.get(t)
        if _is_missing(live_price_orig):
            live_price_orig = None
            missing_prices.append(t)

        rate_live = _live_rate(curr_t, target_currency, rates_live_cache)
        if not fx_ok or _is_missing(rate_live):
            rate_live = None
            if curr_t and curr_t != target_currency:
                missing_fx.append(f"{t} ({curr_t})")
            elif not fx_ok:
                missing_fx.append(t)

        if live_price_orig is None:
            market_value_orig = float('nan')
            unrealized_pl_orig = float('nan')
            pl_percent = float('nan')
            current_price = float('nan')
        else:
            current_price = live_price_orig
            market_value_orig = qty * live_price_orig
            unrealized_pl_orig = (live_price_orig - pmc_orig) * qty
            pl_percent = (
                (live_price_orig - pmc_orig) / pmc_orig * 100
                if pmc_orig > 0 else float('nan')
            )

        if live_price_orig is None or rate_live is None:
            market_value_conv = float('nan')
            unrealized_pl_conv = float('nan')
        else:
            live_price_conv = live_price_orig * rate_live
            market_value_conv = qty * live_price_conv
            unrealized_pl_conv = (live_price_conv - pmc_conv) * qty

        open_positions.append({
            'Ticker': t,
            'Qty': qty,
            'Avg Price': pmc_orig,
            'Current Price': current_price,
            'Initial Value': pmc_orig * qty,
            'Current Value': market_value_orig,
            'Unrealized P&L': unrealized_pl_orig,
            'Unrealized P&L %': pl_percent,
            'Currency': curr_t,
            '_Current Value Conv': market_value_conv,
            '_Unrealized P&L Conv': unrealized_pl_conv,
        })

    if missing_prices:
        names = ", ".join(missing_prices)
        warnings.append(
            f"Current price unavailable for {names}. "
            "Those positions are excluded from portfolio totals."
        )
    if missing_fx:
        names = ", ".join(dict.fromkeys(missing_fx))
        warnings.append(
            f"Portfolio-currency value unavailable for {names}. "
            "Those positions are excluded from portfolio totals."
        )

    return pd.DataFrame(open_positions)


def _build_sales_history(closed_positions, current_prices,
                         rates_live_cache, target_currency, warnings):
    """
    Build DataFrame for sales history with FOMO analysis.

    FOMO in the table is in the instrument currency (sale proceeds minus
    today's value). `_FOMO Conv` is the same difference in portfolio currency.
    Positive FOMO means the sale beat today's price.
    """
    missing_prices = []
    missing_fx = []

    for pos in closed_positions:
        t = pos['Ticker']
        qty = pos['Qty']
        curr_t = pos['Currency']
        proceeds_base = pos['Proceeds']

        live_price_orig = current_prices.get(t)
        if _is_missing(live_price_orig):
            live_price_orig = None
            missing_prices.append(t)

        rate_live = _live_rate(curr_t, target_currency, rates_live_cache)
        if _is_missing(rate_live):
            rate_live = None
            if curr_t and curr_t != target_currency:
                missing_fx.append(f"{t} ({curr_t})")

        if live_price_orig is None:
            pos['Current Price'] = float('nan')
            pos['Value Today'] = float('nan')
            pos['FOMO'] = float('nan')
            pos['_FOMO Conv'] = float('nan')
            continue

        value_today_orig = live_price_orig * qty
        pos['Current Price'] = live_price_orig
        pos['Value Today'] = value_today_orig
        pos['FOMO'] = (pos['Sell Price'] * qty) - value_today_orig

        if rate_live is None or _is_missing(proceeds_base):
            pos['_FOMO Conv'] = float('nan')
        else:
            value_today_conv = live_price_orig * rate_live * qty
            pos['_FOMO Conv'] = proceeds_base - value_today_conv

    if missing_prices:
        names = ", ".join(dict.fromkeys(missing_prices))
        warnings.append(
            f"Current price unavailable for sold ticker {names}. "
            "FOMO for those sales is excluded from the totals."
        )
    if missing_fx:
        names = ", ".join(dict.fromkeys(missing_fx))
        warnings.append(
            f"Exchange rate unavailable for {names}. "
            "FOMO totals exclude those sales."
        )

    return pd.DataFrame(closed_positions)
