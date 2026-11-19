import datetime as dt

import pandas as pd

from core.storage import data_file_path, load_transactions, save_transactions
from core.transactions import normalize_transactions


def _sample():
    df, _ = normalize_transactions(pd.DataFrame(
        [['2024-01-02', 'AAPL', 'BUY', 1.5, 100.25, 'USD'],
         ['2024-02-03', 'ENI.MI', 'SELL', 2, 13, 'EUR']],
        columns=['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency'],
    ))
    return df


def test_missing_file_is_empty_without_messages(tmp_path):
    df, messages = load_transactions(tmp_path / "none.csv")
    assert df.empty
    assert messages == []


def test_round_trip(tmp_path):
    path = tmp_path / "sub" / "tx.csv"
    save_transactions(_sample(), path)
    df, messages = load_transactions(path)
    assert messages == []
    assert len(df) == 2
    assert df.loc[0, 'Date'] == dt.date(2024, 1, 2)
    assert df.loc[0, 'Qty'] == 1.5
    assert df.loc[1, 'Type'] == 'SELL'


def test_save_empty_writes_header_only(tmp_path):
    path = tmp_path / "tx.csv"
    save_transactions(_sample().iloc[0:0], path)
    assert path.read_text().strip() == "Date,Ticker,Type,Qty,Price,Currency"
    df, _ = load_transactions(path)
    assert df.empty


def test_save_leaves_no_temp_files(tmp_path):
    path = tmp_path / "tx.csv"
    save_transactions(_sample(), path)
    save_transactions(_sample(), path)
    assert [p.name for p in tmp_path.iterdir()] == ["tx.csv"]


def test_invalid_saved_rows_are_reported(tmp_path):
    path = tmp_path / "tx.csv"
    path.write_text("Date,Ticker,Type,Qty,Price,Currency\n2024-01-01,AAPL,BUY,1,10,USD\nbad,,,,,\n")
    df, messages = load_transactions(path)
    assert len(df) == 1
    assert "invalid" in messages[0]


def test_unreadable_file_is_reported(tmp_path):
    path = tmp_path / "tx.csv"
    path.write_text("just,some\nother,columns\n")
    df, messages = load_transactions(path)
    assert df.empty
    assert "Could not read" in messages[0]


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("FOMOFOLIO_DATA_FILE", str(tmp_path / "x.csv"))
    assert data_file_path() == tmp_path / "x.csv"
