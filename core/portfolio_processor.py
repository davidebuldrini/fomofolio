"""
Portfolio processing logic for calculating positions, P&L, and FOMO metrics.
"""
from dataclasses import dataclass, field

import pandas as pd

from core.transactions import normalize_transactions
from utils.exchange_rates import (
    get_exchange_rate_history,
    get_latest_rate,
    get_rate_at_date,
)
from utils.numbers import is_missing
from utils.price_fetcher import get_current_prices


_QTY_EPSILON = 1e-9

# Columns in the portfolio (base) currency. The UI appends the currency code.
VALUE_BASE = 'Current Value (base)'
UNREALIZED_BASE = 'Unrealized P&L (base)'
COST_BASE = 'Cost (base)'
PROCEEDS_BASE = 'Proceeds (base)'
REALIZED_BASE = 'Realized P&L (base)'
FOMO_BASE = 'FOMO (base)'


@dataclass
class PortfolioResult:
    """Everything the UI needs. Totals are in the portfolio currency."""
    open_positions: pd.DataFrame
    sales: pd.DataFrame
    total_value: float = 0.0
    realized_pl: float = 0.0
    unrealized_pl: float = 0.0
    # Cost basis of the open positions included in `unrealized_pl`.
    unrealized_cost: float = 0.0
    warnings: list = field(default_factory=list)

    @property
    def total_pl(self):
        if is_missing(self.realized_pl) or is_missing(self.unrealized_pl):
            return float('nan')
        return self.realized_pl + self.unrealized_pl

    @property
    def unrealized_pl_percent(self):
        if is_missing(self.unrealized_pl) or is_missing(self.unrealized_cost) or self.unrealized_cost <= 0:
            return float('nan')
        return self.unrealized_pl / self.unrealized_cost * 100


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


def _sum_known(series):
    """Sum finite values. Empty input is 0. All-missing input is NaN."""
    if series is None or len(series) == 0:
        return 0.0
    known = pd.to_numeric(series, errors='coerce').dropna()
    if known.empty:
        return float('nan')
    return float(known.sum())


class _RateBook:
    """Exchange rate series fetched once per currency pair and reused."""

    def __init__(self, refresh_key):
        self._refresh_key = refresh_key
        self._series = {}

    def series(self, base, target):
        if base == target:
            return None
        key = (base, target)
        if key not in self._series:
            self._series[key] = get_exchange_rate_history(base, target, refresh_key=self._refresh_key)
        return self._series[key]

    def at(self, base, target, date_tx):
        if base == target:
            return 1.0
        return get_rate_at_date(self.series(base, target), date_tx)

    def latest(self, base, target):
        if base == target:
            return 1.0
        return get_latest_rate(self.series(base, target))


