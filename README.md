# Coffee Producer Organizations Data Pipeline

A comprehensive data infrastructure project transforming smallholder coffee farmer data management for five Producer Organizations in Peru, enabling data-driven decision making and sustainable farming practices.

---

## 📋 Project Overview

### The Challenge
Five coffee Producer Organizations (POs) in Peru manage critical data about **900+ smallholder farmers** across **70,000+ transactions** and **4,000+ annual inspections**. This data exists in disparate Excel files with:
- Inconsistent formats across organizations and years
- Manual data entry errors and duplications
- No centralized access for analysis
- Limited ability to track farmer progress over time
- Difficulty generating insights for certification and sustainability initiatives

### The Solution
This project builds a **production-grade data pipeline** that:
1. **Cleans and standardizes** raw data from multiple sources and formats
2. **Integrates** farmer records across years using intelligent matching
3. **Migrates** data to a normalized MySQL database with referential integrity
4. **Connects** to external APIs for real-time field data and soil predictions
5. **Enables** analytics, dashboards, and evidence-based decision making

---

## 🌍 Impact & Scope

### Data Volume
- **70,000+** transaction records (coffee purchases)
- **4,000+** farmer inspection records
- **5+ years** of historical transaction data per most organizations


---

## 📈 Project at a Glance

| Metric | Value |
|--------|-------|
| **Data Records Processed** | 70,000+ transactions, 4,000+ inspections |
| **Historical Data** | 3-5 years per organization |
| **Database Tables** | 15+ normalized tables with foreign keys |
| **Code Quality** | Production-ready Python modules replacing ad-hoc notebooks |
| **Certifications Tracked** | Organic, Fair Trade, Rainforest Alliance, UTZ, EUDR |
| **Geographic Coverage** | 5 regions across Peru |


**Technology Stack**: Python, MySQL, Pandas, API integrations (Kobo, Sagri)  
**Development Stage**: Phase 1 (Core pipeline) 70% complete | Phase 2 (Dashboards, APIs) in planning

---

## 🏗️ Technical Architecture

```
coffee-producers-data-pipeline/
│
├── config/
│   └── paths.py                    # Centralized configuration
│
├── src/
│   ├── stage1_cleaning/            # Raw data → Clean standardized data
│   │   ├── inspections/
│   │   │   ├── bagua_inspections_cleaner.py
│   │   │   ├── huadquina_inspections_cleaner.py
│   │   │   ├── chirinos_inspections_cleaner.py
│   │   │   ├── norandino_inspections_cleaner.py
│   │   │   └── aprocassi_inspections_cleaner.py
│   │   └── transactions/
│   │       ├── bagua_transactions_cleaner.py
│   │       ├── huadquina_transactions_cleaner.py
│   │       ├── chirinos_transactions_cleaner.py
│   │       ├── norandino_transactions_cleaner.py
│   │       └── aprocassi_transactions_cleaner.py
│   │
│   ├── stage2_integration/         # Data integration & foreign keys
│   │   ├── farmer_matching.py      # Intelligent farmer deduplication
│   │   └── relationship_builder.py # Foreign key generation
│   │
│   ├── stage3_migration/           # MySQL database loading
│   │   ├── schema_creator.py
│   │   └── data_migrator.py
│   │
│   ├── kobo_api/                   # Real-time field data collection
│   │   └── norandino_visits.py     # Kobo Toolbox integration
│   │
│   ├── sagri_api/                  # Soil analysis & predictions
│   │   └── soil_predictions.py     # Sagri platform integration
│   │
│   ├── database/                   # Database utilities
│   │   └── connection.py
│   │
│   └── utils/                      # Shared components
│       ├── dni_cleaner.py          # National ID validation
│       ├── file_handler.py         # Excel/CSV processing
│       └── column_cleaner.py       # Standardization
│
├── data/                           # Excluded from git (sensitive)
│   ├── raw/                        # Original Excel/CSV files
│   ├── processed/                  # Cleaned pickle files
│   └── mysql_ready/                # Database-ready exports
│
├── scripts/                        # Executable runners
│   ├── clean_*.py                  # Data cleaning scripts
│   └── compare_*.py                # Validation scripts
│
├── docs/                           # Documentation
│   ├── data_dictionary.md
│   └── database_schema.md
│
└── tests/                          # Testing suite
```

