import datetime as dt

import pandas as pd
import pytest

from core.transactions import (
    DAYFIRST_NOTE,
    MissingColumnsError,
    append_transaction,
    empty_transactions,
    normalize_transactions,
)


def _frame(rows):
    return pd.DataFrame(rows, columns=['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency'])


def test_iso_dates_are_read_as_iso():
    df, messages = normalize_transactions(_frame([['2024-03-04', 'aapl', 'buy', 1, 10, 'usd']]))
    assert df.loc[0, 'Date'] == dt.date(2024, 3, 4)
    assert df.loc[0, 'Ticker'] == 'AAPL'
    assert df.loc[0, 'Type'] == 'BUY'
    assert df.loc[0, 'Currency'] == 'USD'
    assert messages == []


def test_slash_dates_are_day_first():
    df, messages = normalize_transactions(_frame([['03/04/2024', 'AAPL', 'BUY', 1, 10, 'USD']]))
    assert df.loc[0, 'Date'] == dt.date(2024, 4, 3)
    assert DAYFIRST_NOTE in messages


def test_year_first_slash_dates():
    df, _ = normalize_transactions(_frame([['2024/03/04', 'AAPL', 'BUY', 1, 10, 'USD']]))
    assert df.loc[0, 'Date'] == dt.date(2024, 3, 4)


def test_invalid_rows_are_reported_with_line_numbers_and_blank_rows_skipped():
    raw = _frame([
        ['2024-01-01', 'AAPL', 'BUY', 1, 10, 'USD'],
        [None, None, None, None, None, None],
        ['nope', '', 'HOLD', -1, 0, 'XXX'],
    ])
    df, messages = normalize_transactions(raw)
    assert len(df) == 1
    assert len(messages) == 1
    assert messages[0].startswith("Row 4:")
    for reason in ("invalid date", "missing ticker", "BUY or SELL", "quantity", "price", "currency"):
        assert reason in messages[0]


def test_nat_and_timestamps_from_the_editor():
    raw = _frame([
        [pd.Timestamp('2024-01-10'), 'AAPL', 'BUY', 1.0, 10.0, 'USD'],
        [pd.NaT, 'MSFT', None, None, None, None],
    ])
    df, messages = normalize_transactions(raw, first_line=1)
    assert df.loc[0, 'Date'] == dt.date(2024, 1, 10)
    assert len(df) == 1
    assert messages[0].startswith("Row 2: invalid date")


def test_missing_columns_raise():
    with pytest.raises(MissingColumnsError):
        normalize_transactions(pd.DataFrame({'Date': ['2024-01-01']}))


def test_bom_and_spaces_in_headers():
    raw = pd.DataFrame([['2024-01-01', 'AAPL', 'BUY', 1, 10, 'USD']],
                       columns=['﻿Date', ' Ticker', 'Type ', 'Qty', 'Price', 'Currency'])
    df, _ = normalize_transactions(raw)
    assert len(df) == 1


def test_append_transaction_to_empty_keeps_dtypes():
    df, errors = append_transaction(empty_transactions(), {
        'Date': dt.date(2024, 1, 1), 'Ticker': ' msft ', 'Type': 'BUY',
        'Qty': 2.0, 'Price': 100.0, 'Currency': 'USD',
    })
    assert errors == []
    assert df.loc[0, 'Ticker'] == 'MSFT'
    assert df['Qty'].dtype == 'float64'


def test_append_transaction_rejects_invalid():
    base = empty_transactions()
    df, errors = append_transaction(base, {
        'Date': dt.date(2024, 1, 1), 'Ticker': '', 'Type': 'BUY',
        'Qty': 0.0, 'Price': 100.0, 'Currency': 'USD',
    })
    assert df is base
    assert errors