def process_portfolio(df, target_currency, refresh_key=0):
    """
    Calculates portfolio metrics, average cost, P&L, FOMO.
    Separates open positions from sales history.

    Buys are applied before sells on the same date. A sell larger than the
    open quantity realizes P&L only on the shares actually held. Each ticker
    keeps the currency of its first buy; later rows in another currency are
    ignored. When Yahoo quotes a ticker in another currency, the live price is
    converted to the ticker's transaction currency. Missing prices and
    exchange rates stay unknown and are left out of the totals.

    Args:
        df: DataFrame with transaction data
        target_currency: The base currency for portfolio calculations
        refresh_key: Parameter to force price and FX refresh

    Returns:
        PortfolioResult
    """
    if df is None or df.empty:
        return PortfolioResult(pd.DataFrame(), pd.DataFrame())

    df, warnings = normalize_transactions(df)
    if df.empty:
        return PortfolioResult(pd.DataFrame(), pd.DataFrame(), warnings=warnings)

    df['_sort_type'] = df['Type'].map({'BUY': 0, 'SELL': 1})
    # mergesort is stable, so two buys on the same day keep their entry order.
    df = df.sort_values(by=['Date', '_sort_type'], kind='mergesort')

    rates = _RateBook(refresh_key)
    holdings = {}
    closed_positions = []
    realized_amounts = []
    realized_incomplete = False

    for row in df.itertuples(index=False):
        tx_type = row.Type
        ticker = row.Ticker
        qty = row.Qty
        price_orig = row.Price
        curr_orig = row.Currency
        date_tx = row.Date

        position = holdings.setdefault(ticker, _empty_holding())
        if position['currency'] and curr_orig != position['currency']:
            warnings.append(
                f"{tx_type} {ticker} on {date_tx} in {curr_orig} was ignored. "
                f"This ticker is tracked in {position['currency']}."
            )
            continue

        rate = rates.at(curr_orig, target_currency, date_tx)

        if tx_type == 'BUY':
            position['currency'] = curr_orig
            position['qty'] += qty
            position['total_cost_orig'] += qty * price_orig

            if is_missing(rate):
                position['fx_ok'] = False
                warnings.append(
                    f"No exchange rate for {curr_orig} to {target_currency} on {date_tx} ({ticker}). "
                    "That buy is excluded from portfolio-currency P&L."
                )
            elif position['fx_ok']:
                position['total_cost_conv'] += qty * price_orig * rate

            position['pmc_orig'] = position['total_cost_orig'] / position['qty']
            if position['fx_ok']:
                position['pmc_conv'] = position['total_cost_conv'] / position['qty']
            continue

        # SELL
        available = position['qty']
        if available <= _QTY_EPSILON:
            warnings.append(
                f"SELL {ticker} on {date_tx} for {qty:g} shares was ignored because there was no open position."
            )
            continue

        if qty > available + _QTY_EPSILON:
            warnings.append(
                f"SELL {ticker} on {date_tx} for {qty:g} shares exceeds the {available:g} shares held. "
                f"The extra {qty - available:g} shares were excluded from P&L."
            )
            qty = available

        pmc_orig_at_sale = position['pmc_orig']
        pmc_conv_at_sale = position['pmc_conv']

        if position['fx_ok'] and not is_missing(rate):
            proceeds = qty * price_orig * rate
            realized_pl = proceeds - qty * pmc_conv_at_sale
            realized_amounts.append(realized_pl)
        else:
            proceeds = float('nan')
            realized_pl = float('nan')
            realized_incomplete = True
            if is_missing(rate):
                warnings.append(
                    f"No exchange rate for {curr_orig} to {target_currency} on {date_tx} ({ticker}). "
                    "That sale is excluded from realized P&L."
                )
            else:
                warnings.append(
                    f"Realized P&L for {ticker} on {date_tx} is excluded because an earlier "
                    "exchange rate was missing."
                )

        closed_positions.append({
            'Date': date_tx,
            'Ticker': ticker,
            'Qty': qty,
            'Avg Buy Price': pmc_orig_at_sale,
            'Sell Price': price_orig,
            'Value': price_orig * qty,
            PROCEEDS_BASE: proceeds,
            REALIZED_BASE: realized_pl,
            'Currency': position['currency'],
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
    sold_tickers = {pos['Ticker'] for pos in closed_positions}
    quotes = get_current_prices(sorted(set(active_tickers) | sold_tickers), refresh_key=refresh_key)

    ticker_currency = {t: h['currency'] for t, h in holdings.items() if h['currency']}
    live_prices = _live_prices_in_tx_currency(quotes, ticker_currency, rates, warnings)

    df_open = _build_open_positions(active_tickers, holdings, live_prices, rates, target_currency, warnings)
    df_closed = _build_sales_history(closed_positions, live_prices, rates, target_currency, warnings)

    if df_open.empty:
        total_value = unrealized = cost = 0.0
    else:
        total_value = _sum_known(df_open[VALUE_BASE])
        unrealized = _sum_known(df_open[UNREALIZED_BASE])
        included = df_open[UNREALIZED_BASE].notna()
        cost = _sum_known(df_open.loc[included, COST_BASE]) if included.any() else float('nan')

    return PortfolioResult(
        open_positions=df_open,
        sales=df_closed,
        total_value=total_value,
        realized_pl=total_realized_pl,
        unrealized_pl=unrealized,
        unrealized_cost=cost,
        warnings=_unique(warnings),
    )


def _live_prices_in_tx_currency(quotes, ticker_currency, rates, warnings):
    """
    Live price per ticker in the currency its transactions are recorded in.

    When Yahoo quotes the ticker in another currency (e.g. AAPL in USD but
    bought in EUR), the price is converted at the latest rate.
    """
    prices = {}
    converted = []
    unconvertible = []
    for ticker, quote in quotes.items():
        tx_currency = ticker_currency.get(ticker)
        price = quote.get('price')
        quote_currency = quote.get('currency')
        if is_missing(price) or not tx_currency:
            continue
        if not quote_currency or quote_currency == tx_currency:
            prices[ticker] = price
            continue
        rate = rates.latest(quote_currency, tx_currency)
        if is_missing(rate):
            unconvertible.append(f"{ticker} ({quote_currency} to {tx_currency})")
            continue
        prices[ticker] = price * rate
        converted.append(f"{ticker} ({quote_currency} to {tx_currency})")

    if converted:
        warnings.append(
            "Market price converted to the transaction currency at today's rate for "
            f"{', '.join(converted)}. Check that the transactions use the right currency."
        )
    if unconvertible:
        warnings.append(
            f"Market price could not be converted for {', '.join(unconvertible)}. "
            "Those positions are shown without a current price."
        )
    return prices


def _unique(messages):
    return list(dict.fromkeys(messages))


def _build_open_positions(active_tickers, holdings, live_prices, rates, target_currency, warnings):
    """
    Build DataFrame for open positions.

    Display amounts are in the transaction currency. Columns ending in
    "(base)" are in the portfolio currency.
    """
    open_positions = []
    missing_prices = []
    missing_fx = []
    nan = float('nan')

    for t in active_tickers:
        holding = holdings[t]
        qty = holding['qty']
        pmc_orig = holding['pmc_orig']
        pmc_conv = holding['pmc_conv']
        curr_t = holding['currency']

        live_price = live_prices.get(t)
        if is_missing(live_price):
            live_price = None
            missing_prices.append(t)

        rate_live = rates.latest(curr_t, target_currency) if holding['fx_ok'] else None
        if is_missing(rate_live):
            rate_live = None
            missing_fx.append(f"{t} ({curr_t})" if curr_t != target_currency else t)

        current_price = market_value = unrealized = pl_percent = nan
        value_base = unrealized_base = nan
        if live_price is not None:
            current_price = live_price
            market_value = qty * live_price
            unrealized = (live_price - pmc_orig) * qty
            pl_percent = (live_price - pmc_orig) / pmc_orig * 100 if pmc_orig > 0 else nan
            if rate_live is not None:
                value_base = market_value * rate_live
                unrealized_base = value_base - qty * pmc_conv

        open_positions.append({
            'Ticker': t,
            'Qty': qty,
            'Avg Price': pmc_orig,
            'Current Price': current_price,
            'Initial Value': pmc_orig * qty,
            'Current Value': market_value,
            'Unrealized P&L': unrealized,
            'Unrealized P&L %': pl_percent,
            'Currency': curr_t,
            VALUE_BASE: value_base,
            UNREALIZED_BASE: unrealized_base,
            COST_BASE: qty * pmc_conv if holding['fx_ok'] else nan,
        })

    if missing_prices:
        warnings.append(
            f"Current price unavailable for {', '.join(missing_prices)}. "
            "Those positions are excluded from portfolio totals."
        )
    if missing_fx:
        warnings.append(
            f"Portfolio-currency value unavailable for {', '.join(_unique(missing_fx))}. "
            "Those positions are excluded from portfolio totals."
        )

    return pd.DataFrame(open_positions)


def _build_sales_history(closed_positions, live_prices, rates, target_currency, warnings):
    """
    Build DataFrame for sales history with FOMO analysis.

    FOMO is the sale value minus today's value of the same shares, in the
    transaction currency; FOMO (base) is the same difference in portfolio
    currency. Positive FOMO means the sale beat today's price.
    """
    missing_prices = []
    missing_fx = []

    for pos in closed_positions:
        t = pos['Ticker']
        qty = pos['Qty']
        curr_t = pos['Currency']

        live_price = live_prices.get(t)
        if is_missing(live_price):
            missing_prices.append(t)
            pos['Current Price'] = pos['Value Today'] = pos['FOMO'] = pos[FOMO_BASE] = float('nan')
            continue

        rate_live = rates.latest(curr_t, target_currency)
        if is_missing(rate_live):
            rate_live = None
            missing_fx.append(f"{t} ({curr_t})")

        value_today = live_price * qty
        pos['Current Price'] = live_price
        pos['Value Today'] = value_today
        pos['FOMO'] = pos['Value'] - value_today

        if rate_live is None or is_missing(pos[PROCEEDS_BASE]):
            pos[FOMO_BASE] = float('nan')
        else:
            pos[FOMO_BASE] = pos[PROCEEDS_BASE] - value_today * rate_live

    if missing_prices:
        warnings.append(
            f"Current price unavailable for sold ticker {', '.join(_unique(missing_prices))}. "
            "FOMO for those sales is excluded from the totals."
        )
    if missing_fx:
        warnings.append(
            f"Exchange rate unavailable for {', '.join(_unique(missing_fx))}. "
            "FOMO totals exclude those sales."
        )

    return pd.DataFrame(closed_positions)
