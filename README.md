# Coffee Producer Organizations Data Pipeline

A production-grade data infrastructure project transforming smallholder coffee farmer data management for five Producer Organizations (POs) in Peru, enabling evidence-based decision making, certification compliance, and sustainable farming practices.

---

## 📋 Project Overview

### The Challenge
Five coffee Producer Organizations in Peru manage critical data about **8,000+ smallholder farmers** across **100,000+ transactions** and **5+ years of annual inspections**. This data exists in disparate Excel files with:
- Inconsistent formats across organizations and years
- Manual data entry errors and duplications
- No centralized access for analysis
- Limited ability to track farmer progress over time
- Difficulty generating insights for EUDR compliance and sustainability reporting

### The Solution
This project builds a **production-grade data pipeline** that:
1. **Cleans and standardizes** raw data from multiple sources, formats, and years
2. **Integrates** farmer records across organizations using multi-step identity resolution
3. **Migrates** data to a normalized MySQL Shared Data Layer (SDL) with referential integrity
4. **Connects** to external APIs for real-time field data and predictive model outputs
5. **Enables** analytics dashboards and evidence-based decision making

---

## 🌍 Impact & Scope

| Metric | Value |
|--------|-------|
| **Farmer records** | 7,256 unique farmers across 5 POs |
| **Transaction records** | 102,786 coffee purchase records |
| **Farmer-level inspections** | 12,048 records (multi-year, all POs) |
| **Plot-level inspections** | 13,592 individual plot inspections |
| **Farmer-level harvests** | 8,882 records |
| **Plot-level harvests** | 13,592 records |
| **Technical assistance visits** | 5,668 field visits (Norandino via Kobo API) |
| **Historical depth** | Up to 5 years per organization |
| **Database tables** | 13 normalized MySQL tables |
| **Geographic coverage** | 5 regions across Peru |
| **CEA project plots** | 2,640 farmers linked to CEA soil/crop predictions |
| **SAGRI legacy plots** | 269 plots with Aug-2025 soil nutrient snapshot |
| **Extensionists** | 42 registered field technicians |

---

## 🏗️ Architecture

```
coffee-producers-data-pipeline/
│
├── config/                         # Centralized configuration
│
├── src/
│   ├── stage1_cleaning/            # Raw Excel → Clean standardized PKL files
│   │   ├── inspections/            # One cleaner class per PO (5 files)
│   │   └── transactions/           # One cleaner class per PO (5 files)
│   │
│   ├── stage2_integration/         # Clean PKL → MySQL-ready CSV tables
│   │   ├── po_transformers.py      # PO-specific farmer/plot transformers
│   │   ├── table_extractor.py      # MySQL schema extraction functions
│   │   ├── transactions_processor.py  # DNI matching + unified transactions
│   │   └── data_integrator.py      # Main orchestrator with MEMBERSHIP_CONFIGS
│   │
│   ├── stage3_migration/           # MySQL-ready CSVs → SDL database
│   │   └── data_migrator.py        # Loader with resume logic + reconnection
│   │
│   ├── kobo_api/                   # Real-time field visit data (Norandino)
│   │   ├── scripts/
│   │   │   ├── import_kobo_visits.py
│   │   │   ├── populate_extensionists.py
│   │   │   └── test_download_csv_export.py
│   │   └── data_helpers/           # Extensionist + farmer mapping CSVs
│   │
│   ├── sagri_api/                  # Legacy soil nutrient data (Aug-2025 snapshot)
│   │   ├── scripts/
│   │   │   ├── sync_sagri_to_database.py
│   │   │   ├── populate_sagri_plots.py
│   │   │   └── test_fetch_soil_nutrients.py
│   │   └── documentation/
│   │
│   ├── cea_api/                    # CrossEurAsia predictive model integration
│   │   ├── scripts/
│   │   │   ├── norandino_mapas.py      # Streamlit web app for PO leaders
│   │   │   ├── populate_cea_plots.py   # Updates farmers.cea_plot_code
│   │   │   └── test_fetch_cea_soil.py  # API diagnostic tool
│   │   ├── data/
│   │   │   └── cea_plot_codes.csv      # Clean plot codes for webapp (no DNIs)
│   │   └── documentation/
│   │
│   ├── database/                   # Database connection utilities
│   └── utils/
│       ├── dni_cleaner.py          # National ID validation & standardization
│       ├── file_handler.py         # Multi-format Excel processing
│       ├── column_cleaner.py       # Cross-organization standardization
│       └── mapping_helpers.py      # Shared gender/unit lookup mappers
│
├── data/                           # Excluded from git (sensitive farmer data)
│   ├── raw/                        # Original Excel/CSV source files
│   ├── processed/                  # Stage 1 outputs (cleaned PKL files)
│   └── mysql_ready/                # Stage 2 outputs organized by schema group
│       ├── master/                 # farmers_data, lookup_producer_orgs
│       ├── operational/            # addresses, transactions, inspections, harvests
│       └── lookup/                 # countries, genders, units, currencies, products
│
├── scripts/
│   ├── clean_*.py                  # Stage 1 runner scripts (one per PO per data type)
│   ├── run_stage2.py               # Stage 2 full pipeline runner
│   ├── run_stage3.py               # Stage 3 migration runner (--resume / --fresh)
│   └── update_ex_socios.py         # Mark departed members as Ex-socio
│    
│
└── tests/
```

