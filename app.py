import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- Configurazione Pagina ---
st.set_page_config(page_title="InvestTrack - Portfolio Tracker", layout="wide")

# --- Costanti ---
CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY"]

# --- Funzioni di Supporto ---

@st.cache_data
def get_exchange_rate_history(base_currency, target_currency, period="max"):
    """
    Scarica lo storico del tasso di cambio.
    Ritorna una Series con indice Date e valori rate.
    """
    if base_currency == target_currency:
        return None
    
    # Tenta combinazione diretta (es. EURUSD=X)
    pair = f"{base_currency}{target_currency}=X"
    ticker = yf.Ticker(pair)
    hist = ticker.history(period=period)
    
    if not hist.empty:
        return hist['Close']
    
    # Tenta combinazione inversa (es. USDEUR=X)
    pair_inv = f"{target_currency}{base_currency}=X"
    ticker_inv = yf.Ticker(pair_inv)
    hist_inv = ticker_inv.history(period=period)
    
    if not hist_inv.empty:
        return 1.0 / hist_inv['Close']
        
    return None

def get_rate_at_date(rates_series, date_obj):
    """
    Recupera il tasso di cambio per una data specifica dalla serie storica.
    Usa il metodo 'asof' o il valore più vicino.
    """
    if rates_series is None:
        return 1.0
        
    # Assicuriamo che date_obj sia compatibile con l'indice (tz-naive vs tz-aware)
    # yfinance ritorna spesso tz-aware (UTC). Converto date_obj in timestamp tz-naive per semplicità o viceversa.
    # Approccio semplice: convertire indice serie in date (senza ora/tz)
    
    try:
        # Cerchiamo la data esatta o la precedente disponibile
        ts = pd.Timestamp(date_obj)
        if ts.tzinfo is None and rates_series.index.tz is not None:
             ts = ts.tz_localize(rates_series.index.tz)
        
        # asof trova l'ultimo valore valido fino a quella data
        idx = rates_series.index.get_indexer([ts], method='pad')[0]
        if idx == -1:
            # Se la data è antecedente al primo dato, prendiamo il primo
            return rates_series.iloc[0]
        return rates_series.iloc[idx]
    except Exception as e:
        # Fallback in caso di errore
        return 1.0

@st.cache_data(ttl=3600)
def get_current_prices(tickers):
    """
    Scarica i prezzi attuali per una lista di ticker.
    Usa un periodo di 5g per evitare problemi nei weekend/festivi.
    """
    if not tickers:
        return {}
    
    try:
        # download batch
        # period="5d" per avere margine se oggi non c'è dato
        data = yf.download(tickers, period="5d", group_by='ticker', progress=False)
        prices = {}
        
        # Gestione caso singolo ticker vs multipli
        if len(tickers) == 1:
            t = tickers[0]
            try:
                # yfinance returns DataFrame if MultiIndex or Series/DF depending on version
                # Accesso sicuro: data['Close']
                series = data['Close']
                
                # Handling multi-level column if necessary (usually not for single ticker standard download)
                # Se series è DF per qualche motivo
                if isinstance(series, pd.DataFrame):
                    # Fallback
                    series = series.iloc[:, 0]
                
                # Prendi ultimo valore non-NA
                last_valid = series.dropna()
                if not last_valid.empty:
                    prices[t] = last_valid.iloc[-1]
                else:
                    prices[t] = 0.0
            except:
                prices[t] = 0.0
        else:
            for t in tickers:
                try:
                    if t in data.columns: # Top level ticker check
                        series = data[t]['Close']
                    else:
                        # Fallback se struttura diversa, ma con group_by='ticker' dovrebbe essere cosi
                        prices[t] = 0.0
                        continue
                        
                    last_valid = series.dropna()
                    if not last_valid.empty:
                        prices[t] = last_valid.iloc[-1]
                    else:
                         prices[t] = 0.0
                except:
                    prices[t] = 0.0 
        return prices
    except Exception as e:
        # Loggare l'errore ma non bloccare tutto
        print(f"Errore scaricamento prezzi: {e}")
        return {}

# --- Logica Core ---

