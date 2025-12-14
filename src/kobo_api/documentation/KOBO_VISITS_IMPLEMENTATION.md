# Kobo API Integration Documentation

## Purpose & Context

This integration connects Kobo's API with the `shared_data_layer` database to automatically import technical assistance visit records. The system fetches form submissions from the "Visitas Asistencia Tecnica" form, cleans the data following Daniela's specifications, and stores it in the database for tracking farmer visits and agronomist activities in Peru.

**Key Points:**

- The import script can be run at any time to fetch new visit records
- Automatically downloads the latest Kobo export and processes all submissions
- Prevents duplicate imports using unique visit identifiers (`kobo_uuid`)
- Validates data integrity by matching farmers (DNI) and extensionists before inserting
- Logs unmatched records to CSV files for manual review and resolution
- Summary shows both total visit records and unique farmer/extensionist counts for clarity
- Supports test mode and dry-run mode for safe testing before production imports
- No manual intervention needed for updates - just execute the script periodically

**Initial Data Population**
- Initial import completed: 1,324 visits (20% of total) successfully imported into the database
- Identified missing data: 632 farmers and 30 extensionists need to be added to complete the full import
- Created mapping CSVs and import scripts to help the team add the missing data

---

## Script Implementation

### Script Location
- Main script: `src/kobo_api/scripts/import_kobo_visits.py`

### How The Script Works

The process follows these steps:

1. **Download**: Fetch latest CSV from Kobo API
2. **Clean**: Apply data transformations as explained in the section "Data clean up"
3. **Match**:
   - DNI → `farmer_id` from `farmers.national_id`
   - Extensionist code → `extensionist_id`
   - Product name → `product_type_id`
4. **Validate**: Check if `kobo_uuid` already exists (skip duplicates)
5. **Insert**: Load into `technical_assistance_visits` table
6. **Log**: Record any unmatched farmers for manual review

### Execution Modes

The script supports three execution modes to provide flexibility during testing and production use:

#### 1. **Full Import Mode** (Default)
Processes all records in the CSV and inserts them into the database.

```bash
source venv/bin/activate
python src/kobo_api/scripts/import_kobo_visits.py
```

**When to use:** Regular production imports to update the database with all new visits.

**What it does:**
- Processes all records from the latest Kobo export
- Inserts valid records into the database
- Logs unmatched farmers/extensionists
- Skips duplicates (checks `kobo_uuid`)

---

#### 2. **Test Mode** (`--test N`)
Processes only the first N rows for quick testing with a subset of data.

```bash
python src/kobo_api/scripts/import_kobo_visits.py --test 100
```

**When to use:**
- Testing the script with real data before full import
- Validating data cleanup logic
- Quick checks after code changes

**What it does:**
- Processes only the first N rows from the CSV
- Inserts those records into the database (unless combined with `--dry-run`)
- Useful for catching issues without processing thousands of records

---

#### 3. **Dry-Run Mode** (`--dry-run`)
Simulates the entire import process without actually inserting data into the database.

```bash
python src/kobo_api/scripts/import_kobo_visits.py --dry-run
```

**When to use:**
- Validating the import before committing to database changes
- Checking how many records would be imported/skipped
- Reviewing unmatched farmers/extensionists before actual import
- Testing in production environment without side effects

**What it does:**
- Reads and processes all records
- Generates error logs (unmatched farmers/extensionists)
- Shows statistics of what would be imported
- **Does NOT insert anything into the database**

---

#### Combining Modes

You can combine `--test` and `--dry-run` for maximum safety during testing:

```bash
# Process first 10 rows without inserting to database
python src/kobo_api/scripts/import_kobo_visits.py --dry-run --test 10
```

**Recommended workflow:**
1. Start with `--dry-run --test 10` to validate logic with minimal data
2. Run `--dry-run` (full) to see complete import statistics
3. Review error logs and add missing farmers/extensionists
4. Run full import (no flags) when confident



### Data clean up
The script performs the following data clean ups automatically.

