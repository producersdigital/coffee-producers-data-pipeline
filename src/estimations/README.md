# Estimations Module — Implementation

Cleans and loads Norandino's **"Estimado de acopio"** workbooks — one per
campaign year — into two SDL tables. These are the cooperative's own forecasts
of what each producer expects to harvest, which the acopio dashboard compares
against what was actually collected.

## Tables

| Table | Rows | Grain |
|---|---|---|
| `collection_estimations` | 24,067 | one row per producer per year |
| `collection_estimation_crops` | 25,267 | one row per producer-year-crop |

Natural keys: `(estimation_year, farmer_identifier)` for headers,
`(estimation_year, farmer_identifier, crop_code)` for crops.

---

## Running

Two stages, both run from the repo root.

```bash
# Stage 1 — Excel → CSV. No database connection.
python src/estimations/scripts/clean_estimations.py                # all years
python src/estimations/scripts/clean_estimations.py --year 2026    # one year
python src/estimations/scripts/clean_estimations.py --year 2025 --year 2026

# Stage 3 — CSV → SDL. Always dry-run first.
python src/estimations/scripts/load_estimations.py --source-org-code NO --dry-run
python src/estimations/scripts/load_estimations.py --source-org-code NO
```

Both exit with a non-zero status on failure, so they are safe to chain.

### Paths

| What | Where |
|---|---|
| Source workbooks | `src/estimations/data/raw/*.xlsx` |
| Cleaned CSVs | `src/estimations/data/processed/` |

> These are **module-local**, unlike most of the repo, which reads from the
> central `data/` folder. Consolidating this is a deferred item — see
> `docs/OPERATIONS.md`, section 10.

Drop new workbooks into `data/raw/` with the campaign year somewhere in the
filename. The year is parsed from the filename with `(20\d{2})`; a file without
one raises rather than guessing.

### `--source-org-code` is required

The workbook never names the cooperative anywhere inside it, so the source
organisation is supplied on the command line and resolved once against
`producer_organizations` using the same `WHERE org_code = %s` lookup that
`load_farmers` uses. All current files are Norandino (`NO`, `org_id` 249). The
resolved `org_id` is stamped on every row.

---

## Design

### Nothing is positional-safe

The source workbook drifts every year — columns are added, renamed, reordered,
and the header row moves. Two defences:

- **The header row is found, not assumed.** The first 15 rows are scanned for a
  cell containing exactly `Departamento`, a token present in every file.
- **Columns are mapped by regex against normalized header text**, not by
  position. `HEADER_COLUMN_MAP` pairs each canonical field with a pattern and a
  `required` flag. A required column that fails to map **raises** — the pipeline
  never silently loads NULLs where real data should be.

Accented characters are matched with `.` rather than the literal letter
(`caser.o`, `.rea`) because the exports are inconsistently encoded.

### The control total is the real safety net

Each file contains its own `TOTAL GENERAL` grand-total row. It is dropped from
the data, then reused as a check: the sum of loaded coffee kg must equal the
file's stated total, within 1 kg.

```
✅ control check 2025: file total 1,234,567.0 kg vs loaded 1,234,567.0 kg (Δ 0.00)
```

**If this fails, a column has shifted.** Fix the regex mapping — do not override
the check. `clean_estimations.py` exits non-zero when any year's control fails,
so a broken mapping cannot quietly flow into the load stage.

### Wide to long

Source files are wide across three crops — café, caña, cacao. Melting to long
means:

- adding a fourth crop later is a **data** change, not a schema migration
- the join to `collection_transactions` is a single `(year, farmer, crop)` join
  rather than a per-crop column pick

Crop rows are kept only when they carry signal — a volume or an area. A producer
with no cacao produces no cacao row.

### Panela: a derived product with drifting units

Panela is not an independent crop. It is a derived column on the sugarcane row,
exactly cane × 10% in every row of every file — verified, not assumed. It is
therefore carried as `derived_product` on the `SUGARCANE` row rather than given
a crop of its own.