def process_portfolio(df, target_currency):
    """
    Calcola metriche portafoglio, PMC, P&L, FOMO.
    Tutto convertito in target_currency.
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0, 0.0

    df = df.sort_values(by='Date')
    
    holdings = {} # {ticker: {'qty': 0, 'total_cost': 0, 'pmc': 0}}
    history_rows = []
    
    # Pre-fetch exchange rates per valute coinvolte
    currencies_in_use = df['Currency'].unique()
    rates_cache = {}
    for curr in currencies_in_use:
        if curr != target_currency:
            rates_cache[curr] = get_exchange_rate_history(curr, target_currency)
    
    total_realized_pl = 0.0
    
    for index, row in df.iterrows():
        t = row['Ticker']
        qty = row['Qty']
        price_orig = row['Price']
        curr_orig = row['Currency']
        date_tx = row['Date'] # datetime.date
        
        # Setup holdings se nuovo
        if t not in holdings:
            holdings[t] = {'qty': 0, 'total_cost': 0.0, 'pmc': 0.0}
            
        # Get Exchange Rate
        if curr_orig == target_currency:
            rate = 1.0
        else:
            rate_series = rates_cache.get(curr_orig)
            rate = get_rate_at_date(rate_series, date_tx)
            
        price_conv = price_orig * rate
        
        if row['Type'] == 'BUY':
            # Aggiorna PMC
            prev_qty = holdings[t]['qty']
            prev_cost = holdings[t]['total_cost']
            
            # Costo aggiuntivo
            add_cost = qty * price_conv
            
            new_qty = prev_qty + qty
            new_total_cost = prev_cost + add_cost
            
            holdings[t]['qty'] = new_qty
            holdings[t]['total_cost'] = new_total_cost
            if new_qty > 0:
                holdings[t]['pmc'] = new_total_cost / new_qty
            
            history_rows.append({
                'Date': date_tx, 'Ticker': t, 'Type': 'BUY', 'Qty': qty, 
                'Price': price_orig, 'Currency': curr_orig, 'Rate': rate,
                'Price_Base': price_conv, 'Total': price_conv * qty, 'Realized_PL': 0.0, 'FOMO_PL': None
            })
            
        elif row['Type'] == 'SELL':
            # Calcola Realized P&L
            prev_pmc = holdings[t]['pmc']
            proceeds = qty * price_conv
            cost_basis = qty * prev_pmc
            
            realized_pl = proceeds - cost_basis
            total_realized_pl += realized_pl
            
            # Aggiorna holding (riduci quantità e costo totale proporzionalmente)
            holdings[t]['qty'] -= qty
            holdings[t]['total_cost'] -= cost_basis # Rimuovi 'valore' al costo
            
            # Se qty va a 0, resetta total_cost (per evitare errori di float rounding)
            if holdings[t]['qty'] <= 1e-9:
                holdings[t]['qty'] = 0
                holdings[t]['total_cost'] = 0.0
                holdings[t]['pmc'] = 0.0 # Reset PMC se posizione chiusa? O mantieni? Solitamente reset se riapri.
                # Ma prompt dice "Su SELL: Il PMC non cambia". Se vendo tutto e ricompro?
                # Se vendo tutto, quantità è 0. Se ricompro, è nuovo PMC. Corretto.
            
            history_rows.append({
                'Date': date_tx, 'Ticker': t, 'Type': 'SELL', 'Qty': qty, 
                'Price': price_orig, 'Currency': curr_orig, 'Rate': rate,
                'Price_Base': price_conv, 'Total': price_conv * qty, 'Realized_PL': realized_pl, 'FOMO_PL': None # Placeholder
            })

    # --- Live Data ---
    active_tickers = [t for t, data in holdings.items() if data['qty'] > 0]
    sold_tickers_history = [t for t in df[df['Type'] == 'SELL']['Ticker'].unique()]
    all_tickers_needed = list(set(active_tickers + sold_tickers_history))
    
    current_prices = get_current_prices(all_tickers_needed)
    
    # Valuta Target per prezzi attuali
    # Attenzione: i prezzi live sono nella valuta del ticker su Yahoo!
    # Yahoo tickers suffix determina valuta (es .MI = EUR, nient = USD).
    # Dobbiamo sapere la valuta del Ticker LIVE.
    # Semplificazione: Assumiamo che la valuta in input 'Currency' sia quella corretta del ticker.
    # Recuperiamo l'ultimo currency usato per quel ticker?
    # O semplicemente usiamo yfinance info? yfinance info è lento.
    # Useremo la valuta indicata nelle transazioni come valuta "nativa" di quel titolo.
    
    ticker_currencies = {}
    for t in df['Ticker'].unique():
        ticker_currencies[t] = df[df['Ticker'] == t].iloc[0]['Currency']
        
    rates_live_cache = {}
    for curr in set(ticker_currencies.values()):
        if curr != target_currency:
            rates_live_cache[curr] = get_exchange_rate_history(curr, target_currency, period="5d") # short period for live
            
    # --- Costruzione Tabella Posizioni Attuali ---
    positions = []
    total_unrealized_pl = 0.0
    total_value = 0.0
    
    for t in active_tickers:
        qty = holdings[t]['qty']
        pmc = holdings[t]['pmc']
        curr_t = ticker_currencies.get(t, target_currency)
        
        # Prezzo live
        live_price_orig = current_prices.get(t, 0.0)
        
        # Conversione live al tasso odierno
        if curr_t == target_currency:
             rate_live = 1.0
        else:
             # Prendi ultimo tasso disponibile
             rs = rates_live_cache.get(curr_t)
             rate_live = rs.iloc[-1] if rs is not None and not rs.empty else 1.0
             
        live_price_conv = live_price_orig * rate_live
        
        market_value = qty * live_price_conv
        unrealized_pl = (live_price_conv - pmc) * qty
        
        total_value += market_value
        total_unrealized_pl += unrealized_pl
        
        positions.append({
            'Ticker': t,
            'Qtà': qty,
            'PMC': round(pmc, 2),
            'Prezzo Attuale': round(live_price_conv, 2),
            'Valore': round(market_value, 2),
            'P&L Latente': round(unrealized_pl, 2),
            'Currency': target_currency
        })
        
    # --- Calcolo FOMO su Storico ---
    history_df = pd.DataFrame(history_rows)
    if not history_df.empty:
        # Arricchisci rows SELL con FOMO
        # FOMO: (Valore Oggi - Incasso Reale)
        # Incasso Reale = (Price * Rate_at_tx) * Qty = Price_Base * Qty
        # Valore Oggi = (Live_Price * Rate_Today) * Qty
        
        for idx in history_df.index:
            if history_df.loc[idx, 'Type'] == 'SELL':
                t = history_df.loc[idx, 'Ticker']
                qty = history_df.loc[idx, 'Qty']
                sold_cashed_base = history_df.loc[idx, 'Price_Base'] * qty
                
                curr_t = ticker_currencies.get(t, target_currency)
                live_price_orig = current_prices.get(t, 0.0)
                
                 # Conversione live
                if curr_t == target_currency:
                     rate_live = 1.0
                else:
                     rs = rates_live_cache.get(curr_t)
                     rate_live = rs.iloc[-1] if rs is not None and not rs.empty else 1.0
                
                value_today = live_price_orig * rate_live * qty
                
                fomo = value_today - sold_cashed_base
                history_df.loc[idx, 'FOMO_PL'] = fomo

        # --- Arricchimento Storico con Prezzo Attuale e Totale Transazione ---
        # 1. Totale Transazione (Valore storico pagato/incassato)
        history_df['Total'] = history_df['Price_Base'] * history_df['Qty']
        
        # 2. Prezzo Attuale per ogni riga
        # Mappa i prezzi correnti su ogni riga dello storico
        current_prices_list = []
        for idx in history_df.index:
            t = history_df.loc[idx, 'Ticker']
            curr_t = ticker_currencies.get(t, target_currency)
            live_price_orig = current_prices.get(t, 0.0)
            
            # Conversione
            if curr_t == target_currency:
                 rate_live = 1.0
            else:
                 rs = rates_live_cache.get(curr_t)
                 # Usa ultimo tasso disponibile, o 1.0
                 rate_live = rs.iloc[-1] if rs is not None and not rs.empty else 1.0
                 
            current_prices_list.append(live_price_orig * rate_live)
            
        history_df['Current_Price'] = current_prices_list

    return pd.DataFrame(positions), history_df, total_value, total_realized_pl, total_unrealized_pl

# --- Init Session State ---
if 'df_tx' not in st.session_state:
    st.session_state.df_tx = pd.DataFrame(columns=['Date', 'Ticker', 'Type', 'Qty', 'Price', 'Currency'])

# --- Sidebar ---
with st.sidebar:
    st.title("Gestione Portafoglio")
    
    # 1. Impostazioni Valuta
    target_currency = st.selectbox("Valuta Portafoglio", CURRENCIES, index=0) # Default EUR
    st.divider()
    
    # 1.5 Refresh Manuale
    if st.button("🔄 Aggiorna Prezzi"):
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    
    # 2. Upload
    st.header("Importa Dati")
    uploaded_file = st.file_uploader("Carica CSV", type=['csv'])
    if uploaded_file is not None:
        if st.button("Carica da CSV"):
            try:
                st.cache_data.clear() # Reset cache on new upload
                df_loaded = pd.read_csv(uploaded_file)
                # Conversione Date necessarie
                df_loaded['Date'] = pd.to_datetime(df_loaded['Date']).dt.date
                st.session_state.df_tx = df_loaded
                st.success("Dati caricati! Cache Tassi/Prezzi resettata.")
                st.rerun()
            except Exception as e:
                st.error(f"Errore caricamento: {e}")
                
    st.divider()
    
    # 3. Export
    st.header("Esporta Dati")
    csv_data = st.session_state.df_tx.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Scarica CSV Attuale",
        csv_data,
        "portfolio_data.csv",
        "text/csv",
        key='download-csv'
    )
    
    st.divider()
    
    # 4. Form Manuale
    st.header("Nuova Transazione")
    with st.form("add_tx_form"):
        date_in = st.date_input("Data", datetime.today())
        ticker_in = st.text_input("Ticker (es. AAPL)", "").upper()
        type_in = st.selectbox("Tipo", ["BUY", "SELL"])
        qty_in = st.number_input("Quantità", min_value=0.0, step=1.0)
        price_in = st.number_input("Prezzo Unitario", min_value=0.0, step=0.01)
        curr_in = st.selectbox("Valuta Originale", CURRENCIES, index=1) # Default USD
        
        submitted = st.form_submit_button("Aggiungi Transazione")
        if submitted:
            if ticker_in and qty_in > 0 and price_in > 0:
                new_row = {
                    'Date': date_in,
                    'Ticker': ticker_in,
                    'Type': type_in,
                    'Qty': qty_in,
                    'Price': price_in,
                    'Currency': curr_in
                }
                st.session_state.df_tx = pd.concat([st.session_state.df_tx, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Transazione aggiunta!")
                st.rerun()
            else:
                st.error("Dati mancanti o invalidi.")

# --- Main Page ---
st.title("📈 Stock Portfolio Tracker")

# Processing
if not st.session_state.df_tx.empty:
    # Assicurati che Date sia datetime.date per ordinamento corretto
    st.session_state.df_tx['Date'] = pd.to_datetime(st.session_state.df_tx['Date']).dt.date
    
    with st.spinner('Elaborazione dati e tassi di cambio...'):
        df_pos, df_hist, val_tot, pl_real, pl_unreal = process_portfolio(st.session_state.df_tx, target_currency)
    
    # Header Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valore Totale", f"{val_tot:,.2f} {target_currency}")
    col2.metric("P&L Latente (Non Realizzato)", f"{pl_unreal:,.2f} {target_currency}", delta=f"{pl_unreal:,.2f}")
    col3.metric("P&L Realizzato", f"{pl_real:,.2f} {target_currency}", delta=f"{pl_real:,.2f}")
    
    # P&L Totale
    pl_total = pl_real + pl_unreal
    col4.metric("P&L Complessivo", f"{pl_total:,.2f} {target_currency}", delta=f"{pl_total:,.2f}")
    
    st.divider()
    
    # Tab 1: Posizioni
    st.subheader("Posizioni Attuali")
    if not df_pos.empty:
        st.dataframe(df_pos.style.format({
            "PMC": "{:.2f}", 
            "Prezzo Attuale": "{:.2f}",
            "Valore": "{:.2f}",
            "P&L Latente": "{:.2f}"
        }), use_container_width=True)
    else:
        st.info("Nessuna posizione aperta.")
        
    st.divider()
    
    # Tab 2: Storico e FOMO
    st.subheader("Storico Operazioni & FOMO")
    
    # Formattazione Colonne
    st.dataframe(
        df_hist.sort_values(by='Date', ascending=False).style.format({
            "Price": "{:.2f}",
            "Price_Base": "{:.2f}",
            "Total": "{:.2f}",
            "Current_Price": "{:.2f}",
            "Rate": "{:.4f}",
            "Realized_PL": "{:.2f}", 
            "FOMO_PL": "{:.2f}"
        }, na_rep="-"),
        use_container_width=True
    )
    
else:
    st.info("Nessuna transazione presente. Usa la sidebar per caricare un CSV o aggiungere transazioni manualmente.")