**Note on Architecture**: The kobo_api and sagri_api modules are independent integration layers that connect external data sources directly to the database, operating in parallel to the core cleaning/integration/migration pipeline.

---

## 🔑 Key Technical Features

### Advanced Data Cleaning
- **Multi-format Excel handling**: Complex multi-row headers, merged cells, variable column structures
- **DNI (National ID) validation**: 8-digit standardization with error correction (e.g., O→0 substitution)
- **Intelligent total row detection**: Pattern-based removal of summary rows
- **Encoding normalization**: UTF-8 handling across Spanish special characters
- **Date parsing**: Multiple format support with error recovery
- **Column harmonization**: Aggregating split columns across years (e.g., 6 crop types → `area_otros_cultivos`)

### Farmer Identity Resolution
Multi-step matching algorithm:
1. **Exact DNI match**: Primary key when available
2. **Fuzzy name matching**: Levenshtein distance for name variations
3. **Synthetic ID generation**: `UNKNOWN_BG_001` pattern for unmatched records
4. **Cross-year deduplication**: Same farmer across multiple inspection years gets one ID

### Database Design
- **Normalized schema**: Farmers → Inspections → Transactions with proper foreign keys
- **Referential integrity**: Cascading updates and deletes
- **Data validation**: Pre-insertion checks for orphaned records
- **Audit trails**: Creation timestamps and data source tracking

### API Integrations
- **Kobo Toolbox**: Real-time field visit data collection (Norandino)
- **Sagri Platform**: Soil analysis and yield prediction API

---

## 📊 Current Status

### ✅ Phase 1 Completed (Foundation)
**Database Infrastructure**
- [x] MySQL database schema design with normalized tables
- [x] Referential integrity and foreign key constraints
- [x] Migration of **70,000+ transaction records** to database
- [x] Migration of **4,000+ farmer profiles** with relationship mapping
- [x] Audit trails and data source tracking

**Core Utilities**
- [x] DNI (National ID) cleaner with validation and error correction
- [x] File handler supporting multi-format Excel files (multi-row headers, merged cells)
- [x] Column standardization module for cross-organization consistency
- [x] Farmer matching algorithm (DNI-based, fuzzy name matching, synthetic ID generation)

### 🔄 Phase 1 In Progress (Data Cleaning Pipeline)
**Completed Producer Organizations:**
- [x] **Bagua Grande**: 
  - Inspections cleaner (422 records, 40 columns) - **Verified ✓**
  - Transactions cleaner (4,373 records across 2022-2025) - **Verified ✓**
  - *Note: 2025 data has known quality issues awaiting PO correction*
  
- [x] **Huadquiña**: 
  - Inspections cleaner (333 records, 40 columns) - **Verified ✓**
  - Transactions cleaner (23,597 records) - **Verified ✓**
  
- [x] **Chirinos**: 
  - Transactions cleaner (39,331 records, 2020-2024) - **Verified ✓**
  - Inspections cleaner (multi-year aggregation) - **In development**

**Pending Producer Organizations:**
- [ ] **Norandino**: Inspections + Transactions cleaners
- [ ] **Aprocassi**: Inspections + Transactions cleaners

**Pipeline Progress**: ~55% complete (3 of 5 POs with verified cleaners)

### 🔄 Current Work (Week of March 2026)
- Completing Chirinos inspections cleaner with column harmonization across years
- Implementing farmer ID generation for multi-year Chirinos data
- Code refactoring from Jupyter notebooks to production Python modules
- Verification scripts comparing cleaner outputs against original notebooks

