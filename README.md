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

Each ticker keeps the currency of its first buy. Later rows in a different currency are ignored, because the market price from Yahoo is in the listing currency.

London listings (tickers ending in `.L`) are quoted in pence. InvestTrack converts those prices to pounds. Record those transactions in GBP.

Portfolio totals are in the selected portfolio currency. If a price or exchange rate is missing, that position is left out of the totals instead of being valued at zero. On a sale, only the shares you actually hold are included in realized P&L. Buys are processed before sells when they share the same date.

## Installation
Make sure you have the virtual environment active.

```bash
pip install -r requirements.txt
```

## Launch
To launch the application run:

```bash
streamlit run app.py
```