**Core Cleanup (As Specified by Daniela):**

1. **tiempo_total → Number**: Convert to numeric type using `pd.to_numeric()` with error handling
2. **DNI → String**: Force DNI field to string type (preserves leading zeros) and strip whitespace
3. **Año_visita**: Extract year from visit date and convert to string format
4. **mes_visita**: Extract month from visit date and convert to zero-padded string (e.g., "01", "02")

**Additional Automated Cleanups:**

5. **Date parsing**: Convert 'Fecha' field to proper datetime format
6. **All time fields → Number**: Convert all 6 time breakdown fields to numeric (advisory, traceability, crop management, harvest followup, travel, office work)
7. **Boolean conversions**: Convert all 24 checkbox fields (symptoms and diseases) from Kobo format to proper boolean values
8. **Whitespace handling**: Strip leading/trailing whitespace from DNI and text fields
9. **Null handling**: Replace NaN/null values with appropriate defaults (empty strings for text, 0 or NULL for numbers)
10. **Error tolerance**: Use `errors='coerce'` for all numeric conversions to prevent script failures from malformed data

### Handling missing farmers or extensionists

For data integrity, the database uses foreign key constraints that require every visit to link to existing farmers and extensionists. When a visit references a DNI or extensionist code that doesn't exist in the database, the script:

