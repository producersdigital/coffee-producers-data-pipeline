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
| **Farmer records** | 8,507 unique farmers across 5 POs |
| **Transaction records** | 102,786 coffee purchase records |
| **Farmer-level inspections** | 12,048 records (multi-year, all POs) |
| **Plot-level inspections** | 13,592 individual plot inspections |
| **Farmer-level harvests** | 8,882 records |
| **Plot-level harvests** | 13,592 records |
| **Technical assistance visits** | 6,646 field visits (Norandino via Kobo API) |
| **Historical depth** | Up to 5 years per organization |
| **Database tables** | 26 normalized MySQL tables |
| **Geographic coverage** | 5 regions across Peru |
| **CEA project plots** | 2,640 farmers linked to CEA soil/crop predictions |
| **SAGRI legacy plots** | 2,694 SAGRI plots, all linked to farmers |
| **Extensionists** | 54 registered field technicians |
| **EUDR deforestation alerts** | 28,895 farm-level alerts (Satelligence, 10 POs) |
| **EUDR due-diligence assessments** | 14 assessments across 7 POs (Osapiens) |
| **EUDR plot findings** | 1,201 plot-level non-compliance records |
| **Commercial contracts** | 46 UK buyer contracts, 844,215 kg |
| **Harvest estimations** | 24,067 producer-year records, 25,267 crop records (Norandino) |
| **Trainings** | 2,520 events, 30,105 participant records (Norandino via Kobo API) |

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
│   ├── kobo_api/                   # Real-time field data (Norandino)
│   │   ├── scripts/
│   │   │   ├── import_kobo_visits.py      # Technical assistance visits
│   │   │   ├── import_kobo_trainings.py   # Trainings + participants
│   │   │   ├── populate_extensionists.py
│   │   │   ├── populate_farmers.py
│   │   │   └── test_download_csv_export.py
│   │   ├── documentation/          # Per-module implementation notes
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
│   ├── estimations/                # Norandino harvest estimation workbooks
│   │   ├── scripts/
│   │   │   ├── clean_estimations.py    # Stage 1: wide Excel → two long CSVs
│   │   │   └── load_estimations.py     # Stage 3: CSVs → SDL
│   │   └── data/                   # Excluded from git (raw + processed)
│   │
│   ├── eudr/                       # EUDR compliance: alerts, assessments, contracts
│   │   ├── scripts/
│   │   │   ├── eudr_loader.py         # Satelligence alerts + PO compliance
│   │   │   ├── osapiens_loader.py     # Due-diligence assessments + plot findings
│   │   │   └── contracts_loader.py    # UK coffee buyer commercial contracts
│   │   └── data/                   # Excluded from git (sheet exports)
│   │
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
- **Org hierarchy capture**: `org_first_level`, `org_coordination` and `base`
  mapped from membership files for POs that report internal structure
- **Member status normalization**: regex repair of mojibake accents
  (`H?bil` → `Hábil`) across inconsistently-encoded exports

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
- **`cea_plot_code` in farmers table**: links CEA project farmers to their plot code — enables joins without storing DNIs in the webapp

### Estimations Module (Norandino harvest forecasts)

- **Nothing is positional-safe**: the source workbook drifts every year, so the
  header row is located by scanning for a `Departamento` token rather than a
  fixed offset, and every column is mapped by regex against normalized header
  text. A required column that fails to map raises — the pipeline never silently
  loads NULLs
- **Self-validating load**: each file's own `TOTAL GENERAL` row is dropped from
  the data, then reused as a control. Loaded coffee kg must equal the file's
  stated total, which catches a future column shift before it reaches the SDL
- **Wide-to-long crop melt**: source files are wide across three crops
  (café / caña / cacao). Melting to long means adding a fourth crop is a data
  change, not a schema migration, and the join to `collection_transactions` is a
  single (year, farmer, crop) join instead of a per-crop column pick
- **Unit drift handled with an audit trail**: panela headers say `QQ DE 50 KGS`
  for 2021–2024 and `KG` from 2025. Verified against the data (panela is a
  derived column, exactly cane × 10%), so quintal years are normalized to kg
  while `source_value` / `source_unit` preserve what arrived
- **Deferred acopio conversion**: `ACOPIO_CONVERSIONS` maps each
  (crop, product_form) to an acopio unit and factor, currently identity. When
  the `collection_transactions` unit is confirmed, set the factor and re-run —
  the load is idempotent and simply rewrites the two acopio columns

### Kobo Trainings Module

- **XLSX, not CSV**: the Capacitaciones form is a repeat-group form whose three
  sheets survive in XLSX and are flattened in CSV. The downloader pulls
  `data_url_xlsx` from a named export; sheets are detected by name pattern, not
  position, so a renamed parent sheet doesn't break the import