---

## 🔑 Key Technical Features

### Stage 1: Advanced Data Cleaning
- **Multi-year harmonization**: Chirinos (5 years 2020–2024) and Norandino (3 years 2023–2025) with year-aware column mapping
- **Cumulative Kobo export handling**: Norandino's 2025 Kobo export contains 2023+2024+2025 records — split by `info_general/ciclo` cycle value
- **Multi-format Excel handling**: Complex multi-row headers, merged cells, variable column structures
- **DNI standardization**: 8-digit zero-padded strings via `DNICleaner` utility — consistent across all pipeline stages
- **UTM coordinate conversion**: Zone 17S (EPSG:32717) via `pyproj` for Bagua and Aprocassi
- **Plot aggregation**: Norandino's wide-format 10-plot-per-row structure aggregated to farmer level
- **Encoding normalization**: Mojibake fix for `Ecológico`/`R-Ecológico` variants across file exports
- **Crop type flags**: `inspeccion_cafe`, `inspeccion_panela`, `inspeccion_cacao` (0/1) stored per inspection

### Stage 2: Intelligent Data Integration
- **Membership-first architecture**: `MEMBERSHIP_CONFIGS` dict drives authoritative farmer identity for NO and CH — Scenario A updates ALL fields (name, gender, phone, status, dates) for existing farmers; Scenario C adds new members
- **Multi-year identity split**: All POs produce 1 row/farmer/year in temporal tables while maintaining 1 row/farmer (latest year) in identity tables
- **3-stage transaction linking**: `national_id` exact → farmer name exact → fuzzy name match (90% threshold) — achieves 96%+ linkage rate
- **Ex-socio tracking**: `update_ex_socios.py` compares updated membership files against DB and marks departed members without deleting their historical records

### Stage 3: Production Migration
- **Resume logic**: All loaders skip already-loaded rows via duplicate checks — safe to restart after any crash
- **Transparent reconnection**: `load_transactions()` reconnects automatically on MySQL timeout without data loss
- **FK-ordered operations**: DELETE and INSERT sequences respect foreign key constraints
- **DNI normalization at lookup**: `_get_farmer_id()` normalizes to 8-digit zero-padded format before every query — handles format inconsistencies between CSV and DB

### CrossEurAsia (CEA) API Integration
- **Soil Health model**: 18 soil nutrient maps per plot (pH, OC, OM, N, P, K, and 12 more) via presigned S3 URLs
- **Server-side HTML fetch**: Streamlit webapp fetches map HTML server-side to bypass S3 CORS restrictions — maps render inline without downloads
- **Multi-model ready**: `MODELOS` config dict in `norandino_mapas.py` accepts Crop Health and Yield Estimation 
- **No URL storage**: CEA presigned URLs expire in 1 hour — maps fetched fresh on demand, never stored in DB
- **`cea_plot_code` in farmers table**: Links each of the 2,695 CEA project farmers to their plot code — enables joins without storing DNIs in the webapp

