"""
Configuration constants for FOMOfolio application.
"""

# Supported currencies
CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD", "HKD", "SEK", "NOK", "DKK"]

# Page configuration
PAGE_TITLE = "FOMOfolio - Portfolio Tracker"
PAGE_LAYOUT = "wide"

# Cache TTL (Time To Live) in seconds
PRICE_CACHE_TTL = 3600  # 1 hour
# Listing currency of a ticker rarely changes.
QUOTE_CURRENCY_CACHE_TTL = 86400  # 1 day
# Upper bound on cached entries per function (each refresh creates new keys).
CACHE_MAX_ENTRIES = 64

# A historical FX quote older than this (relative to the transaction date)
# is treated as missing rather than reused.
FX_MAX_GAP_DAYS = 7

# Yahoo quotes some listings in minor units (e.g. pence). Map them to the
# major currency and the divisor that converts the quote.
MINOR_UNIT_CURRENCIES = {
    "GBp": ("GBP", 100.0),
    "GBX": ("GBP", 100.0),
    "ZAc": ("ZAR", 100.0),
    "ILA": ("ILS", 100.0),
}
