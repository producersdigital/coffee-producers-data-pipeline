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
4. **Connects** to external APIs for real-time field data and soil analysis predictions
5. **Enables** analytics dashboards and evidence-based decision making

---

## 🌍 Impact & Scope

| Metric | Value |
|--------|-------|
| **Farmer records** | 8,271 unique farmers across 5 POs |
| **Transaction records** | 102,789 coffee purchase records |
| **Inspection records** | 7,455 farmer-level inspection records (multi-year) |
| **Historical depth** | Up to 5 years per organization (Chirinos 2020–2024) |
| **Plot-level records** | 5,394 individual plot inspections |
| **Database tables** | 13 normalized MySQL-ready tables |
| **Geographic coverage** | 5 regions across Peru |
| **Membership coverage** | 5,806 Norandino cooperative members integrated |

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
│   │   └── data_integrator.py      # Main orchestrator
│   │
│   ├── stage3_migration/           # MySQL-ready CSVs → SDL database (pending)
│   │   ├── schema_creator.py
│   │   └── data_migrator.py
│   │
│   ├── kobo_api/                   # Real-time field visit data (Norandino)
│   ├── sagri_api/                  # Soil analysis & yield predictions
│   ├── database/                   # Database connection utilities
│   │
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
│   └── run_stage2.py               # Stage 2 full pipeline runner
│
└── tests/
```

---

## 🔑 Key Technical Features

### Stage 1: Advanced Data Cleaning
- **Multi-year harmonization**: Chirinos inspections unified across 5 years (2020–2024) with column mapping per year
- **Multi-format Excel handling**: Complex multi-row headers, merged cells, variable column structures
- **DNI standardization**: 8-digit zero-padded strings with float/string normalization
- **UTM coordinate conversion**: Zone 17S (EPSG:32717) via `pyproj` for Bagua and Aprocassi
- **Plot aggregation**: Norandino's wide-format 10-plot-per-row structure aggregated to farmer level
- **Stable sorts**: All comparisons use `kind='stable'` to prevent data corruption
- **Verified against notebooks**: Each cleaner has a comparison script confirming row-for-row match

### Stage 2: Intelligent Data Integration
- **Multi-year identity split**: Chirinos data correctly produces 1 row/farmer/year in temporal tables while maintaining 1 row/farmer in identity tables
- **Membership file integration**: Norandino cooperative membership list cross-referenced against inspections and transactions — adds 3,507 members with no inspection activity
- **3-stage transaction linking**: national_id exact match → farmer name exact match → fuzzy name match (90% threshold) — achieves 96%+ linkage rate
- **Synthetic ID generation**: `UNKNOWN_BG_001` pattern for farmers in transactions with no matching record
- **Plot deduplication**: Disambiguation of same-named plots with `#N` suffix; true duplicate removal

### Database Design (SDL)
- **Normalized schema**: Farmers → Inspections → Plots → Transactions → Lookups
- **Referential integrity**: Cascading foreign keys
- **Schema grouping**: master / operational / lookup table separation
- **Multi-PO ready**: `org_code` (BG/HU/CH/NO/AP) as FK throughout

---

## 📊 Current Status

### ✅ Stage 1 Complete — All 5 PO Cleaners

| PO | Inspections | Transactions | Notes |
|----|-------------|--------------|-------|
| **Bagua Grande** | ✅ 422 records | ✅ 4,373 records | 2025 corrected file integrated; UTM Zone 17S |
| **Huadquiña** | ✅ 333 records | ✅ 23,597 records | Perfect match verified |
| **Chirinos** | ✅ 4,028 records (5 years) | ✅ 39,331 records | Multi-year 2020–2024; `año_inspeccion` column |
| **Norandino** | ✅ 2,343 records | ✅ 25,200 records | 10-plot aggregation; wide-format intermediate file |
| **Aprocassi** | ✅ 888 records | ✅ 10,288 records | UTM Zone 17S fix |

All cleaners verified with comparison scripts. Full test coverage against original notebooks.

### ✅ Stage 2 Complete — Data Integration Pipeline

The full integration pipeline is operational and produces 13 MySQL-ready tables:

**Pipeline order:**
```
Load Stage 1 PKLs
  → PO transformers (farmer-level + plot-level per PO)
  → Temporal/identity split (Chirinos multi-year fix)
  → Extract inspection tables
  → Norandino membership integration
  → Build transactions table (incl. Bagua DNI fuzzy matching)
  → Link transactions to farmers (3-stage matching)
  → Add unmatched transaction farmers as External
  → Build addresses from complete farmer table
  → Export to data/mysql_ready/
```

**Final table counts:**

