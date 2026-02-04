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
│   └── portfolio_processor.py      # Portfolio processing, P&L and FOMO calculation
│
├── utils/                          # Utility functions
│   ├── __init__.py
│   ├── exchange_rates.py           # Exchange rate management
│   └── price_fetcher.py            # Stock price download
│
└── ui/                             # User interface components
    ├── __init__.py
    ├── sidebar.py                  # Sidebar with controls
    └── main_view.py                # Main view with metrics and tables
```

## 📄 Module Descriptions

### `app.py` - Entry Point
- Main file that orchestrates the application
- Manages session state initialization
- Coordinates UI component rendering
- Only ~60 lines vs ~450 original lines

### `config.py` - Configuration
- Global constants (supported currencies, page title, layout)
- Cache parameters (TTL for prices)
- Easy to modify without touching the logic

### `core/portfolio_processor.py` - Business Logic
**Main functions:**
- `process_portfolio()`: Processes transactions and calculates metrics
- `_build_open_positions()`: Builds open positions DataFrame
- `_build_sales_history()`: Builds sales history DataFrame with FOMO

**Responsibilities:**
- Weighted average cost calculation (PMC)
- Realized and unrealized P&L calculation
- FOMO analysis on sales
- Position management (opening/closing)

### `utils/exchange_rates.py` - Exchange Rates
**Functions:**
- `get_exchange_rate_history()`: Downloads historical exchange rates from Yahoo Finance
- `get_rate_at_date()`: Retrieves the rate for a specific date

**Features:**
- Cache with `@st.cache_data`
- Identical currency handling
- Fallback on inverse rates
- Timezone-aware handling

### `utils/price_fetcher.py` - Stock Prices
**Functions:**
- `get_current_prices()`: Downloads current prices for a list of tickers

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
- Manual price refresh
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
CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD"]  # Add here
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