- **Unified participants table**: registered and non-registered attendees in one
  table with an `is_registered` flag. Registered rows carry per-profile columns
  (`nombre_completo_socio`, `..._personal`, `..._int`, `..._reforestacion`)
  which are coalesced into single `full_name` / `organization` / `gender` /
  `birth_date` fields
- **Duplicate submission collapse**: Kobo flags accidental resends with a
  `DUPLICATE-<ts>-<n>-<asset>-<uuid>` identifier and clones the repeat children
  too. Parent rows are grouped by the trailing real UUID and the most complete
  copy kept (tie-break: latest submission time, then lowest id); the dropped
  copy's participants are excluded with it
- **Mixed-locale birth dates**: the column holds both `d/m/Y` and `m/d/Y` from
  different devices. Parsed per value with `dayfirst=True` so pandas falls back
  to month-first where day-first is impossible — both unambiguous forms parse
  correctly
- **Soft links by design**: `training_participants.farmer_id` has no constraint
  because many attendees are staff or externals not in `farmers`;
  `extensionist_code` has no FK, so a technician code not yet registered loads
  fine and gains a name on the next dashboard refresh with no re-import. Both
  match rates are printed each run
- **Reported counts kept, not derived**: 218 trainings recorded attendance
  without participant lists, so the enumerator's men/women/total figures are the
  only attendee numbers available for them

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
| `farmers_data` | 8,507 | NO + CH from membership; others from inspections + transactions |
| `farmers_addresses` | 8,507 | Matches farmers exactly |
| `farmer_level_inspections` | 12,048 | All POs, multi-year (2020–2025) |
| `plot_level_inspections` | 13,592 | BG + NO + AP plot data |
| `farmer_level_harvests` | 8,882 | Rows with at least one harvest value |
| `plot_level_harvests` | 13,592 | Plot-level harvest data |
| `acopio_transactions` | 102,786 | All 5 POs, 5 years |

### ✅ Stage 3 Complete — SDL Migration

All core tables loaded to DigitalOcean MySQL 8.0.45 with SSL. Migration uses
resume logic — safe to restart on timeout without data loss. The SDL now holds
26 tables in total, including those loaded by the EUDR, estimations and
trainings modules.

**SDL table counts:**

| Table | Rows |
|-------|------|
| `collection_transactions` | 102,786 |
| `training_participants` | 30,105 |
| `eudr_satelligence_alerts` | 28,895 |
| `collection_estimation_crops` | 25,267 |
| `collection_estimations` | 24,067 |
| `inspections_plot_level` | 13,592 |
| `harvests_plot_level` | 13,592 |
| `inspections_farmer_level` | 12,048 |
| `harvests_farmer_level` | 8,882 |
| `farmers` | 8,507 |
| `farmer_addresses` | 8,507 |
| `technical_assistance_visits` | 6,646 |
| `trainings` | 2,520 |
| `eudr_osapiens_plot_findings` | 1,201 |
| `sagri_soil_data` | 807 |
| `sagri_plots` | 2,694 |
| `eudr_po_compliance` | 72 |
| `extensionists` | 54 |
| `eudr_contracts` | 46 |
| `producer_organizations` | 24 |
| `eudr_osapiens_assessments` | 14 |

Plus five lookup tables (countries, currencies, genders, product types, units).
2,640 farmers carry a `cea_plot_code`.

### ✅ Kobo API Integration Complete

- **54 extensionists** registered from Norandino field teams
- **6,646 technical visits** imported 
- 1,167 visits blocked by 50 former members not appearing in the farmers table (to ask Norandino)
- 17 visits blocked by 3 testing extensionists 
- Duplicate prevention via `kobo_uuid` unique constraint
- Time column capping: out-of-range values (e.g. 90,000,888,888h) automatically set to NULL

### ✅ SAGRI Legacy Soil Data

- **807 records** in `sagri_soil_data` (269 plots × 3 nutrients for Aug-2025)
- `sagri_plots` 2,694 plots, 100% linked to farmers via national_id (including cooperative RUCs).

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


### ✅ Estimations Module

Norandino "Estimado de acopio" workbooks, one per campaign year, cleaned and
loaded into two tables.

| Table | Rows | Grain |
|-------|------|-------|
| `collection_estimations` | 24,067 | one row per producer per year |
| `collection_estimation_crops` | 25,267 | one row per producer-year-crop |

- Control totals reconcile against each file's own `TOTAL GENERAL` row
- `org_id` resolved once per run from `--source-org-code` against
  `producer_organizations` — all current files are Norandino, and the sheet
  never names the cooperative itself
- Dry run reports the farmer match rate against `farmers.national_id` plus
  insert / update / unchanged counts via `row_hash`

### ✅ Kobo Trainings Integration

| Table | Rows |
|-------|------|
| `trainings` | 2,520 |
| `training_participants` | 30,105 |