Its unit changed mid-history: headers say `QQ DE 50 KGS` for 2021–2024 and `KG`
from 2025. The quintal years are normalized to kg (× 50), detected from the
header wording rather than the year, so a file that reverts is handled too.

`derived_source_value` and `derived_source_unit` preserve exactly what arrived.
Normalization is never destructive here.

### National IDs

Cleaned with the shared `DNICleaner` — float-to-int, strip leading apostrophes,
zero-pad to 8 — so `03212564` survives as a string instead of becoming
`3212564.0`. Rows with an empty identifier after cleaning are dropped.

### Idempotency

Both tables carry a SHA-256 `row_hash` over the content columns, with
`ON DUPLICATE KEY UPDATE` on the natural key. Re-running the same file is a
no-op; re-running a corrected file updates in place. The dry run uses the same
hash to report insert / update / unchanged counts before anything is written.

### Soft link to farmers

`farmer_identifier` holds the producer's national ID but has **no foreign key**
to `farmers`. Estimations include producers who may not yet exist in the SDL,
and the estimate is still worth keeping. The dry run reports the match rate
against `farmers.national_id`:

```
✅ farmer match: 7,912/8,104 distinct identifiers in farmers.national_id (97.6%)
```

The flag is ✅ at 95%+, ⚠️ at 80–95%, ❌ below. A sudden drop means the workbook
and `farmers` have diverged — investigate before loading.

### Duplicate producers within a year

If the same identifier appears twice in one file, the first is kept and a
warning is printed. The duplicate is a source-file problem; report it to
Norandino rather than letting it silently decide which row wins.

---

## Open item — acopio unit conversion

`ACOPIO_CONVERSIONS` maps each `(crop_code, product_form)` to an acopio unit and
a conversion factor from kg. **All three are currently identity (kg × 1.0)**,
because the unit `collection_transactions` records has not been confirmed.

```python
ACOPIO_CONVERSIONS = {
    ('COFFEE',    'PERGAMINO'): ('KG', 1.0),
    ('SUGARCANE', 'CANE'):      ('KG', 1.0),
    ('CACAO',     'DRY_BEAN'):  ('KG', 1.0),
}
```

When the acopio unit is confirmed — for example if coffee is recorded in 56 kg
pergamino quintales — set the factor and re-run the load. The operation is
idempotent, so it simply rewrites `estimated_volume_acopio` and `acopio_unit`.
Nothing else needs to change, and no re-clean is required.

Until then, **do not compare `estimated_volume_acopio` against
`collection_transactions` volumes** as though the units agree. They may not.

---

## Idiom

`load_estimations.py` deliberately matches `src/stage3_migration/data_migrator.py`
— plain functions, `_val` / `_num` / `_int` helpers, loaders returning `bool`,
an orchestrator with a steps list — rather than the Kobo importer's class and
argparse pattern. There is no API session or pagination state to hold here. This
is file-in, table-out, exactly like the migration stages.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `required columns unmapped -> <field>` | A header was renamed in the new workbook | Add the new wording to that field's regex in `HEADER_COLUMN_MAP` |
| `Header row (containing 'Departamento') not found` | The header sits below row 15, or the token was renamed | Raise `MAX_HEADER_SCAN`, or update `HEADER_TOKEN` |
| `Cannot infer year from filename` | The filename has no 4-digit year | Rename the file to include the campaign year |
| `❌ control check` mismatch | A column shifted and the wrong column was read as coffee volume | Fix the mapping; never bypass the check |
| `Processed CSVs not found` | Stage 1 has not been run for these years | Run `clean_estimations.py` first |
| `Source org_code 'XX' not found` | Wrong code passed | Check `producer_organizations.org_code` — Norandino is `NO` |
| Farmer match rate drops sharply | The workbook and `farmers` have diverged | Investigate before loading; rows still load, but the dashboard join will be thin |

---

*See also: `docs/OPERATIONS.md` for the pipeline runbook, and the Estimations
section of the root `README.md` for the summary.*
