# Kobo Trainings Module — Implementation

Imports the **Capacitaciones Norandino** Kobo form (a repeat-group form, 3 sheets)
into two SDL tables, feeding the trainings dashboard.

## Tables

- **`trainings`** — one row per training event (parent, keyed on `kobo_uuid`).
- **`training_participants`** — one row per attendee, **unified**: registered and
  non-registered in one table with an `is_registered` flag.

## One-time setup

1. Create the tables: run `trainings_schema.sql` in Workbench.
2. Create the named export in Kobo (once): open the *Capacitaciones Norandino*
   form → **DATA → Downloads** → format **XLSX**, tick **Include labels**, keep
   repeat groups as **separate sheets** → **Save selection as** → name it
   **`Trainings`**. The importer finds it by that name.
3. Confirm `.env` has `KOBO_API_TOKEN` (the same token Visits uses) and
   `KOBO_SERVER_URL` (defaults to `https://eu.kobotoolbox.org`).

Form UID is set in the script: `ASSET_UID = "aEhGgarqvLn9gqQ7CxyXS8"`.

## Running

```bash
cd src/kobo_api/scripts
python import_kobo_trainings.py --dry-run    # download + process, no writes
python import_kobo_trainings.py              # download live from Kobo, load
python import_kobo_trainings.py --test 50    # only first 50 trainings
python import_kobo_trainings.py --file path/to/export.xlsx   # skip download
```

Each run pulls the current snapshot from Kobo (pull-on-demand — the same model
as Visits), saves a timestamped copy to `data/kobo_exports/`, then loads.

## Design

**Downloader** (`KoboXLSXExporter`) mirrors the Visits `KoboCSVExporter` but pulls
`data_url_xlsx` — a repeat-group form keeps its 3 sheets in XLSX; CSV flattens them.

**Sheet detection** is by name pattern (`no_registrados` / `registrados` / the rest),
not sheet position, so a renamed parent sheet won't break it.

**Linking**: participant `_submission__id` → `trainings.kobo_submission_id` (verified:
every child links to a parent). Hard FK.

**Column handling**
- Registered participants: the per-profile columns (`nombre_completo_socio`,
  `..._personal`, `..._int`, etc.) are coalesced into single `full_name` /
  `organization` / `gender` / `birth_date` fields. The Kobo `${...}` display columns
  are empty in exports and ignored.
- Non-registered: plain single columns map directly; `appagrop`/`area`/`reference`
  are NULL (registered-only).
- DNIs cleaned with the shared `DNICleaner`; `0`/too-short placeholders → NULL
  (common on non-registered externals).
- Birth dates are a **mixed** `d/m/Y` + `m/d/Y` column (different devices' locales:
  ~23k unambiguously day-first, ~11k month-first, ~23k ambiguous). Parsed per value
  with `dayfirst=True`, so pandas falls back to month-first when day-first is
  impossible — both unambiguous forms parse correctly; genuinely ambiguous values
  (both parts ≤12) default to day-first and a fraction may be off. Acceptable for a
  demographic field; if it ever matters, the raw string can be preserved too.

**FK / link policy**
- `trainings.org_id` → `producer_organizations` (Norandino=249, stamped). Hard FK.
- `trainings.extensionist_code` = `Nombre_Tecnico` (the technician **code**, not a DNI),
  stored as-is on every row. **No FK** — join to `extensionists.extensionist_code` for
  the name. A code not yet in `extensionists` loads fine and shows a NULL name until
  someone adds it (then the name appears on the next refresh, **no re-import**). Codes
  not currently in `extensionists` are counted in the run summary and logged to `logs/`.
- `training_participants.farmer_id` → `farmers`. **Soft link, no constraint** —
  many attendees are staff/externals (`Operarios`, `Terceros`…) not in `farmers`
  by design. Match rate is printed each run.

**Reported counts**: `reported_men` / `reported_women` / `reported_total` are the
enumerator's figures. Kept (not derived) because 218 trainings have
`Registrar listas? = No` — counts but no participant rows — so these are the only
attendee numbers for them. The dashboard can also COUNT participant rows for the
list-based trainings.

**Test submissions**: submissions whose `Nombre_Tecnico` is in the `TEST_CODES` set (e.g. `testeopd`, `croppietest`) are form trials, not real trainings, and are dropped at load (their participants excluded via the `valid` set). Add codes to `TEST_CODES` at the top of the script as they appear. Count reported each run.

**Duplicate submissions**: Kobo flags accidental resends with a `DUPLICATE-<ts>-<n>-<asset>-<uuid>` `_uuid` and clones the repeat children too. The importer groups parent rows by the trailing real UUID and keeps the most complete copy (tie-break: latest `_submission_time`, then lowest `_id`); the dropped copy's participants are excluded via the `valid` submission set. The clean 36-char UUID is stored as `kobo_uuid`. Count reported each run.

**Idempotency**
- `trainings`: `kobo_uuid` UNIQUE + `ON DUPLICATE KEY UPDATE` (edited submissions
  re-sync).
- `training_participants`: `row_hash` UNIQUE + `INSERT IGNORE` — Kobo repeat rows
  have no stable id of their own, so a content hash is the natural key. Re-running
  the same export is a no-op.

## Idiom

Matches `import_kobo_visits.py` (KoboImporter class, argparse, lookup dicts,
error-CSV logging, run summary) — the API-form case where that idiom fits, unlike
the file-based estimations loader.

## Verified against a real export

2,485 trainings; 29,710 participants (29,169 registered + 541 non-registered);
117 placeholder DNIs correctly nulled; INSERT arity and dry-run safety confirmed.
Farmer match rate and unmatched-extensionist counts are reported live against the SDL.