- Three-sheet repeat-group form imported from a named Kobo XLSX export
- Participants link to trainings by submission id (hard FK, every child verified
  to have a parent); `farmer_id` is a soft link
- Test submissions (`TEST_CODES`) and Kobo-flagged duplicate resends dropped at
  load, both counted in the run summary
- Idempotent: `kobo_uuid` UNIQUE with `ON DUPLICATE KEY UPDATE` for trainings so
  edited submissions re-sync; `row_hash` UNIQUE with `INSERT IGNORE` for
  participants, since Kobo repeat rows have no stable id of their own


### ✅ EUDR Compliance Module

EUDR splits into two halves and the SDL mirrors that split: **deforestation**
monitoring from satellite imagery, and **legal due diligence** from the broker's
compliance platform. Two providers, two independent schemas, joined at the
cooperative and contract level rather than merged.

| Table | Rows | Source |
|-------|------|--------|
| `eudr_satelligence_alerts` | 28,895 | Satelligence monthly export |
| `eudr_po_compliance` | 72 | PO compliance tracking sheet |
| `eudr_osapiens_assessments` | 14 | Osapiens due-diligence export |
| `eudr_osapiens_plot_findings` | 1,201 | Osapiens, plot grain |
| `eudr_contracts` | 46 | UK coffee buyer commercial sheet |

- **Two-table split for Osapiens**: the export is one row per plot, but all
  assessment-level columns repeat identically across every row. Split into
  assessments (14) and plot findings (1,201), eliminating ~99% duplication
- **Contract-to-assessment link**: `purchase_ref_norm` ↔ `doc_id_normalized`
  joins a shipment to the plots that supplied it — the broker runs one Osapiens
  assessment per contract. Reference formats differ (`14-50498` vs
  `IACL_PO50498_FOB`), so both sides normalize to the numeric core
- **Provider-specific date parsing**: Satelligence is month-first (`9/1/2023`),
  Osapiens day-first (`31/12/2025`). Separate parsers — sharing one would
  silently null every day above 12
- **Mixed-language months**: the contracts sheet uses `May-26` alongside
  `Ago-26`, `Set-26`, `Dic-26`, `Ene-27`. `MONTH_MAP` covers both languages
- **Deferred identifier resolution**: Osapiens sends plot IDs in a different
  format per cooperative. Raw values stored with resolution columns left null
  until the plot registry can resolve them authoritatively
- **Idempotent loads**: MD5 row hashes for alerts, assessment hashes for
  Osapiens, natural keys elsewhere — all `ON DUPLICATE KEY UPDATE`

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

### EUDR module
```bash
cd src/eudr/scripts
python eudr_loader.py --dry-run        # validate, write *_CLEAN_PREVIEW.csv
python eudr_loader.py                  # Satelligence alerts + PO compliance
python osapiens_loader.py              # assessments + plot findings
python contracts_loader.py             # UK coffee buyer contracts
```

Export each sheet tab to `src/eudr/data/` under the exact filename the loader
expects. Always dry-run first — the preview shows fill rates and name
resolution before anything touches the database.

### Estimations module
```bash
cd src/estimations/scripts
python clean_estimations.py                              # all years
python clean_estimations.py --year 2026                  # one year
python load_estimations.py --source-org-code NO --dry-run
python load_estimations.py --source-org-code NO
```

### Kobo trainings
```bash
cd src/kobo_api/scripts
python import_kobo_trainings.py --dry-run     # download + process, no writes
python import_kobo_trainings.py               # download live from Kobo, load
python import_kobo_trainings.py --test 50     # only first 50 trainings
python import_kobo_trainings.py --file path/to/export.xlsx   # skip download
```

Trainings requires a named XLSX export called `Trainings` to exist in the Kobo
UI (DATA → Downloads → XLSX, include labels, repeat groups as separate sheets).
The importer finds it by that name.

### Streamlit webapp (local)
```bash
streamlit run src/cea_api/scripts/norandino_mapas.py
```

---

## 🗺️ Roadmap

### Phase 3 — Pending

| Item | Description | Status |
|------|-------------|--------|
| **Plot polygons** | Unified plot registry: points and polygons, multi-format ingest (GeoJSON, KML, Excel), cross-provider identifier resolution | In design |
| **ROTA financial data** | Producers Direct microloan dataset | Awaiting to create connection to Kobo |
| **EUDR dashboards** | Power BI reports for UK buyer — overview, deforestation, due diligence | Mockups approved, build pending |

---

## 🛠️ Technology Stack

**Languages**: Python 3.11+  
**Database**: MySQL 8.0.45 (DigitalOcean managed, SSL)  
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
Develop monitoring tools for EU Deforestation Regulation compliance using plot polygon data, deforestation alert feeds, and legality variables. Skills: GIS, environmental data, climate open soruces, Python.

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