1. **Skips that specific visit** (doesn't insert it)
2. **Continues processing all other valid records**
3. **Logs the unmatched records** to CSV files for review

**Log Files Location**

Each import run creates a timestamped folder with separate error logs:

```
src/kobo_api/logs/import_YYYYMMDD_HHMMSS/
├── unmatched_farmers.csv          # Visits with unknown DNIs
├── unmatched_extensionists.csv    # Visits with unknown extensionist codes
└── summary.txt                     # Import statistics
```

**What Gets Logged**

**unmatched_farmers.csv** contains:
- DNI that wasn't found
- Producer name from Kobo
- Visit date
- Kobo UUID
- Error reason

**unmatched_extensionists.csv** contains:
- Extensionist code that wasn't found
- DNI of the farmer
- Producer name
- Visit date
- Kobo UUID
- Error reason

**Resolution Workflow**

1. **Review the error logs** after each import
2. **Verify the data**: Check if DNIs/codes have typos or if people are truly missing from the database
3. **Add missing records**:
   - For farmers: Insert into `farmers` table with all required information (name, DNI, location, organization, etc.)
   - For extensionists: Insert into `extensionists` table with code and name
4. **Re-run the import**: The script will automatically process previously failed records on the next run (it checks by `kobo_uuid` to avoid duplicates)

**Important**: When adding farmers, ensure all their information is complete to maintain data integrity across the entire database. 


## Data Structure

### Kobo form's columns

The Kobo form, when downloaded as a CSV, contains 118 form fields. After conversations with the PD team, the decision of keeping only 44 columns for the database was made. Those 44 columns can be found as "Annex II" in this document. 

### Database Design

Two new tables were created in the MySQL database to store this Kobo data. The design links technical assistance visit data to our existing farmer records while maintaining data integrity.

#### Table 1: `extensionists`

Stores information about extension workers (técnicos) who conduct the technical assistance visits. As requested by Daniela, this table is necesary to track who made the respective visits.

**Why a separate table?**
- Extension workers visit many farmers repeatedly
- Avoids duplicating extensionist names across thousands of visit records
- Enables linking extensionists to their organizations
- Makes it easy to track performance metrics per extensionist

**Columns:**
- `extensionist_id`: Unique internal identifier
- `extensionist_code`: Unique identifier (e.g., "n02873158", "j47338464")
- `extensionist_name`: Full name of the extension worker
- `org_id`: Links to the producer organization they work for (future: multiple organizations)
- `is_active`: Allows deactivating without deleting historical data

#### Table 2: `technical_assistance_visits`

Stores all technical assistance visit records from Kobo, with all 44 required fields.

**Why this structure?**
- Each visit is linked to both a farmer and an extensionist via foreign keys
- Foreign key constraints ensure data integrity - the database will reject visits if the farmer or extensionist doesn't exist
- All 44 Kobo fields are preserved for complete historical records
- Disease/symptom data stored as boolean flags for easy querying

**All columns in the table:**

*Identifiers & Links:*
- `visit_id` - Primary key (auto-increment)
- `kobo_uuid` - Unique Kobo record identifier from `_uuid`
- `kobo_submission_id` - Kobo submission ID from `_id`
- `farmer_id` - Foreign key to farmers table
- `extensionist_id` - Foreign key to extensionists table

*Visit Information:*
- `visit_date` - Date of visit from "Fecha"
- `visit_year` - Extracted year (CHAR(4))
- `visit_month` - Extracted month (CHAR(2))
- `producer_name_from_kobo` - Producer name from Kobo (for validation)
- `product_name_raw` - Product name as string ("Café", "Cacao", "Panela")

*Time Breakdown (decimal hours):*
- `advisory_sig_time` - 1.1 SIG advisory time
- `advisory_traceability_time` - 1.2 Traceability advisory time
- `technical_crop_management_time` - 1.3 Crop management time
- `harvest_followup_time` - 1.4 Harvest follow-up time
- `travel_time` - 1.5 Travel time
- `office_work_time` - 1.6 Office work time
- `total_time` - Total time

*Activity Details:*
- `activity_description` - Description of activity
- `recommendations` - Recommendations given
- `commitments_next_visit` - Commitments for next visit
- `current_certification_status` - Current certification status

*Disease Information:*
- `has_coffee_eye_spot` - Coffee eye spot presence (yes/no)

*Symptoms (8 boolean fields):*
- `symptom_brown_spots_leaves`
- `symptom_dark_border`
- `symptom_black_center_eye`
- `symptom_falling_leaves`
- `symptom_branch_spots`
- `symptom_drying_branches`
- `symptom_white_fuzz_branches`
- `symptom_fruit_spots`

*Other Diseases (16 boolean fields):*
- `disease_brown_spots_leaves`
- `disease_dark_border`
- `disease_black_center`
- `disease_falling_leaves`
- `disease_branch_spots`
- `disease_drying_branches`
- `disease_white_fuzz`
- `disease_fruit_spots`
- `disease_roya`
- `disease_anthracnose`
- `disease_broca`
- `disease_spider_mite`
- `disease_cercospora`
- `disease_leaf_miners`
- `disease_black_foot`
- `disease_phoma`

*Metadata:*
- `kobo_submission_time` - Kobo submission timestamp
- `data_source` - Source of data (default: 'kobo_api'). Can be used in the future of other data sources.
- `created_at` - Record creation timestamp
- `updated_at` - Record update timestamp

**How it links to farmers:**
- Kobo form captures the farmer's DNI (national ID) in the "Insertar No de DNI productor" field
- Our import script matches this DNI to `farmers.national_id`
- The `farmer_id` foreign key creates the relationship
- `producer_name_from_kobo` field stores the name from Kobo for validation purposes

**Key design decisions:**
- **Disease tracking**: 24 boolean fields for symptoms and diseases enable granular analysis
- **Duplicate prevention**: `kobo_uuid` unique constraint prevents re-importing the same visit
- **Year/month fields**: Extracted from visit date as strings as requested by Daniela

**Indexes for performance:**
- Visit date (for time-range queries)
- Farmer + date (farmer visit history)
- Extensionist + date (extensionist workload analysis)
- Year + month (monthly/annual reporting)

### Data Integrity Features

The database architecture provides automatic validation:

1. **Foreign key to farmers**: Rejects visits if DNI doesn't match an existing farmer
2. **Foreign key to extensionists**: Rejects visits if extensionist code is not in the database
3. **Foreign key to products**: Rejects visits if product type is invalid
4. **Unique constraint on kobo_uuid**: Prevents duplicate imports of the same visit

This means failed validations are caught at the database level, not just in application code.


## Initial Data Insertion

### Current Status
An initial import has been completed with the available data:

**Visits Imported:** 1,324 out of 6,633 total records (20%)
- Date range: January 2023 - November 2025
- Covering 466 unique farmers
- Recorded by 6 extensionists
- Spanning 3 years of data

**Remaining:** 5,309 visit records (80%) could not be imported due to missing farmers (632 unique) and extensionists (30 unique) in the database.

To complete the full import, the missing farmers and extensionists must be added first. Tools and documentation are provided below to help the team complete this setup.

### Extensionists
In the current Kobo forms there are 37 different extensionists. However, for only 7 of them we had complete data. Those 7 are already in the `extensionists` table. The remaining 30 are missing.

**The Challenge:**
The Kobo CSV contains extensionist codes (e.g., "n02873158") in the `Nombre_Tecnico` field, but not their names. For data integrity from the start, the database requires both code and name.

**Solution:**
I mapped out all 37 extensionists (both complete and incomplete). This information is found in a CSV. Additionally, a script was created to support the insertion of new extensionists once their data is completed.

- CSV: `src/kobo_api/data_helpers/extensionists_mapping.csv`
- Script: `src/kobo_api/scripts/populate_extensionists.py`

**Workflow to fix this**
1. Fill in the missing names in extensionists_mapping.csv
2. Run the import script: `python src/kobo_api/scripts/populate_extensionists.py`

The script only inserts extensionists marked as "MISSING" with names provided, skipping those already in the database.

### Farmers
The Kobo CSV contains 2,018 unique farmer DNIs. Of these, 1,387 (68.7%) already exist in the database. The remaining 631 (31.3%) are missing and need to be added.

**The Challenge:**
The Kobo visits reference farmer DNIs that don't exist in the `farmers` table. The database enforces foreign key constraints, so visits cannot be imported until all referenced farmers are in the database.

**Solution:**
I extracted all missing farmer DNIs with their available information from Kobo (name, organization). This data is in a CSV file. A script was created to insert these farmers once the team completes the required fields.

- CSV: `src/kobo_api/data_helpers/farmers_mapping.csv`
- Script: `src/kobo_api/scripts/populate_farmers.py`

**What's pre-filled in the CSV:**
- `national_id` (DNI) - from Kobo
- `farmer_name_from_kobo` - full name from Kobo
- `org_name_from_kobo` - organization name from Kobo (needs to be matched to `org_id`)

**What the team needs to complete:**
- `org_id` - **REQUIRED** - Match the organization name to the ID in your organizations table
- `telephone` - Optional
- `gender_id` - Optional (1 for male, 2 for female)
- `birth_date` - Optional (format: YYYY-MM-DD)

**Workflow to fix this**
1. Open farmers_mapping.csv
2. Match organization names to get the `org_id` from your organizations table
3. Fill in optional fields if available
4. Run the import script: `python src/kobo_api/scripts/populate_farmers.py`

**Important:** The script will only insert farmers with a valid `org_id`. Rows without `org_id` will be skipped.

---

# Annex I: Notes about the implementation

- **Data Refresh**: Kobo caches exports for 5 minutes, so re-running the script within 5 minutes will not show new submissions
- **Optional Fields**: Disease/symptom fields and time fields (1.5, 1.6) are conditional - they only appear when filled in
- **Delimiter**: CSV uses semicolon (;) instead of comma (,)
- **File Format**: UTF-8 encoding with Spanish characters supported
- **Server**: EU Kobo server (`https://eu.kobotoolbox.org`)
- **Form**: Visitas Asistencia Tecnica
- **Form UID**: `aH5cqApoTcJcK3MLrxKxn2`
- **Authentication**: API Token (stored in `.env` file)
- **Export Used**: "Asistencia Tecnica" (named export configured in Kobo UI)
- **API Documentation**: https://support.kobotoolbox.org/api.html

# Annex II: Fields Requested to keep by Daniela (44 fields)

1. **Nombre_Tecnico** - Extension worker code
2. **ID registro** - Record UUID
3. **Fecha** - Visit date
4. **Insertar No de DNI productor** - Producer ID number
5. **nombre_completo** - Producer full name
6. **estatus_cert_actual** - Current certification status
7. **1.1 Asesoria en la gestión documentaria del SIC y fortalecimiento organizativo** - SIG advisory time
8. **1.2 Asesoria en acopio y trazabilidad del producto** - Traceability advisory time
9. **1.3 Asistencia técnica a productores en el manejo del cultivo** - Crop management time
10. **1.4 Seguimiento a la cosecha y post cosecha del producto** - Harvest follow-up time
11. **1.5 Tiempo de traslado** - Travel time
12. **1.6 Trabajo de gabinete** - Office work time
13. **tiempo_total** - Total time
14. **Producto** - Product (café, panela, cacao, other)
15. **Descripción de la actividad** - Activity description
16. **¿La parcela está con ojo de pollo?** - Coffee eye spot disease presence
17. **Qué síntomas presenta** - Symptoms present (parent field)
18. **Qué síntomas presenta/Manchas redondas de color marrón claro o beige en las hojas**
19. **Qué síntomas presenta/Las manchas tienen un borde más oscuro alrededor**
20. **Qué síntomas presenta/En el centro de la mancha hay un punto negro, como un ojo**
21. **Qué síntomas presenta/Las hojas están cayendo**
22. **Qué síntomas presenta/Manchas en las ramas**
23. **Qué síntomas presenta/Ramas secando**
24. **Qué síntomas presenta/Pelusa o capa blanca en las ramas**
25. **Qué síntomas presenta/Frutos con manchas similares a las de las hojas**
26. **¿Qué otras enfermedades están afectando?** - Other diseases (parent field)
27. **¿Qué otras enfermedades están afectando?/Manchas redondas de color marrón claro o beige en las hojas**
28. **¿Qué otras enfermedades están afectando?/Las manchas tienen un borde más oscuro alrededor**
29. **¿Qué otras enfermedades están afectando?/En el centro de la mancha hay un punto negro, como un ojo**
30. **¿Qué otras enfermedades están afectando?/Las hojas están cayendo**
31. **¿Qué otras enfermedades están afectando?/Manchas en las ramas**
32. **¿Qué otras enfermedades están afectando?/Ramas secando**
33. **¿Qué otras enfermedades están afectando?/Pelusa o capa blanca en las ramas**
34. **¿Qué otras enfermedades están afectando?/Frutos con manchas similares a las de las hojas**
35. **¿Qué otras enfermedades están afectando?/Roya**
36. **¿Qué otras enfermedades están afectando?/Antracnosis**
37. **¿Qué otras enfermedades están afectando?/Broca**
38. **¿Qué otras enfermedades están afectando?/Arañero**
39. **¿Qué otras enfermedades están afectando?/Cercospora**
40. **¿Qué otras enfermedades están afectando?/Minadores**
41. **¿Qué otras enfermedades están afectando?/Pie negro**
42. **¿Qué otras enfermedades están afectando?/Phoma**
43. **Recomendaciones** - Recommendations
44. **Compromisos para la proxima visita** - Commitments for next visit


# Annex III: Test downloading data
A script was created to test the download of the data from Kobo's API. To run it, simply use the commands below.

```bash
# Activate virtual environment
source venv/bin/activate

# Run the download script
python src/kobo_api/scripts/test_download_csv_export.py
```

The script will:
1. Connect to Kobo API
2. Find the "Asistencia Tecnica" export
3. Download the full CSV
4. Save to `data/kobo_exports/`

## Data Storage
- **Directory**: `data/kobo_exports/`
- **File naming**: `kobo_export_YYYYMMDD_HHMMSS.csv`
- **Format**: CSV with semicolon (;) delimiter
- **Records**: 6,633 submissions (as of Dec 2025)

## Configuration
- API credentials: `.env` file (KOBO_API_TOKEN)
- Server URL: `.env` file (KOBO_SERVER_URL)