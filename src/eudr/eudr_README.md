# EUDR Module

Loads EU Deforestation Regulation compliance data into the SDL: satellite
deforestation alerts, legal due-diligence assessments, and the commercial
contracts that tie them to shipments.

---

## Why two providers

EUDR splits into two obligations, and two different platforms serve them:

| | **Satelligence** | **Osapiens** |
|---|---|---|
| Answers | has deforestation occurred on or near this plot? | is this supply chain legally compliant? |
| Grain | one row per alert per farm | one row per plot per assessment |
| Geometry | farm and alert coordinates | none |
| Output | alert type, date, deforested area | compliance status, 9 legal criteria, non-compliant area |
| Who uses it | the cooperative, before submitting | the broker, to file the DDS |

The cooperative validates its plots in Satelligence first and uploads only the
compliant ones to Osapiens, which the broker uses. Osapiens sometimes finds
further non-compliant plots.

These are **not** two sources for the same measurement, so they are never
merged into one table and there is no "provider" toggle. They join at the
cooperative and contract level.

A third platform, **Convoya**, serves the other broker (Mexico). It is a plot
validation register rather than an alerts feed — not yet migrated.

---

## Tables

| Table | Grain | Source file |
|---|---|---|
| `eudr_satelligence_alerts` | one alert per farm | `EUDR_farm_level_alerts.csv` |
| `eudr_po_compliance` | one row per PO per year | `EUDR_PO_compliance.csv` |
| `eudr_osapiens_assessments` | one assessment (per PO per contract) | `EUDR_Osapiens_farm_level_alerts.csv` |
| `eudr_osapiens_plot_findings` | one plot within an assessment | same file |
| `eudr_contracts` | one contract line | `EUDR_Comercial_CD_2026.csv` |

All source files live in `src/eudr/data/`, which is gitignored. Filenames must
match exactly — the loaders resolve them by path, not by argument.

### The Osapiens split

The Osapiens export is one row per plot, but every assessment-level column
repeats identically on each row. A cooperative with 331 plots stores its nine
legal scores, compliance status and dates 331 times.

Splitting at the natural grain gave 14 assessments and 1,201 plot findings from
the same file. Only `Land_plot_ID`, `monitored_area` and `non-compliance_area`
vary per row.

Consequence worth knowing: `compliance_status` is a property of the
**assessment**, not of each plot. A plot with `non_compliance_area = 0` inside
a Failed assessment still reads "Failed". Never build a "plots failed" count
from that column.

### The contract link

`eudr_contracts.purchase_ref_norm` joins to
`eudr_osapiens_assessments.doc_id_normalized`.

The broker runs one Osapiens assessment per contract, so this is what connects
a shipment to the plots that supplied it — the core of any
can-we-ship-this question.

Reference formats differ across sources, so both sides normalize to the longest
run of digits:

```
contracts:  14-50498           ->  50498
            P2600647           ->  2600647
osapiens:   IACL_PO50498_FOB   ->  50498
            IACH-49262         ->  49262
```

Coverage is currently thin (1 of 46 contracts) because most contracts ship
later than the assessments already run. It grows as assessments arrive.

---

## Running

```bash
conda activate coffee-data-system
cd src/eudr/scripts

python eudr_loader.py --dry-run
python eudr_loader.py

python osapiens_loader.py --dry-run
python osapiens_loader.py

python contracts_loader.py --dry-run
python contracts_loader.py
```

Always dry-run first. It cleans, validates and writes `*_CLEAN_PREVIEW.csv`
without touching the database.

### What to check in each dry run

**eudr_loader** — the fill-rate block for the four optional alert columns. If
`deforestation_area` drops to zero, the export lost those columns. Also watch
the "rows share identifying fields" line: a sudden jump means real alerts are
being collapsed by the row hash (see Gotchas).

**osapiens_loader** — assessments per cooperative should be one or two each. If
a PO shows hundreds, `Doc_ID` varies more than expected and `ASSESSMENT_KEY_FIELDS`
needs narrowing. Every `Doc_ID` should produce a non-null normalized value.

**contracts_loader** — no unmapped cooperative names, and ship/land months
parsed at 100%. A shortfall means a month abbreviation missing from `MONTH_MAP`.

All loads are idempotent. Re-running updates rows in place via
`ON DUPLICATE KEY UPDATE`; it never duplicates.

---

## Gotchas

**Dates differ by provider.** Satelligence is month-first (`9/1/2023` = 1 Sep).
Osapiens is day-first (`31/12/2025`). `eudr_loader._date` and
`osapiens_loader._date_dmy` are separate for this reason — sharing one parser
would silently null every day above 12.

