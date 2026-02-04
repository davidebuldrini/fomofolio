# InvestTrack - Struttura del Codice

## 📁 Organizzazione del Progetto

Il codice è stato ristrutturato in una architettura modulare per migliorare leggibilità e manutenibilità.

```
investtrack/
│
├── app.py                          # Entry point principale dell'applicazione
├── config.py                       # Costanti e configurazioni globali
│
├── core/                           # Logica di business
│   ├── __init__.py
│   └── portfolio_processor.py      # Elaborazione portfolio, calcolo P&L e FOMO
│
├── utils/                          # Funzioni utilitarie
│   ├── __init__.py
│   ├── exchange_rates.py           # Gestione tassi di cambio
│   └── price_fetcher.py            # Download prezzi azionari
│
└── ui/                             # Componenti interfaccia utente
    ├── __init__.py
    ├── sidebar.py                  # Barra laterale con controlli
    └── main_view.py                # Vista principale con metriche e tabelle
```

## 📄 Descrizione dei Moduli

### `app.py` - Entry Point
- File principale che orchestra l'applicazione
- Gestisce l'inizializzazione dello stato della sessione
- Coordina il rendering dei componenti UI
- Solo ~60 righe vs ~450 righe originali

### `config.py` - Configurazione
- Costanti globali (valute supportate, titolo pagina, layout)
- Parametri di cache (TTL per i prezzi)
- Facile da modificare senza toccare la logica

### `core/portfolio_processor.py` - Logica di Business
**Funzioni principali:**
- `process_portfolio()`: Elabora transazioni e calcola metriche
- `_build_open_positions()`: Costruisce DataFrame posizioni aperte
- `_build_sales_history()`: Costruisce DataFrame cronologia vendite con FOMO

**Responsabilità:**
- Calcolo costo medio ponderato (PMC)
- Calcolo P&L realizzato e non realizzato
- Analisi FOMO sulle vendite
- Gestione delle posizioni (apertura/chiusura)

### `utils/exchange_rates.py` - Tassi di Cambio
**Funzioni:**
- `get_exchange_rate_history()`: Scarica storico tassi di cambio da Yahoo Finance
- `get_rate_at_date()`: Recupera il tasso per una data specifica

**Caratteristiche:**
- Cache con `@st.cache_data`
- Gestione valute identiche
- Fallback su tassi inversi
- Gestione timezone-aware

### `utils/price_fetcher.py` - Prezzi Azionari
**Funzioni:**
- `get_current_prices()`: Scarica prezzi correnti per lista di ticker

**Caratteristiche:**
- Cache con TTL configurabile
- Download batch per efficienza
- Gestione ticker singoli e multipli
- Periodo di 5 giorni per evitare problemi weekend/festivi

### `ui/sidebar.py` - Barra Laterale
**Funzioni:**
- `render_sidebar()`: Rendering completo della sidebar
- `_render_upload_section()`: Sezione import CSV
- `_render_export_section()`: Sezione export CSV
- `_render_transaction_form()`: Form inserimento transazione

**Responsabilità:**
- Selezione valuta portfolio
- Refresh manuale prezzi
- Import/Export dati
- Inserimento transazioni

### `ui/main_view.py` - Vista Principale
**Funzioni:**
- `render_main_view()`: Vista completa con metriche e tabelle
- `render_empty_state()`: Stato vuoto quando non ci sono transazioni
- `_render_metrics()`: Metriche principali (valore, P&L)
- `_render_open_positions()`: Tabella posizioni aperte
- `_render_sales_history()`: Tabella cronologia vendite
- `_render_fomo_stats()`: Statistiche FOMO

**Caratteristiche:**
- Formattazione colori per P&L (rosso/verde)
- Tabs per separare posizioni aperte e vendite
- Tooltips esplicativi

## 🎯 Vantaggi della Nuova Struttura

### 1. **Separazione delle Responsabilità**
- UI separata dalla logica di business
- Funzioni utilitarie isolate
- Configurazione centralizzata

### 2. **Manutenibilità**
- Ogni file ha uno scopo specifico
- Facile individuare dove modificare il codice
- Riduzione della complessità per file

### 3. **Testabilità**
- Moduli indipendenti facilmente testabili
- Funzioni pure senza effetti collaterali
- Mock semplificato per i test

### 4. **Riusabilità**
- Componenti UI riutilizzabili
- Funzioni utilitarie generiche
- Logica di business modulare

### 5. **Leggibilità**
- Codice più organizzato e chiaro
- Docstring complete per ogni funzione
- Nomi descrittivi e struttura logica

## 🔧 Come Modificare

### Aggiungere una nuova valuta
Modifica `config.py`:
```python
CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD"]  # Aggiungi qui
```

### Modificare il calcolo P&L
Modifica `core/portfolio_processor.py` nelle funzioni:
- `_build_open_positions()` per posizioni aperte
- `_build_sales_history()` per vendite

### Aggiungere un nuovo componente UI
1. Crea funzione in `ui/sidebar.py` o `ui/main_view.py`
2. Chiamala da `app.py` nella funzione `main()`

### Modificare la fonte dati dei prezzi
Modifica `utils/price_fetcher.py`:
- Sostituisci yfinance con altra API
- Mantieni la stessa interfaccia della funzione

## 🚀 Esecuzione

```bash
streamlit run app.py
```

L'applicazione si avvierà con la nuova struttura modulare, mantenendo tutte le funzionalità originali.
