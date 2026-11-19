# InvestTrack - Code Structure

## 📁 Project Organization

The code has been restructured into a modular architecture to improve readability and maintainability.

```
investtrack/
│
├── app.py                          # Main application entry point
├── config.py                       # Global constants and configurations
│
├── core/                           # Business logic
│   ├── __init__.py
│   ├── portfolio_processor.py      # Portfolio processing, P&L and FOMO calculation
│   ├── storage.py                  # Saving and loading transactions on disk
│   └── transactions.py             # Transaction validation and normalization
│
├── utils/                          # Utility functions
│   ├── __init__.py
│   ├── exchange_rates.py           # Exchange rate management
│   ├── numbers.py                  # Shared numeric helpers (is_missing)
│   └── price_fetcher.py            # Stock price and quote currency download
│
├── ui/                             # User interface components
│   ├── __init__.py
│   ├── state.py                    # Session state synced with the saved file
│   ├── sidebar.py                  # Sidebar with controls
│   ├── transactions_editor.py      # Editable transaction table
│   └── main_view.py                # Main view with metrics and tables
│
└── tests/                          # pytest suite (market data is mocked)
```

## 📄 Module Descriptions

### `app.py` - Entry Point
- Main file that orchestrates the application
- Manages session state initialization
- Coordinates UI component rendering

### `config.py` - Configuration
- Global constants (supported currencies, page title, layout)
- Cache parameters (TTL for prices and quote currencies, max entries)
- FX lookup tolerance and minor-unit currencies (GBp, ZAc, ILA)
- Easy to modify without touching the logic

### `core/portfolio_processor.py` - Business Logic
**Main functions:**
- `process_portfolio()`: Processes transactions and returns a `PortfolioResult`
- `_build_open_positions()`: Builds open positions DataFrame
- `_build_sales_history()`: Builds sales history DataFrame with FOMO

**Responsibilities:**
- Weighted average cost calculation (PMC)
- Realized and unrealized P&L calculation
- FOMO analysis on sales
- Position management (opening/closing)

### `core/transactions.py` - Transactions
**Functions:**
- `normalize_transactions()`: Single validator used by CSV import, the manual form and the processor
- `append_transaction()`: Validates and appends one transaction
- `empty_transactions()`: Empty table with canonical columns and dtypes

### `core/storage.py` - Saved Data
**Functions:**
- `load_transactions()`: Reads and validates the saved file; reports unreadable files or invalid rows
- `save_transactions()`: Atomic write (temp file + replace)
- `data_file_path()`: `data/transactions.csv`, or `INVESTTRACK_DATA_FILE`
- `to_csv_bytes()`: CSV used by both the saved file and the export

### `ui/state.py` - Session State
- `init_session_state()`: Loads the saved file once per session
- `set_transactions()`: The only way to change transactions: updates state, saves, leaves a notice
- `show_notice()`: Shows the notice after the rerun

### `ui/transactions_editor.py` - Transaction Editor
- `render_transactions_editor()`: `st.data_editor` with Save / Discard; validates through `normalize_transactions`

### `utils/exchange_rates.py` - Exchange Rates
**Functions:**
- `get_exchange_rate_history()`: Downloads the full daily history from Yahoo Finance (one download per pair)
- `get_rate_at_date()`: Rate on or before a date; None outside the history or after a long gap
- `get_latest_rate()`: Most recent rate in the series

**Features:**
- Cache with `@st.cache_data`
- Identical currency handling
- Fallback on inverse rates
- Index normalized to naive dates, so lookups do not depend on time zones

### `utils/price_fetcher.py` - Stock Prices
**Functions:**
- `get_current_prices()`: Latest price and listing currency for each ticker
- `get_quote_currency()`: Listing currency reported by Yahoo (cached for a day)
- `to_major_units()`: Converts minor-unit quotes (e.g. pence) to the major unit

**Features:**
- Cache with configurable TTL
- Batch download for efficiency
- Single and multiple ticker handling
- 5-day period to avoid weekend/holiday issues

### `ui/sidebar.py` - Sidebar
**Functions:**
- `render_sidebar()`: Complete sidebar rendering
- `_render_upload_section()`: CSV import section
- `_render_export_section()`: CSV export section
- `_render_transaction_form()`: Transaction entry form

**Responsibilities:**
- Portfolio currency selection
- Manual price refresh (the only control that bypasses the price/FX cache)
- Data Import/Export
- Transaction entry

### `ui/main_view.py` - Main View
**Functions:**
- `render_main_view()`: Complete view with metrics and tables
- `render_empty_state()`: Empty state when there are no transactions
- `_render_metrics()`: Main metrics (value, P&L)
- `_render_open_positions()`: Open positions table
- `_render_sales_history()`: Sales history table
- `_render_fomo_stats()`: FOMO statistics

**Features:**
- Color formatting for P&L (red/green)
- Tabs to separate open positions and sales
- Explanatory tooltips

## 🎯 Advantages of the New Structure

### 1. **Separation of Concerns**
- UI separated from business logic
- Isolated utility functions
- Centralized configuration

### 2. **Maintainability**
- Each file has a specific purpose
- Easy to identify where to modify code
- Reduced complexity per file

### 3. **Testability**
- Independently testable modules
- Pure functions without side effects
- Simplified mocking for tests

### 4. **Reusability**
- Reusable UI components
- Generic utility functions
- Modular business logic

### 5. **Readability**
- More organized and clear code
- Complete docstrings for each function
- Descriptive names and logical structure

## 🔧 How to Modify

### Add a new currency
Modify `config.py`:
```python
CURRENCIES = ["EUR", "USD", "GBP", ..., "NZD"]  # Add here
```

### Modify P&L calculation
Modify `core/portfolio_processor.py` in the functions:
- `_build_open_positions()` for open positions
- `_build_sales_history()` for sales

### Add a new UI component
1. Create function in `ui/sidebar.py` or `ui/main_view.py`
2. Call it from `app.py` in the `main()` function

### Modify price data source
Modify `utils/price_fetcher.py`:
- Replace yfinance with another API
- Maintain the same function interface

## 🚀 Execution

```bash
streamlit run app.py
```

The application will start with the new modular structure, maintaining all the original functionality.