**`flo_id` is varchar, always use `_id` not `_int`.** Integer conversion strips
leading zeros and breaks the FK match against `producer_organizations`. This
bug was live for one release.

**Contract months are mixed English and Spanish** in the same column: `May-26`
alongside `Ago-26`, `Set-26`, `Dic-26`, `Ene-27`. `MONTH_MAP` covers both.

**Cooperative names differ across every source.** `producer_organizations` uses
`org_name` (not `po_name`), and the contracts sheet writes `Frontera` for
COOPAFSI, `Huadquina` without the ñ, `Tzotzil` for Tzeltal Tzotzil.
`CONTRACT_PO_ALIASES` in `contracts_loader.py` maps them; accents are stripped
before lookup.

**Osapiens may send a blank `floid`.** It has done so for Norandino, whose EUDR
data exists only in Osapiens — so those rows dropping means that cooperative
disappears entirely. Check the Google Sheet has `floid` filled for every PO
before exporting.

**The row hash assumes point-type alerts.** `ALERT_HASH_FIELDS` includes
`alert_latitude` and `alert_longitude`. A polygon-type alert may carry neither
(its location sits in `alert_polygons`), so several distinct polygon alerts for
one farm, date and type would hash identically and collapse to one. Revisit the
hash when polygon alerts start arriving.

**"PO" means two different things.** In the EUDR sheets it is Producer
Organization. In `eudr_contracts.cafedirect_po` it is the buyer's purchase
order number. Never join them.

---

## Deferred: identifier resolution

`eudr_osapiens_plot_findings` has three columns intentionally left null on
every row: `resolved_farmer_id`, `resolved_farm_unit_id`, `match_method`.

Osapiens sends `Land_plot_ID` in a different format per cooperative:

| PO | Format | Appears to match |
|---|---|---|
| SJO (843) | `2546443` | Satelligence `farmer_id` |
| CECOVASA (795) | `SF02535389` | `farmer_id` |
| Tzeltal Tzotzil (837) | `#-OR11-44-1` | `farm_unit_id`, minus the `#-` |
| Aprocassi (912) | `LaPiria_27853…`, `67091`, `#-AXL32MR9` | mixed; some unresolvable |

That mapping is reverse-engineered from samples, not documented by Osapiens,
and at least one observed value has no resolution path. So `land_plot_id_raw`
is stored exactly as received and resolution is left to the forthcoming plot
registry (`farm_plots`), which should own that logic in one place rather than
having a second, weaker resolver here.

Nothing is blocked by this — the dashboard works at cooperative level.

---

## Open questions

Pending answers from the EUDR data coordinator and the providers:

1. **Osapiens legal criteria scale** — what are the min and max values, and does
   higher mean more or less risk? Observed values cluster near 2.0 for every
   cooperative and do not differentiate.
2. **`Deforest_degrad` is 0 or 6** while every other criterion sits near 2. A
   different scale, or a genuinely severe finding?
3. **Is `Compliance status` derived only from `Deforest_degrad`?** In every
   cooperative checked, status is Failed exactly when that flag is 6. If so,
   "cooperatives failing due diligence" is really a deforestation measure.
4. **What is `monitored_area`?** It is 3.94 on nearly every row for three
   cooperatives but varies for Aprocassi (0.74 to 5.01). Likely a default.
5. **Third compliance status** — "Not successful" appeared on one assessment.
   An assessment that errored is not the same as one that failed.
6. **Satelligence optional columns** — `deforestation_area` populates on 2% of
   rows; `monitored_area`, `alert_polygons` and `alert_geolocation_type` are
   empty. Are the latter three ever sent? Without `monitored_area`,
   `deforestation_area` has no denominator.
7. **Convoya ID columns** — `CTO Farmer ID` (`094-97-2-01`) is more granular
   than `CTO Plot ID` (`094-97-2`). Likely swapped.
8. **Does every contract get an assessment**, and how long after signing?

---

## Shared code

The Osapiens and contracts loaders import helpers from `eudr_loader.py`:
`_val`, `_id`, `_num`, `_upsert_sql`, `_upsert_batches`. All three live in the
same directory, so the bare import resolves; the `__main__` guard means nothing
executes on import.

`_upsert_batches` sends 500 rows per round trip and reconnects once on a
dropped connection. The remote host drops long-running connections — a
row-by-row loop over 29,000 alerts took roughly 20 minutes and failed partway;
batched it takes under a minute.
