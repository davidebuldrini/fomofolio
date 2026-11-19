# FOMOfolio - Stock Portfolio Tracker

Single Page Application built with Streamlit for stock portfolio tracking.

## Features
- Weighted Average Cost Calculation
- Realized and Unrealized P&L
- Multi-currency Support (Automatic conversion to portfolio currency)
- FOMO Analysis on Sales
- Export/Import data via CSV (add to or replace existing transactions)
- Transactions saved to disk automatically
- Edit and delete transactions in the Transactions tab

## Data assumptions

Enter quantities and prices already adjusted for splits, consistent with the current Yahoo Finance price. FOMOfolio does not apply stock splits or dividends. A pre-split lot left at the old quantity will not match the live price, and the P&L will be wrong.

Dates in `YYYY-MM-DD` format are read as such. Any other format is read day-first (`03/04/2024` is 3 April).

Each ticker keeps the currency of its first buy. Later rows in a different currency are ignored. If Yahoo quotes the ticker in another currency (for example AAPL bought in EUR, quoted in USD), the live price is converted to the transaction currency at today's rate and a warning is shown.

Listings quoted in minor units (for example London stocks quoted in pence, `GBp`) are converted to the major unit. Record those transactions in GBP.

Portfolio totals are in the selected portfolio currency. If a price or exchange rate is missing, that position is left out of the totals instead of being valued at zero. An exchange rate is treated as missing when the transaction date is before the available history or more than a week after the last quote. On a sale, only the shares you actually hold are included in realized P&L. Buys are processed before sells when they share the same date.

## Saved data

Transactions are saved to `data/transactions.csv` (ignored by git) every time they change: CSV import, the manual form, or the Transactions tab. They are loaded again when the app starts. Set `FOMOFOLIO_DATA_FILE` to use another file:

```bash
FOMOFOLIO_DATA_FILE=~/portfolio.csv streamlit run app.py
```

The file has the same columns as the CSV export. Writes are atomic, so an interrupted save never leaves a half-written file. The file is shared by every browser session of the same app instance.

## Editing transactions

Open the **Transactions** tab to change cells, add rows at the bottom, or select rows and press Delete. Nothing changes until you press **Save changes**; **Discard changes** restores the saved data. Rows with invalid values are listed and nothing is saved until they are fixed.

## Desktop app (macOS and Windows)

FOMOfolio can be packaged as a standalone desktop app with Python included. It opens in a native window, and closing the window stops the app.

Build on macOS (creates `dist/FOMOfolio.app` and a `.dmg`):

```bash
./build_mac.sh
```

Build on Windows (creates `dist\FOMOfolio\FOMOfolio.exe` and a `.zip`):

```powershell
.\build_win.ps1
```

Each build targets the system it runs on (Apple Silicon, Intel Mac or Windows). PyInstaller cannot cross-compile.

The desktop app saves transactions in a per-user folder, not in `data/`:

- macOS: `~/Library/Application Support/FOMOfolio/transactions.csv`
- Windows: `%APPDATA%\FOMOfolio\transactions.csv`

The app was previously called InvestTrack. On first start, transactions saved in the old `InvestTrack` folder are copied to the new one automatically.

To move existing data to the macOS app:

```bash
mkdir -p ~/Library/Application\ Support/FOMOfolio && cp data/transactions.csv ~/Library/Application\ Support/FOMOfolio/
```

The apps are not signed with a developer certificate. The first time, open them with right-click → Open on macOS, or More info → Run anyway on Windows.

### Automatic builds on GitHub

`.github/workflows/build.yml` runs the tests and builds the three versions (macOS arm64, macOS Intel, Windows). Pushing a tag such as `v1.0.0` publishes them in a GitHub Release:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

You can also start it from the Actions tab (Run workflow). The files are then available as run artifacts.

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
