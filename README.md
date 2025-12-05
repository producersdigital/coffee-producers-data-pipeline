# Coffee Producer Organizations Data Pipeline

A comprehensive data cleaning, integration, and migration pipeline for five coffee producer organizations in Peru, migrating from Excel/CSV-based workflows to a normalized MySQL database structure.

## Overview

This project transforms raw inspection and transaction data from multiple Producer Organizations into a clean, integrated MySQL database with proper foreign key relationships and data integrity controls.

### Producer Organizations
- **Bagua** (Amazonas)
- **Huadquiña** (Ayacucho)
- **Chirinos** (Cajamarca)
- **Norandino** (Piura)
- **Aprocassi** (San Martín)

## Architecture
```
coffee-producers-data-pipeline/
├── config/
│   └── paths.py              # Centralized path configuration
├── src/
│   ├── stage1_cleaning/      # Raw data cleaning by PO
│   │   ├── inspections/
│   │   │   ├── bagua_inspections_cleaner.py
│   │   │   ├── huadquina_inspections_cleaner.py
│   │   │   ├── chirinos_inspections_cleaner.py
│   │   │   ├── norandino_inspections_cleaner.py
│   │   │   └── aprocassi_inspections_cleaner.py
│   │   └── transactions/
│   │       ├── bagua_transactions_cleaner.py
│   │       └── ...
│   ├── stage2_integration/   # Data integration & foreign keys
│   ├── stage3_migration/     # MySQL database loading
│   ├── stage4_api_sync/      # Real-time API integrations
│   │   ├── kobo_visits/      # Kobo API for Norandino visits
│   │   └── sagri_predictions/ # Sagri soil predictions API
│   └── utils/                # Shared utilities
├── data/                     # Excluded from git
│   ├── raw/
│   ├── processed/
│   └── mysql_ready/
├── docs/                     # Documentation
├── scripts/                  # Executable runners
└── tests/                    # Testing suite
```

## Key Features

### Data Cleaning & Standardization
- **Multi-row header handling** for complex Excel files
- **DNI (National ID) standardization** with validation
- **Fuzzy name matching** for farmer identification across datasets when national_id not provided
- **Synthetic ID generation** for unmatched records
- **Encoding issue resolution** (UTF-8 normalization)
- **TOTAL row removal** and data validation

### Database Integration
- **Foreign key relationship management** between farmers, inspections, and transactions
- **Multi-step matching process** using pd_farmer_id, national_id, and fuzzy matching
- **Data integrity validation** before insertion
- **Duplicate detection and resolution**

### Modular Design
- Shared utility classes used across all cleaners
- Separate handling for inspections (complex) vs transactions (simple)
- Centralized configuration management
- Reusable components for scalability

## Current Status

### Completed ✓
- Database schema design and implementation
- Migration of 70,000+ transaction records
- Migration of 4,000+ farmer records
- Core utility modules (`dni_cleaner.py`, `file_handler.py`)

### In Progress 🔄
- Individual cleaner development for all five Producer Organizations
- Refactoring from notebooks to modular production code
- Documentation and testing

### Planned 📋
- Norandino Visits data integration (Kobo API connection)
- Sagri soil analysis predictions API integration

## Data Privacy

This repository contains **code only** - no personal farmer data, credentials, or certificates are included. All sensitive information is excluded via `.gitignore`.