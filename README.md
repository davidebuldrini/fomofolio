# InvestTrack - Stock Portfolio Tracker

Single Page Application built with Streamlit for stock portfolio tracking.

## Features
- Weighted Average Cost Calculation
- Realized and Unrealized P&L
- Multi-currency Support (Automatic conversion to portfolio currency)
- FOMO Analysis on Sales
- Export/Import data via CSV

## Data assumptions

Enter quantities and prices already adjusted for splits, consistent with the current Yahoo Finance price. InvestTrack does not apply stock splits or dividends. A pre-split lot left at the old quantity will not match the live price, and the P&L will be wrong.

Dates in `YYYY-MM-DD` format are read as such. Any other format is read day-first (`03/04/2024` is 3 April).

Each ticker keeps the currency of its first buy. Later rows in a different currency are ignored. If Yahoo quotes the ticker in another currency (for example AAPL bought in EUR, quoted in USD), the live price is converted to the transaction currency at today's rate and a warning is shown.

Listings quoted in minor units (for example London stocks quoted in pence, `GBp`) are converted to the major unit. Record those transactions in GBP.

Portfolio totals are in the selected portfolio currency. If a price or exchange rate is missing, that position is left out of the totals instead of being valued at zero. An exchange rate is treated as missing when the transaction date is before the available history or more than a week after the last quote. On a sale, only the shares you actually hold are included in realized P&L. Buys are processed before sells when they share the same date.

Transactions are kept only for the current browser session. Export a CSV to keep them.

## Installation
Make sure you have the virtual environment active.

```bash
pip install -r requirements.txt
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Launch
To launch the application run:

```bash
streamlit run app.py
```