### 📋 Planned (Phase 2)
- [ ] **Dashboard connectivity**: Connect database to visualization platforms (Power BI / Tableau / custom web dashboards)
- [ ] **Phase 2 database tables** - Migration and integration of:
  - **ROTA**: Crop rotation tracking and planning data
  - **EUDR Alerts**: EU Deforestation Regulation compliance monitoring
  - **Polygons**: Polygons data of each plot from each farmer
  - **Training Data**: Training topics and records
- [ ] **API deployment**: 
  - Kobo API integration for real-time field visit data (Norandino)
  - Sagri API integration for soil analysis predictions
- [ ] **Automated data pipelines** for annual updates
- [ ] **Data quality monitoring** and alerting system
- [ ] **Advanced analytics**:
  - Machine learning models for yield prediction
  - Risk assessment algorithms
  - Climate adaptation indicators

---

## 🎓 Collaboration Opportunities

We are actively seeking partnerships with universities and research institutions specialized in data science, agricultural technology, and development economics.

### Priority Opportunities

**1. Sagri Soil Analysis Model Validation** ⭐
- **Challenge**: Validate predictive accuracy of Sagri platform's soil analysis and yield forecasting models
- **Scope**: Compare Sagri predictions against actual harvest data from our database
- **Impact**: Ensure evidence-based soil management recommendations for smallholder farmers
- **Skills needed**: Machine learning validation, agricultural science, statistical analysis

**2. Code Review & Refactoring**
- **Challenge**: Optimize data cleaning algorithms for performance and maintainability
- **Scope**: Review ~5,000 lines of Python code across cleaning, integration, and migration modules
- **Impact**: Improve pipeline efficiency and reduce processing time
- **Skills needed**: Python, pandas, software engineering best practices


### Research Collaboration Areas

**Data Science / Computer Science**
- Machine learning model development (yield prediction, risk scoring, anomaly detection)
- Research of historical and predictive climate datasets for climate dashboards 
- Automated data quality checks and validation frameworks
- Natural language processing for farmer feedback analysis from agricultural advice
- Time series analysis of productivity trends

**Agricultural Science / Economics**
- Climate adaptation strategies and their correlation with yield outcomes
- Soil health indicators and their relationship to coffee quality
- Supply chain optimization and market access analysis

**Social Science / Development Studies**
- Gender equity analysis in smallholder farming cooperatives
- Economic empowerment indicators and household resilience
- Community development impact of PO membership

### What We Provide

✅ **Access to real-world agricultural data** (anonymized as needed)  
✅ **Direct connection with Producer Organizations** for field validation  
✅ **Existing database infrastructure** ready for analysis  
✅ **Technical documentation** and data dictionaries  


---

## 🛠️ Technology Stack

**Languages**: Python 3.11+  
**Database**: MySQL 8.0  
**Key Libraries**: 
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `openpyxl` - Excel file handling
- `mysql-connector-python` - Database connectivity
- `fuzzywuzzy` - Fuzzy string matching
- `requests` - API integrations

**Development**: Git, VS Code, Jupyter Notebooks (migration to .py modules in progress)

---

## 🔒 Data Privacy & Security

- **No sensitive data in repository**: All farmer data, credentials, and certificates excluded via `.gitignore`
- **Anonymization**: Personal identifiers can be masked for research datasets
- **Access control**: Database credentials managed via environment variables



---

## 📞 Contact

**Project Developer**: Daniela  
**Organization**: Producers Direct


**For Collaboration Inquiries**:  
📧 Email: [sam@producersdirect.org]
🌐 Website: [(https://producersdirect.org/)]  
💻 GitHub: [https://github.com/producersdigital/coffee-producers-data-pipeline]

**For Academic Partnerships**: Please include "University Collaboration" in subject line  
**For Donor Inquiries**: Please include "Funding Opportunity" in subject line

---

## 📜 License

**Code**: MIT License (open source - see LICENSE file)  
**Data**: Not included in repository due to privacy protections

---