---

## 📊 Current Status

### ✅ Stage 1 Complete — All 5 PO Cleaners

| PO | Inspections | Transactions | Notes |
|----|-------------|--------------|-------|
| **Bagua Grande** | ✅ 422 records | ✅ 4,373 records | UTM Zone 17S conversion |
| **Huadquiña** | ✅ 333 records | ✅ 23,597 records | 2025 inspection year |
| **Chirinos** | ✅ 4,028 records (5 years) | ✅ 39,331 records | Multi-year 2020–2024 |
| **Norandino** | ✅ 6,938 records (3 years) | ✅ 25,200 records | Multi-year 2023–2025; 10-plot wide format |
| **Aprocassi** | ✅ 888 records | ✅ 10,288 records | UTM Zone 17S conversion |

### ✅ Stage 2 Complete — Data Integration Pipeline

| Table | Records | Notes |
|-------|---------|-------|
| `farmers_data` | 7,256 | NO + CH from membership; others from inspections + transactions |
| `farmers_addresses` | 7,256 | Matches farmers exactly |
| `farmer_level_inspections` | 12,048 | All POs, multi-year (2020–2025) |
| `plot_level_inspections` | 13,592 | BG + NO + AP plot data |
| `farmer_level_harvests` | 8,882 | Rows with at least one harvest value |
| `plot_level_harvests` | 13,592 | Plot-level harvest data |
| `acopio_transactions` | 102,786 | All 5 POs, 5 years |

### ✅ Stage 3 Complete — SDL Migration

All 13 tables successfully loaded to DigitalOcean MySQL 8.0 with SSL. Migration uses resume logic — safe to restart on timeout without data loss.

**Final SDL table counts:**

| Table | Rows |
|-------|------|
| `farmers` | 7,256 |
| `farmer_addresses` | 7,256 |
| `inspections_farmer_level` | 12,048 |
| `inspections_plot_level` | 13,592 |
| `harvests_farmer_level` | 8,882 |
| `harvests_plot_level` | 13,592 |
| `collection_transactions` | 102,786 |
| `sagri_plots` | 269 |
| `technical_assistance_visits` | 5,668 |
| `extensionists` | 42 |
| `farmers with cea_plot_code` | 2,640 |

### ✅ Kobo API Integration Complete

- **42 extensionists** registered from Norandino field teams
- **5,668 technical visits** imported (83% of 6,853 total Kobo records)
- 1,167 visits blocked by 50 former members not appearing in the farmers table (to ask Norandino)
- 17 visits blocked by 3 testing extensionists 
- Duplicate prevention via `kobo_uuid` unique constraint
- Time column capping: out-of-range values (e.g. 90,000,888,888h) automatically set to NULL

### ✅ SAGRI Legacy Soil Data

- **807 records** in `sagri_soil_data` (269 plots × 3 nutrients for Aug-2025)
- `sagri_plots` expanded from 269 → 2,695 rows with `farmer_id`, `national_id`, `selected_crop`, `plot_name`

### ✅ CrossEurAsia (CEA) Integration

- **Soil Health API** connected — 18 nutrients per plot, Mar 2026 model
- **Crop Health API** connected — NDVI, GNDVI, NDMI, SAVI, EVI, NDRE, CIRE indices for coffee + cane; latest/history/range modes
- **Streamlit webapp** (`norandino_mapas.py`) — PO leaders select model + plot, interactive maps render inline
- **`cea_plot_code`** column in `farmers` table — 2,640 of 2,695 CEA project farmers linked (55 not yet in SDL)
- Maps fetched server-side to bypass S3 CORS — no downloads, no new tabs
- Yield Estimation API — awaiting URL from CrossEurAsia (May 2026+)

### ✅ Member Status Reconciliation

- **427 Norandino farmers** marked as `Ex-socio` after comparison with April 2026 membership file
- Historical inspection, harvest and transaction records preserved for all ex-socios
- `update_ex_socios.py` — rerunnable each time a new membership file is received

