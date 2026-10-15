# OPERATIONS

How to run, refresh and troubleshoot the Shared Data Layer (SDL) pipeline.

Read this when something needs loading, something broke, or someone new is
taking over. It assumes you can open a terminal and MySQL Workbench, and nothing
else about the project.

`README.md` explains **what** this project is. This explains **how to operate
it**. Module-level detail lives in each module's own documentation
(`src/eudr/eudr_README.md`, `src/kobo_api/documentation/`,
`src/sagri_api/documentation/`).

Every command and flag below was verified against the code in this repository.

---

## Table of contents

1. [Before anything else](#1-before-anything-else)
2. [The database](#2-the-database)
3. [Where the source files go](#3-where-the-source-files-go)
4. [The core pipeline — Stages 1 to 3](#4-the-core-pipeline--stages-1-to-3)
5. [The integration modules](#5-the-integration-modules)
6. [Verifying a load](#6-verifying-a-load)
7. [Troubleshooting](#7-troubleshooting)
8. [Conventions that are not obvious from the code](#8-conventions-that-are-not-obvious-from-the-code)
9. [Routine cadence](#9-routine-cadence)
10. [Known open items](#10-known-open-items)
11. [Contact](#11-contact)

---

## 1. Before anything else

### 1.1 What you need

| Thing | Where it comes from |
|---|---|
| Python 3.11+ with the project environment | `conda activate coffee-data-system`, then `pip install -r requirements.txt` |
| `.env` at the repo root | Copy `.env.example` and fill in from the password manager |
| `config/certificates/ca-certificate.crt` | Download from the DigitalOcean database dashboard |
| MySQL Workbench (or any client) | Verification queries and schema changes |
| Access to the source files | See [section 3](#3-where-the-source-files-go) |

Neither `.env` nor the certificate is in git — `.gitignore` excludes both
deliberately, along with every `.csv` and `.xlsx`. **A fresh clone cannot
connect to the database until you add them.** That is intended, not a bug.

`.env` needs:

```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
KOBO_SERVER_URL, KOBO_API_TOKEN
```

### 1.2 Confirm the connection first

```bash
python src/database/connection.py
```

Expected:

```
Successfully connected to MySQL database
MySQL Server version: 8.0.45
Connection closed
```

If this fails, nothing downstream will work. Check in this order:

1. The certificate exists at exactly `config/certificates/ca-certificate.crt`.
2. `.env` has all five `DB_*` values.
3. **Your current IP is in the DigitalOcean firewall's trusted sources.** This is
   the usual cause when it worked yesterday and doesn't today — a home internet
   connection gets a new IP address periodically.

### 1.3 Run everything from the repo root

```bash
cd /path/to/coffee-producers-data-pipeline
python src/eudr/scripts/eudr_loader.py --dry-run
```

Every loader resolves its own paths from the location of its own file, so the
folder you are standing in does not change where it looks for data. Running from
the repo root is still the habit to keep — it is what the examples below assume,
and it makes a mistyped path obvious instead of silently relative.

---

## 2. The database

- **Engine**: MySQL 8.0.45, DigitalOcean Managed Databases, SSL required
- **Schema**: `shared_data_layer`
- **Tables**: 26, plus 5 lookup tables and reporting views
- **Entry point**: `src/database/connection.py` → `create_connection()`

Every script in the project uses that one function. It loads `.env`, attaches
the CA certificate and sets `autocommit=True`. If credentials change, that is
the only place that needs to know.

### 2.1 End of life — action required

**MySQL 8.0 reaches end of life on 30 October 2026.** DigitalOcean will require
an upgrade to 8.4. Take a full backup first and schedule it outside working
hours: Power BI reports and every loader point at this one instance.

Owner: Sam. 

### 2.2 Taking a backup

DigitalOcean keeps automatic daily backups, but take your own before a schema
change, a `--fresh` migration, or the version upgrade:

```bash
mysqldump --host=<DB_HOST> --port=<DB_PORT> --user=<DB_USER> -p \
  --ssl-ca=config/certificates/ca-certificate.crt \
  --single-transaction --routines --triggers \
  shared_data_layer > backup_$(date +%Y%m%d).sql
```

Store it outside the repository. The dump contains every farmer's name and
national ID.

---

## 3. Where the source files go

**Each module reads from a different folder.** There is no single `data/raw/`
that everything uses, and putting a file in the wrong place produces a
"file not found" that looks like a broken script.

| Module | Put the file here |
|---|---|
| Stage 1 (PO Excel files) | `data/raw/` |
| SAGRI (`sagri_codes.xlsx`) | `data/raw/sagri/` |
| EUDR (all three loaders) | `src/eudr/data/` |
| Estimations | `src/estimations/data/raw/` |
| Kobo visits and trainings | Downloaded automatically from the API — nothing to place |
| CEA | Fetched from the API — nothing to place |

Intermediate and output files:

| Stage | Writes to |
|---|---|
| Stage 1 | `data/processed/` (cleaned `.pkl` files) |
| Stage 2 | `data/mysql_ready/{master,operational,lookup}/` |
| Stage 3 | MySQL — no files |

All of these are excluded from git. They contain farmer personal data.

---

## 4. The core pipeline — Stages 1 to 3

This runs when a PO sends new or corrected historical files. It is not a routine
refresh.

```
Stage 1   raw Excel per PO      →  cleaned PKL files
Stage 2   cleaned PKL files     →  integrated, farmer-linked CSVs
Stage 3   integrated CSVs       →  MySQL SDL
```

### 4.1 Stage 1 — cleaning

One runner per PO per dataset, in `scripts/`:

```bash
python scripts/clean_norandino_inspections.py     # multi-year 2023–2025
python scripts/clean_norandino_transactions.py
python scripts/clean_chirinos_inspections.py      # multi-year 2020–2024
python scripts/clean_chirinos_transactions.py
python scripts/clean_aprocassi_inspections.py
python scripts/clean_aprocassi_transactions.py
python scripts/clean_huadquina_inspections.py
python scripts/clean_huadquina_transactions.py
python scripts/clean_bagua_inspections.py
python scripts/clean_bagua_transactions.py
```

`scripts/clean_bagua_complete.py` runs both Bagua halves in one go.

Run only the cleaners whose source file actually changed.

### 4.2 Stage 2 — integration

```bash
python scripts/run_stage2.py
```

No flags. Links every record to a farmer identity by national ID, then exact
name, then fuzzy name at a 90% threshold.

**Check the match rate it prints.** The established baseline is 96%+. A sudden
drop means a source file changed shape — investigate before loading, not after.

### 4.3 Stage 3 — migration to the SDL

```bash
python scripts/run_stage3.py            # clears main tables, keeps lookups
python scripts/run_stage3.py --resume   # continue after a failure, clears nothing
python scripts/run_stage3.py --fresh    # clears lookup tables too
```

It checks that all 13 Stage 2 CSVs exist before touching the database, so a
half-finished Stage 2 cannot produce a half-loaded SDL.

**`--resume` is the one to use after a dropped connection.** It skips the
clearing step and resumes transactions by index. Re-running the default mode
after a partial failure wipes what loaded successfully and starts again from
zero.

> ⚠️ The default mode **clears the main tables**. Tables loaded by the
> integration modules below (EUDR, trainings, estimations, SAGRI, CEA) are not
> part of Stage 3 and are not cleared — but confirm that before running it on a
> working day.

### 4.4 Post-migration

```bash
python scripts/update_ex_socios.py              # preview only
python scripts/update_ex_socios.py --apply      # mark departed members
```

Run this each time a new membership file arrives. It marks departed members as
`Ex-socio` rather than deleting them, so their history survives.

---

## 5. The integration modules

Each is independent. Running one never requires running another.

### 5.1 Kobo — technical assistance visits

```bash
python src/kobo_api/scripts/import_kobo_visits.py --dry-run
python src/kobo_api/scripts/import_kobo_visits.py
python src/kobo_api/scripts/import_kobo_visits.py --test 50   # first 50 rows only
```

Tables: `technical_assistance_visits`, `extensionists`.

Pulls a live snapshot from Kobo on every run. To register new field technicians
first:

```bash
python src/kobo_api/scripts/populate_extensionists.py
```

Detail: `src/kobo_api/documentation/KOBO_VISITS_IMPLEMENTATION.md`.

### 5.2 Kobo — trainings

```bash
python src/kobo_api/scripts/import_kobo_trainings.py --dry-run
python src/kobo_api/scripts/import_kobo_trainings.py
python src/kobo_api/scripts/import_kobo_trainings.py --test 50
python src/kobo_api/scripts/import_kobo_trainings.py --file path/to/export.xlsx
```

Tables: `trainings`, `training_participants`.

**A prerequisite that is easy to forget**: a *named* XLSX export called
`Trainings` must exist in the Kobo UI — DATA → Downloads → XLSX, tick
"Include labels", keep repeat groups as separate sheets, then "Save selection
as" → `Trainings`. The importer finds it **by that name**. If someone renames or
deletes it, the download fails with no obvious explanation.

Use `--file` to load a previously downloaded export when Kobo is unreachable.

Detail: `src/kobo_api/documentation/KOBO_TRAININGS_IMPLEMENTATION.md`.

### 5.3 Estimations — Norandino harvest forecasts

```bash
python src/estimations/scripts/clean_estimations.py                   # all years
python src/estimations/scripts/clean_estimations.py --year 2026       # one year
python src/estimations/scripts/load_estimations.py --source-org-code NO --dry-run
python src/estimations/scripts/load_estimations.py --source-org-code NO
```

Tables: `collection_estimations`, `collection_estimation_crops`.

`--source-org-code` is **required** — the workbook never names the cooperative,
so the organisation is supplied on the command line and resolved against
`producer_organizations`. All current files are Norandino (`NO`).

`--year` can be repeated to process several specific years.

**The loader validates loaded coffee kg against each file's own `TOTAL GENERAL`
row.** If that check fails, a column has shifted in the workbook. Fix the
mapping — do not override the check.

### 5.4 EUDR

Three loaders, three data sources, no dependencies between them.

```bash
python src/eudr/scripts/eudr_loader.py --dry-run
python src/eudr/scripts/eudr_loader.py

python src/eudr/scripts/osapiens_loader.py --dry-run
python src/eudr/scripts/osapiens_loader.py

python src/eudr/scripts/contracts_loader.py --dry-run
python src/eudr/scripts/contracts_loader.py
```

| Table | Source |
|---|---|
| `eudr_satelligence_alerts` | Satelligence farm-level alert export |
| `eudr_po_compliance` | Satelligence PO compliance sheet |
| `eudr_osapiens_assessments` | Osapiens export, assessment grain |
| `eudr_osapiens_plot_findings` | Osapiens export, plot grain |
| `eudr_contracts` | UK coffee buyer contracts sheet |

Export each sheet tab to `src/eudr/data/` under the exact filename the loader
expects. `eudr_loader.py --dry-run` also writes `*_CLEAN_PREVIEW.csv` files so
you can inspect what would be loaded before anything is written.

Detail, including the Osapiens two-table split and the
`purchase_ref_norm` ↔ `doc_id_normalized` contract link: `src/eudr/eudr_README.md`.

### 5.5 SAGRI

Two scripts, two different jobs.

```bash
# Plot registry from the workbook
python src/sagri_api/scripts/populate_sagri_plots.py           # preview, writes nothing
python src/sagri_api/scripts/populate_sagri_plots.py --apply   # write

# Soil nutrient data from the SAGRI API
python src/sagri_api/scripts/sync_sagri_to_database.py                     # all plots
python src/sagri_api/scripts/sync_sagri_to_database.py --test NORCAJ2338   # single plot
python src/sagri_api/scripts/sync_sagri_to_database.py --month Oct-2025    # another month
```

Tables: `sagri_plots`, `sagri_soil_data`.

`populate_sagri_plots.py` reads `data/raw/sagri/sagri_codes.xlsx`. **Always run
the preview first** — it reports the farmer match rate and the insert/update
split before anything is written. The expected match rate is **100%**; anything
lower means the workbook and `farmers` have diverged.

Detail: `src/sagri_api/documentation/SAGRI_API_INTEGRATION.md`.

### 5.6 CEA (CrossEurAsia)

```bash
python src/cea_api/scripts/populate_cea_plots.py            # preview
python src/cea_api/scripts/populate_cea_plots.py --apply    # write

streamlit run src/cea_api/scripts/norandino_mapas.py        # the map viewer
```

Updates `farmers.cea_plot_code`. CEA presigned URLs expire after one hour, so
maps are fetched fresh on demand and never stored.

---

## 6. Verifying a load

Run this after any load.

```sql
SELECT table_name, table_rows
FROM information_schema.tables
WHERE table_schema = 'shared_data_layer'
ORDER BY table_rows DESC;
```

`table_rows` is an InnoDB estimate. For an exact figure, count the table
directly.

### 6.1 The check that matters more than the row count

A table can hold the right number of rows with every meaningful column NULL.
That is exactly how the SAGRI bug stayed hidden for months
([section 7.1](#71-a-script-succeeds-but-the-table-stays-empty)). So check
*populated columns*, not just totals:

```sql
SELECT COUNT(*)             AS rows_total,
       COUNT(farmer_id)     AS linked,
       COUNT(national_id)   AS has_dni,
       COUNT(selected_crop) AS has_crop
FROM sagri_plots;
```

`COUNT(column)` ignores NULLs. Any column returning far less than `rows_total`
is the one to investigate. Apply the same pattern to whichever table you just
loaded, naming the columns that are supposed to be populated.

### 6.2 Current baseline — October 2026

| Table | Rows |
|---|---|
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
| `sagri_plots` | 2,694 |
| `trainings` | 2,520 |
| `eudr_osapiens_plot_findings` | 1,201 |
| `sagri_soil_data` | 807 |
| `eudr_po_compliance` | 72 |
| `extensionists` | 54 |
| `eudr_contracts` | 46 |
| `producer_organizations` | 24 |
| `eudr_osapiens_assessments` | 14 |

Plus five lookup tables: countries, currencies, genders, product types, units.

**A number that has gone down since the last refresh is a red flag.** Loaders
are idempotent by design; they should never lose rows.

---

## 7. Troubleshooting

Six failures have actually happened on this project. Each is written up
symptom-first, because in every case the symptom pointed somewhere other than
the cause.

### 7.1 A script "succeeds" but the table stays empty

**Symptom.** `populate_sagri_plots.py` ran without errors for months.
`sagri_plots` held 269 rows with `farmer_id`, `national_id`, `selected_crop` and
`plot_name` **100% NULL**.

**Cause.** The script had been moved from `scripts/` into
`src/sagri_api/scripts/` without updating how it finds the project root:

```python
project_root = Path(__file__).parent.parent     # → src/sagri_api, not the repo root
```

The Excel path therefore pointed at a folder that does not exist. The script hit
its own "file not found" branch, printed a message, and **returned before
opening a database connection** — on every run, including `--apply`.

**Fix.** Count the levels. A script at `src/<module>/scripts/<name>.py` needs
**four** `.parent` calls to reach the repo root:

```python
project_root = Path(__file__).parent.parent.parent.parent
```

**The general lesson.** A missing input must be loud. Returning quietly makes
failure indistinguishable from success in a terminal nobody is watching. Exit
with an error code, and print the path it actually looked in:

```python
if not EXCEL_PATH.exists():
    print(f"  ❌ File not found: {EXCEL_PATH}")
    print(f"     Project root resolved to: {project_root.resolve()}")
    sys.exit(1)
```

**How to catch it early.** After any load, check populated columns rather than
row counts ([section 6.1](#61-the-check-that-matters-more-than-the-row-count)).
The row count looked plausible for the entire time this bug was live.

### 7.2 "Lost connection to MySQL server during query"

**Symptom.** A loader dies part-way. In the real case, at 12,500 of 28,895 rows.

**Cause.** One `cursor.execute()` per row against a remote host. Each row is a
network round trip; tens of thousands of them take around twenty minutes and the
connection eventually drops.

**Fix.** Batch with `executemany`, 500 rows at a time, and reconnect-and-retry
once on failure. `src/eudr/scripts/eudr_loader.py` → `_upsert_batches()` is the
reference implementation. Copy it rather than writing a new one.

**Before re-running, check what landed.** Loaders are idempotent — row hashes
with `ON DUPLICATE KEY UPDATE`, or `INSERT IGNORE` — so re-running is safe and
already-loaded rows are updated in place rather than duplicated.

**Watch where the commit sits.** A script that commits only at the very end
loses the whole run when the connection drops. `populate_sagri_plots.py` still
has this shape — fine at 2,700 rows, not at 30,000.

### 7.3 "Data too long for column" (error 1406)

**Symptom.** One row out of 2,695 fails to insert. The run completes, reports
`Errors: 1`, and still prints a green ✅.

**Cause.** `sagri_plots.national_id` was `VARCHAR(8)`, sized for a Peruvian DNI.
One plot is registered to a cooperative under an 11-digit **RUC**
(`20146696041`). `farmers.national_id` is `VARCHAR(50)` and stored it fine — the
child table was simply narrower than its parent.

**Fix.** Widen to match the parent. Widening a varchar is non-destructive:

```sql
ALTER TABLE sagri_plots MODIFY COLUMN national_id VARCHAR(50);
```

**Prevention.** Any column that joins to another must be at least as wide. Audit
with:

```sql
SELECT TABLE_NAME, CHARACTER_MAXIMUM_LENGTH
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'shared_data_layer'
  AND COLUMN_NAME = 'national_id'
ORDER BY CHARACTER_MAXIMUM_LENGTH;
```

**The wider lesson.** A national identifier is not always 8 digits. Juridical
persons — cooperatives and associations — hold an 11-digit RUC and appear in
`farmers` like any other counterparty. Never validate one by length alone.

### 7.4 Foreign keys match nothing, silently

**Symptom.** The loader reports success, the foreign key column is populated,
and joins return no rows.

**Cause.** `flo_id` is a `VARCHAR` and some values carry leading zeros.
Converting to `int` on the way in strips them, producing a value that looks
correct and matches nothing.

**Fix.** Treat identifiers as strings end to end. In `eudr_loader.py`:

```python
out['flo_id'] = df['floid'].map(_id)      # string — NOT _int
```

The same rule applies to national IDs. Use the shared `DNICleaner`, which
zero-pads to 8 and returns strings:

```python
from src.utils.dni_cleaner import DNICleaner
df['national_id'] = DNICleaner(verbose=False).clean(df['national_id'],
                                                    column_name='national_id')
```

Without it, a 7-digit national ID in a source file matches no farmer — silently.
This is a project-wide convention, not a per-script choice.

### 7.5 Dates load without error but are wrong

**Symptom.** Dates parse cleanly and land in the wrong month.

**Cause.** The providers disagree. Satelligence exports **month-first**
(`9/1/2023` = 9 January). Osapiens exports **day-first** (`31/12/2025`). One
shared parser silently mangles one of them, and only dates with a day above 12
reveal it.

**Fix.** One parser per provider, never shared. `osapiens_loader.py` defines
`_date_dmy()` specifically so it cannot inherit `eudr_loader._date()`.

The same trap exists in the Kobo trainings birth-date column, which holds
**both** formats from different devices' locales. It is parsed per value with
`dayfirst=True`, so pandas falls back to month-first only where day-first is
impossible.

### 7.6 Duplicate rows in a source workbook

**Symptom.** The preview reports more rows to update than exist in the table —
for example 270 updates against 269 existing codes.

**Cause.** The same key appears twice in the source file. In the real case,
`NORPIU0992` appeared twice with identical data and two spellings of the plot
name.

**What to do.** Decide whether the duplicate rows agree:

- **Identical data** — harmless. The second write overwrites the first with the
  same values. Report it to the file's owner so it is deduplicated at source.
- **Conflicting data** — stop. One record is wrong, and whichever row the loader
  reads last wins arbitrarily. A plot code pointing at the wrong farmer
  propagates into soil data and EUDR plot matching.

Check before applying:

```bash
python -c "import pandas as pd; df=pd.read_excel('data/raw/sagri/sagri_codes.xlsx',dtype=str); df.columns=[c.strip().lower().replace(' ','_') for c in df.columns]; c=df['sagri_code'].astype(str).str.strip(); print(c[c.duplicated(keep=False)].value_counts())"
```

---

## 8. Conventions that are not obvious from the code

These are decisions, not accidents. Changing one breaks something downstream.

- **Identifiers are strings.** `flo_id`, `national_id`, plot codes. Never `int`.
- **National IDs go through `DNICleaner`.** 8-digit zero-padded strings,
  everywhere, at every stage.
- **Loaders are idempotent.** Re-running is always safe. Row hashes
  (MD5 / SHA-256) with `ON DUPLICATE KEY UPDATE`, or `INSERT IGNORE` where
  source rows have no stable identifier of their own.
- **Dry run first.** Every loader has a preview mode — `--dry-run`, or the
  default no-write mode in `populate_sagri_plots.py`, `populate_cea_plots.py`
  and `update_ex_socios.py`, which require `--apply` to write. The preview
  prints match rates and insert/update counts. That is where a bad file gets
  caught, not after writing.
- **Soft links where the populations genuinely differ.**
  `training_participants.farmer_id` has no constraint, because many attendees
  are staff or external people who are not farmers. `extensionist_code` has no
  foreign key, so a technician code that is not yet registered still loads and
  gains a name later with no re-import. Match rates are printed every run
  instead.
- **Departed members are marked, not deleted.** `member_status = 'Ex-socio'`.
  History must stay intact.
- **No farmer data in git.** `.gitignore` blocks `data/`, every `.csv` and
  `.xlsx`, certificates, and `.env`. Before committing anything new, confirm it
  is covered.

---

## 9. Routine cadence

| Task | When | Section |
|---|---|---|
| Kobo visits | Monthly, or before a dashboard review | [5.1](#51-kobo--technical-assistance-visits) |
| Kobo trainings | Monthly | [5.2](#52-kobo--trainings) |
| EUDR Satelligence alerts | When a new export arrives from the provider | [5.4](#54-eudr) |
| EUDR Osapiens | When the coordinator shares a new assessment export | [5.4](#54-eudr) |
| EUDR contracts | When the buyer updates the contracts sheet | [5.4](#54-eudr) |
| SAGRI soil data | When a new monthly snapshot is available | [5.5](#55-sagri) |
| Estimations | Annually, per campaign | [5.3](#53-estimations--norandino-harvest-forecasts) |
| Ex-socio reconciliation | When a new membership file arrives | [4.4](#44-post-migration) |
| Stages 1–3 | When a PO sends corrected historical files | [4](#4-the-core-pipeline--stages-1-to-3) |
| Row-count baseline check | After every load | [6](#6-verifying-a-load) |

*These are current practice, not a formal commitment. Confirm with Sam before
treating any of them as a service level promised to a third party.*

---

## 10. Known open items

**Infrastructure**

- **MySQL 8.0 → 8.4 upgrade** before 30 October 2026. Owner: Sam.
- **`temp_table`** holds 0 rows and can be dropped.

**Code**

- **Input paths are not consistent across modules — deliberately deferred.**
  Most modules read from the central `data/` folder; EUDR reads from
  `src/eudr/data/` and estimations from `src/estimations/data/`. This is
  documented in [section 3](#3-where-the-source-files-go) rather than fixed,
  because consolidating means re-testing five working loaders against the live
  database for a purely cosmetic gain. **Do it when you are next editing those
  modules anyway**, not as a standalone change. The edits would be:
  `EUDR_DATA` in `eudr_loader.py`, `osapiens_loader.py` and
  `contracts_loader.py`; `RAW_DIR` / `PROCESSED_DIR` in `clean_estimations.py`
  and `load_estimations.py`. Then move the two folders, update the docstring in
  `load_estimations.py`, the README line naming `src/eudr/data/`, and this
  document.
  **`src/cea_api/data/cea_plot_codes.csv` must not move** — it is the only data
  file tracked in git, whitelisted in `.gitignore` on purpose, and the Streamlit
  app deployed on Streamlit Community Cloud reads it from the repository.
- **`scripts/run_polygons.py` and `scripts/run_trainings.py` are empty files**
  (0 bytes). They imply a runner exists when it does not — write them or delete
  them.
- **`src/eudr/eudr_README.md`** should be renamed to `src/eudr/README.md` so
  GitHub renders it automatically on the folder page.
- **`populate_sagri_plots.py` commits only at the end** of its run. Fine at the
  current row count; convert to batched commits if the workbook grows.

**Data**

- **Convoya loader** (`eudr_plot_validations`) deferred, pending the EUDR
  coordinator's answer on whether `CTO Farmer ID` and `CTO Plot ID` are swapped
  in the export.
- **`farm_plots`** — the unified plot registry with geometry — still to be
  designed and built.
- **Eight open questions with the EUDR data coordinator** on the Osapiens score
  scale and how compliance status is derived. Listed in
  `src/eudr/eudr_README.md`.
- **129 `sagri_plots` rows have no `plot_name`** — blank in the source workbook,
  not a load failure.
- **Plot names in `sagri_codes.xlsx` are inconsistently cased**
  (`La casa vieja` vs `CASA VIEJA`). Normalise before grouping or searching on
  them.

**Documentation**

- The README's Kobo section still says **5,668 technical visits**; the database
  holds **6,646**, which is what the Impact table says. One of the two is stale.
- `src/estimations/` has no module documentation.

---

## 11. Contact

| Area | Who |
|---|---|
| Pipeline, SDL, Power BI | Daniela Alvarez — BI Developer |
| Project ownership, infrastructure decisions | Sam — Producers Direct, UK |
| EUDR data and provider exports | EUDR data coordinator |
| Field data and Kobo forms | Producers Direct Peru team |

---

*Last updated: October 2026.*