| Table | Records | Location |
|-------|---------|----------|
| `farmers_data` | 8,271 | master/ |
| `farmers_addresses` | 8,271 | operational/ |
| `farmer_level_inspections` | 7,455 | operational/ |
| `plot_level_inspections` | 5,394 | operational/ |
| `farmer_level_harvests` | 4,289 | operational/ |
| `plot_level_harvests` | 5,394 | operational/ |
| `acopio_transactions` | 102,789 | operational/ |
| `lookup_producer_orgs` | 5 | master/ |
| 5 × lookup tables | 7–8 each | lookup/ |

### 🔄 Stage 3 In Progress — MySQL Migration

MySQL schema and migration scripts exist (`stage3_migration/`) but have not yet been run against the production SDL database. The `data/mysql_ready/` CSV exports are the handoff point for this step.

**Next steps:**
1. Run `schema_creator.py` to create SDL tables
2. Run `data_migrator.py` to load all 13 tables
3. Verify row counts and foreign key integrity in MySQL

### 📋 Phase 2 Planned — Second Data Layer

The following datasets are identified for a second integration round into the SDL:

| Dataset | Source | Status |
|---------|--------|--------|
| **ROTA financial data** | Producers Direct financial system | Awaiting data export |
| **Plot polygons** | Chirinos + Norandino field GPS data | Files received, pipeline TBD |
| **Training records** | Bagua Grande + Norandino training logs | Files received, pipeline TBD |
| **EUDR deforestation alerts** | EU deforestation monitoring API | Integration design pending |

**Phase 2 also includes:**
- Kobo Toolbox API → `technical_assistance_visits` table (Norandino)
- Sagri ML API → `sagri_soil_data` + `sagri_plots` tables
- Annual refresh automation for all 5 POs

---

## 🚀 Running the Pipeline

### Prerequisites
```bash
conda activate coffee-data-system
pip install -r requirements.txt
```

### Stage 1 — Clean all POs
```bash
# Run individual cleaners (example)
python scripts/clean_bagua_inspections.py
python scripts/clean_bagua_transactions.py
# ... repeat for all 5 POs
```

### Stage 2 — Full integration
```bash
python scripts/run_stage2.py
```

Outputs are written to `data/mysql_ready/master/`, `operational/`, and `lookup/`.

---

## 🛠️ Technology Stack

**Languages**: Python 3.11+  
**Database**: MySQL 8.0  
**Key Libraries**:

| Library | Purpose |
|---------|---------|
| `pandas` | Data manipulation and pipeline orchestration |
| `numpy` | Numerical operations |
| `openpyxl` | Multi-format Excel file handling |
| `pyproj` | UTM coordinate conversion (Zone 17S) |
| `fuzzywuzzy` + `python-Levenshtein` | Fuzzy farmer name matching |
| `mysql-connector-python` | SDL database connectivity |
| `requests` | Kobo + Sagri API integrations |
| `python-dotenv` | Credential management |

**Development**: Git, VS Code  
**Architecture**: Modular Python classes replacing ad-hoc Jupyter notebooks

---

## 🔒 Data Privacy & Security

- **No sensitive data in repository**: All farmer data, credentials, certificates and raw files excluded via `.gitignore`
- **Canonical ID format**: DNI normalized to 8-digit zero-padded strings throughout
- **Synthetic IDs**: Unmatched farmers receive `UNKNOWN_<ORG>_<N>` IDs — no personal data exposed
- **Credentials**: Database and API credentials managed exclusively via environment variables (`.env`)

---

## 🎓 Collaboration Opportunities

We are actively seeking partnerships with universities and research institutions in data science, agricultural technology, and development economics.

### Priority Research Areas

**1. Sagri Soil Analysis Model Validation** ⭐
Validate predictive accuracy of Sagri's soil analysis and yield forecasting models against actual harvest data from our database. Skills needed: ML validation, agricultural science, statistical analysis.

**2. EUDR Compliance Analytics**
Develop monitoring tools for EU Deforestation Regulation compliance using plot polygon data and deforestation alert feeds. Skills needed: GIS, environmental data, Python.

**3. Yield Prediction & Climate Adaptation**
Time series analysis of productivity trends and their correlation with altitude, soil health, and climate variables. Skills needed: ML, time series, agricultural economics.

**4. Gender Equity & Social Impact**
Analysis of gender indicators across cooperatives and their relationship to farm productivity and PO membership benefits. Skills needed: social science, statistics.

### What We Provide
✅ Real-world agricultural data (anonymizable for research use)  
✅ Direct connection with 5 Producer Organizations for field validation  
✅ Existing database infrastructure ready for analysis  
✅ Technical documentation and data dictionaries  

---

## 📞 Contact

**Project Developer**: Daniela  
**Organization**: Producers Direct  
📧 [sam@producersdirect.org]  
🌐 [producersdirect.org](https://producersdirect.org/)  
💻 [github.com/producersdigital/coffee-producers-data-pipeline](https://github.com/producersdigital/coffee-producers-data-pipeline)
