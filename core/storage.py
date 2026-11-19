"""
Saving and loading transactions on disk.

Transactions are stored as a CSV file with the same columns as the export,
so the saved file can also be opened or imported elsewhere.
"""
import os
import tempfile
from pathlib import Path

import pandas as pd

from core.transactions import REQUIRED_COLUMNS, empty_transactions, normalize_transactions

DEFAULT_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def data_file_path():
    """Location of the saved transactions. Override with INVESTTRACK_DATA_FILE."""
    override = os.environ.get("INVESTTRACK_DATA_FILE")
    return Path(override).expanduser() if override else DEFAULT_DATA_FILE


def to_csv_bytes(df):
    """CSV text for the transaction table (ISO dates, canonical columns)."""
    if df is None or df.empty:
        df = empty_transactions()
    return df[REQUIRED_COLUMNS].to_csv(index=False).encode('utf-8')


def load_transactions(path=None):
    """
    Read saved transactions.

    Returns:
        tuple: (DataFrame, list of messages). A missing file gives an empty
        table and no messages. An unreadable file gives an empty table and an
        error message; the file is left untouched.
    """
    path = Path(path) if path else data_file_path()
    if not path.exists():
        return empty_transactions(), []
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig", skip_blank_lines=False)
        df, messages = normalize_transactions(raw)
    except Exception as e:
        return empty_transactions(), [f"Could not read saved transactions from {path}: {e}"]
    skipped = [m for m in messages if m.startswith("Row ")]
    if skipped:
        messages = [
            f"Some saved rows in {path} are invalid and were not loaded. "
            "They will be dropped from the file the next time transactions change."
        ] + messages
    return df, messages


def save_transactions(df, path=None):
    """
    Write transactions atomically: a crash mid-write never leaves a partial file.

    Raises:
        OSError: when the file cannot be written.
    """
    path = Path(path) if path else data_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".transactions-", suffix=".csv", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(to_csv_bytes(df))
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
