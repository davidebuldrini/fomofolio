"""
Single entry point for transaction validation and normalization.

CSV imports, the manual form and the portfolio processor all go through
`normalize_transactions`, so the rules live in one place.
"""
import datetime as dt
import math
import re

import pandas as pd

from config import CURRENCIES

REQUIRED_COLUMNS = ['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency']
TX_TYPES = ('BUY', 'SELL')
_YEAR_FIRST = re.compile(r'^(\d{4})[/.](\d{1,2})[/.](\d{1,2})$')
DAYFIRST_NOTE ="Dates not in YYYY-MM-DD format were read as day/month/year."


class MissingColumnsError(ValueError):
    """Raised when the input lacks one or more required columns."""


def empty_transactions():
    """An empty transaction table with the canonical columns and dtypes."""
    return pd.DataFrame({
        'Date': pd.Series(dtype='object'),
        'Ticker': pd.Series(dtype='object'),
        'Type': pd.Series(dtype='object'),
        'Qty': pd.Series(dtype='float64'),
        'Price': pd.Series(dtype='float64'),
        'Currency': pd.Series(dtype='object'),
    })


def _clean_text(series):
    return series.map(lambda v: '' if pd.isna(v) else str(v).strip().upper())


def _parse_one_date(value):
    """
    Returns (datetime.date or None, used_dayfirst).

    ISO dates (YYYY-MM-DD, optionally with a time) are read as such. Other text
    is read day-first (DD/MM/YYYY), the European convention, so 03/04/2024 is
    3 April rather than 4 March.
    """
    if value is None:
        return None, False
    if isinstance(value, pd.Timestamp):
        return (None if pd.isna(value) else value.date()), False
    if isinstance(value, dt.datetime):
        return value.date(), False
    if isinstance(value, dt.date):
        return value, False
    try:
        if pd.isna(value):
            return None, False
    except (TypeError, ValueError):
        return None, False

    text = str(value).strip()
    if not text:
        return None, False
    try:
        return pd.to_datetime(text, format='ISO8601').date(), False
    except (ValueError, TypeError):
        pass
    year_first = _YEAR_FIRST.match(text)
    if year_first:
        try:
            year, month, day = (int(part) for part in year_first.groups())
            return dt.date(year, month, day), False
        except ValueError:
            return None, False
    try:
        return pd.to_datetime(text, dayfirst=True).date(), True
    except (ValueError, TypeError, OverflowError):
        return None, False


def _positive_number(value):
    number = pd.to_numeric(value, errors='coerce')
    if pd.isna(number):
        return None
    number = float(number)
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def normalize_transactions(df, first_line=2):
    """
    Validate and normalize a transaction table.

    A missing required column raises MissingColumnsError. Invalid rows are
    dropped and described individually so the rest can still be used.
    Fully blank rows are dropped silently.

    Args:
        df: raw DataFrame
        first_line: line number of the first data row, used in messages
            (2 for a CSV with a header line)

    Returns:
        tuple: (normalized DataFrame, list of messages)
    """
    data = df.copy()
    data.columns = [str(col).strip().lstrip('﻿') for col in data.columns]
    data = data.loc[:, ~data.columns.duplicated()]
    missing = [col for col in REQUIRED_COLUMNS if col not in data.columns]
    if missing:
        raise MissingColumnsError(
            f"Missing columns: {', '.join(missing)}. Expected {', '.join(REQUIRED_COLUMNS)}."
        )

    data = data[REQUIRED_COLUMNS].reset_index(drop=True)
    kept = []
    messages = []
    used_dayfirst = False

    for offset, raw in enumerate(data.itertuples(index=False, name=None)):
        date_raw, ticker_raw, type_raw, qty_raw, price_raw, curr_raw = raw
        if all(_is_blank(v) for v in raw):
            continue

        reasons = []
        date, dayfirst = _parse_one_date(date_raw)
        if date is None:
            reasons.append("invalid date")

        ticker = '' if _is_blank(ticker_raw) else str(ticker_raw).strip().upper()
        if not ticker or ticker == 'NAN':
            reasons.append("missing ticker")

        tx_type = '' if _is_blank(type_raw) else str(type_raw).strip().upper()
        if tx_type not in TX_TYPES:
            reasons.append("type must be BUY or SELL")

        qty = _positive_number(qty_raw)
        if qty is None:
            reasons.append("quantity must be positive")

        price = _positive_number(price_raw)
        if price is None:
            reasons.append("price must be positive")

        currency = '' if _is_blank(curr_raw) else str(curr_raw).strip().upper()
        if currency not in CURRENCIES:
            reasons.append(f"currency must be one of {', '.join(CURRENCIES)}")

        if reasons:
            messages.append(f"Row {offset + first_line}: {', '.join(reasons)}.")
            continue

        used_dayfirst = used_dayfirst or dayfirst
        kept.append({
            'Date': date,
            'Ticker': ticker,
            'Type': tx_type,
            'Qty': qty,
            'Price': price,
            'Currency': currency,
        })

    if not kept:
        return empty_transactions(), messages

    cleaned = pd.DataFrame(kept, columns=REQUIRED_COLUMNS)
    cleaned['Qty'] = cleaned['Qty'].astype('float64')
    cleaned['Price'] = cleaned['Price'].astype('float64')
    if used_dayfirst:
        messages.append(DAYFIRST_NOTE)
    return cleaned, messages


def _is_blank(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        return False
    return isinstance(value, str) and not value.strip()


def append_transaction(df_tx, row):
    """
    Validate one transaction dict and append it.

    Returns:
        tuple: (new DataFrame, list of error reasons; empty on success)
    """
    cleaned, messages = normalize_transactions(pd.DataFrame([row]), first_line=1)
    if cleaned.empty:
        reasons = [m.split(': ', 1)[-1] for m in messages if m.startswith("Row ")]
        return df_tx, reasons or ["Invalid transaction."]
    if df_tx is None or df_tx.empty:
        return cleaned, []
    return pd.concat([df_tx, cleaned], ignore_index=True), []