---

## 🚀 Running the Pipeline

### Prerequisites
```bash
conda activate coffee-data-system
pip install -r requirements.txt
```

### Stage 1 — Clean all POs
```bash
python scripts/clean_norandino_inspections.py   # multi-year 2023-2025
python scripts/clean_chirinos_inspections.py    # multi-year 2020-2024
# ... repeat for remaining POs
```

### Stage 2 — Full integration
```bash
python scripts/run_stage2.py
```

### Stage 3 — SDL migration
```bash
python scripts/run_stage3.py --fresh    # first run
python scripts/run_stage3.py --resume   # restart after timeout
```

### Post-migration scripts
```bash
python scripts/update_ex_socios.py --apply          # mark departed members
python src/kobo_api/scripts/populate_extensionists.py
python src/kobo_api/scripts/import_kobo_visits.py   # import field visits
python src/cea_api/scripts/populate_cea_plots.py --apply
```

### Streamlit webapp (local)
```bash
streamlit run src/cea_api/scripts/norandino_mapas.py
```

---

## 🗺️ Roadmap

### Phase 3 — Pending
| Item | Description | Status |
|------|-------------|--------|

| **Plot polygons** | EUDR-compliant polygon table from Chirinos + Norandino GPS data | Partial Files received |
| **ROTA financial data** | Producers Direct microloan dataset | Awaiting files or create connection to Kobo |
| **EUDR** | OSapiens alerts table | Pending migration to SDL |
---

## 🛠️ Technology Stack

**Languages**: Python 3.11+  
**Database**: MySQL 8.0 (DigitalOcean managed, SSL)  
**Web**: Streamlit (deployed on Streamlit Community Cloud)

| Library | Purpose |
|---------|---------|
| `pandas` | Data manipulation and pipeline orchestration |
| `openpyxl` | Multi-format Excel file handling |
| `pyproj` | UTM coordinate conversion (Zone 17S) |
| `fuzzywuzzy` | Fuzzy farmer name matching |
| `mysql-connector-python` | SDL database connectivity |
| `requests` | Kobo + CEA API integrations |
| `streamlit` | Predictive model map viewer webapp |
| `python-dotenv` | Credential management |

---

## 🔒 Data Privacy & Security

- **No sensitive data in repository**: All farmer data, credentials, certificates, and raw files excluded via `.gitignore`
- **DNI normalization**: 8-digit zero-padded strings throughout — consistent lookup across all pipeline stages
- **Webapp CSV**: `cea_plot_codes.csv` contains only plot codes, crop type and plot name — no DNIs, safe for GitHub
- **Credentials**: Database and API credentials managed exclusively via `.env` (never committed)
- **Ex-socio policy**: Departed members are marked `Ex-socio` not deleted — historical transaction and visit data preserved

---

## 🎓 Collaboration Opportunities

We are actively seeking partnerships with universities and research institutions in data science, agricultural technology, and development economics.

### Priority Research Areas

**1. EUDR Compliance Analytics**  
Develop monitoring tools for EU Deforestation Regulation compliance using plot polygon data and deforestation alert feeds. Skills: GIS, environmental data, Python.

**2. Yield Prediction & Climate Adaptation**  
Time series analysis of productivity trends correlated with altitude, soil health, and climate variables. Skills: ML, time series, agricultural economics.

**3. Gender Equity & Social Impact**  
Analysis of gender indicators across cooperatives and their relationship to farm productivity and PO membership benefits. Skills: social science, statistics.

### What We Provide
✅ Real-world agricultural data (anonymizable for research use)  
✅ Direct connection with 5 Producer Organizations for field validation  
✅ Existing database infrastructure ready for analysis  
✅ Technical documentation and data dictionaries  

---

## 📞 Contact

**Organization**: Producers Direct  
📧 [sam@producersdirect.org]  
🌐 [producersdirect.org](https://producersdirect.org/)  
💻 [github.com/producersdigital/coffee-producers-data-pipeline](https://github.com/producersdigital/coffee-producers-data-pipeline)
