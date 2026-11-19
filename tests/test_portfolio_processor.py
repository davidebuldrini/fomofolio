import datetime as dt
import math

import pandas as pd
import pytest

import core.portfolio_processor as pp


def _series(start, values):
    index = pd.date_range(start, periods=len(values), freq='D')
    return pd.Series(values, index=index, dtype='float64')


@pytest.fixture
def market(monkeypatch):
    """Fake prices and FX. Tests fill `quotes` and `fx` before calling process."""
    state = {'quotes': {}, 'fx': {}}

    def fake_prices(tickers, refresh_key=0):
        return {t: state['quotes'][t] for t in tickers if t in state['quotes']}

    def fake_fx(base, target, refresh_key=0):
        return state['fx'].get((base, target))

    monkeypatch.setattr(pp, 'get_current_prices', fake_prices)
    monkeypatch.setattr(pp, 'get_exchange_rate_history', fake_fx)
    return state


def _tx(*rows):
    return pd.DataFrame(rows, columns=['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency'])


def test_average_cost_and_unrealized_same_currency(market):
    market['quotes'] = {'AAPL': {'price': 15.0, 'currency': 'USD'}}
    res = pp.process_portfolio(_tx(
        ['2024-01-01', 'AAPL', 'BUY', 100, 10, 'USD'],
        ['2024-01-02', 'AAPL', 'BUY', 50, 12, 'USD'],
    ), 'USD')
    row = res.open_positions.iloc[0]
    assert row['Avg Price'] == pytest.approx(1600 / 150)
    assert res.total_value == pytest.approx(150 * 15)
    assert res.unrealized_pl == pytest.approx(150 * 15 - 1600)
    assert res.unrealized_pl_percent == pytest.approx((2250 - 1600) / 1600 * 100)
    assert res.realized_pl == 0.0


def test_partial_and_excess_sell(market):
    market['quotes'] = {'AAPL': {'price': 20.0, 'currency': 'USD'}}
    res = pp.process_portfolio(_tx(
        ['2024-01-01', 'AAPL', 'BUY', 10, 10, 'USD'],
        ['2024-01-05', 'AAPL', 'SELL', 4, 15, 'USD'],
        ['2024-01-06', 'AAPL', 'SELL', 10, 15, 'USD'],
    ), 'USD')
    assert res.open_positions.empty
    assert res.realized_pl == pytest.approx(10 * 5)
    assert list(res.sales['Qty']) == [4, 6]
    assert any('exceeds' in w for w in res.warnings)
    # FOMO: sold at 15, now 20 -> negative.
    assert res.sales['FOMO'].iloc[0] == pytest.approx(4 * 15 - 4 * 20)


def test_buy_before_sell_on_same_day(market):
    market['quotes'] = {'X': {'price': 10.0, 'currency': 'USD'}}
    res = pp.process_portfolio(_tx(
        ['2024-01-01', 'X', 'SELL', 5, 12, 'USD'],
        ['2024-01-01', 'X', 'BUY', 5, 10, 'USD'],
    ), 'USD')
    assert res.realized_pl == pytest.approx(10)


def test_fx_conversion_uses_historical_and_latest_rate(market):
    market['quotes'] = {'AAPL': {'price': 110.0, 'currency': 'USD'}}
    # USD->EUR: 0.9 on the buy date, 0.8 most recently.
    market['fx'] = {('USD', 'EUR'): _series('2024-01-01', [0.9, 0.85, 0.8])}
    res = pp.process_portfolio(_tx(['2024-01-01', 'AAPL', 'BUY', 1, 100, 'USD']), 'EUR')
    assert res.total_value == pytest.approx(110 * 0.8)
    assert res.unrealized_pl == pytest.approx(110 * 0.8 - 100 * 0.9)


def test_date_before_fx_history_is_missing_not_first_rate(market):
    market['quotes'] = {'AAPL': {'price': 110.0, 'currency': 'USD'}}
    market['fx'] = {('USD', 'EUR'): _series('2024-01-01', [0.9, 0.8])}
    res = pp.process_portfolio(_tx(['2020-01-01', 'AAPL', 'BUY', 1, 100, 'USD']), 'EUR')
    assert math.isnan(res.total_value)
    assert any('No exchange rate' in w for w in res.warnings)


def test_quote_currency_differs_from_transaction_currency(market):
    # Bought in EUR, Yahoo quotes in USD: price converted USD->EUR.
    market['quotes'] = {'AAPL': {'price': 200.0, 'currency': 'USD'}}
    market['fx'] = {('USD', 'EUR'): _series('2024-01-01', [0.9, 0.9])}
    res = pp.process_portfolio(_tx(['2024-01-01', 'AAPL', 'BUY', 1, 150, 'EUR']), 'EUR')
    assert res.open_positions.iloc[0]['Current Price'] == pytest.approx(180)
    assert res.total_value == pytest.approx(180)
    assert any('converted to the transaction currency' in w for w in res.warnings)


def test_missing_price_is_excluded_not_zero(market):
    market['quotes'] = {'A': {'price': 10.0, 'currency': 'USD'}}
    res = pp.process_portfolio(_tx(
        ['2024-01-01', 'A', 'BUY', 1, 5, 'USD'],
        ['2024-01-01', 'B', 'BUY', 1, 5, 'USD'],
    ), 'USD')
    assert res.total_value == pytest.approx(10)
    assert res.unrealized_cost == pytest.approx(5)
    assert any('Current price unavailable for B' in w for w in res.warnings)


def test_other_currency_row_is_ignored(market):
    market['quotes'] = {'A': {'price': 10.0, 'currency': 'USD'}}
    res = pp.process_portfolio(_tx(
        ['2024-01-01', 'A', 'BUY', 1, 5, 'USD'],
        ['2024-01-02', 'A', 'BUY', 1, 5, 'EUR'],
    ), 'USD')
    assert res.open_positions.iloc[0]['Qty'] == 1
    assert any('tracked in USD' in w for w in res.warnings)


def test_empty_input():
    res = pp.process_portfolio(pd.DataFrame(), 'EUR')
    assert res.open_positions.empty and res.sales.empty
    assert res.total_value == 0.0
