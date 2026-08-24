"""
Estimations — Stage 3 SDL Load
==============================================================================
Loads the two Stage-1 CSVs into the SDL:
 
    data/processed/collection_estimations.csv       -> collection_estimations
    data/processed/collection_estimation_crops.csv  -> collection_estimation_crops
 
Idiom: matches src/stage3_migration/data_migrator.py — plain functions,
_val/_num helpers, loaders return bool, ON DUPLICATE KEY UPDATE for idempotent
re-runs, emoji logging, an orchestrator with a steps list. (Not the Kobo
class+argparse idiom: there is no API session/pagination state to hold here —
this is file-in, table-out, exactly like the migration stages.)
 
org_id resolution:
    All six current files are Norandino. The sheet never says "Norandino" on
    its own, so the source cooperative is passed on the CLI and resolved once
    against producer_organizations — the same WHERE org_code = %s lookup
    load_farmers uses — then stamped on every row.
 
Dry run (always run this first):
    python load_estimations.py --source-org-code NO --dry-run
        Connects read-only. Resolves org_id, reports the farmer match rate
        against farmers.national_id, and shows how many rows would be inserted
        / updated / left unchanged (via row_hash). Writes nothing.
 
Real load:
    python load_estimations.py --source-org-code NO
 
Author: Daniela (assisted)
"""
 
import argparse
import sys
from pathlib import Path
 
import pandas as pd
 
# ── project bootstrap (repo convention) ──────────────────────────────────────
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from src.database.connection import create_connection  # noqa: E402
 
MODULE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = MODULE_DIR / 'data' / 'processed'
HEADERS_CSV = PROCESSED_DIR / 'collection_estimations.csv'
CROPS_CSV = PROCESSED_DIR / 'collection_estimation_crops.csv'
 
# =============================================================================
# ACOPIO-UNIT CONVERSION CONFIG
# =============================================================================
# estimated_volume_acopio = estimated_volume_kg * factor, labelled acopio_unit.
# Defaults to identity (kg) until collection_transactions' unit is confirmed.
# When you learn the acopio unit for a crop, set it here and re-run the load —
# the operation is idempotent, so it simply rewrites the two acopio columns.
#
# Example once confirmed (coffee acopio recorded in 56 kg pergamino quintales):
#   ('COFFEE', 'PERGAMINO'): ('QQ_56KG', 1.0 / 56.0),
ACOPIO_CONVERSIONS = {
    # (crop_code, product_form): (acopio_unit, factor_from_kg)
    ('COFFEE',    'PERGAMINO'): ('KG', 1.0),
    ('SUGARCANE', 'CANE'):      ('KG', 1.0),
    ('CACAO',     'DRY_BEAN'):  ('KG', 1.0),
}
DEFAULT_ACOPIO = ('KG', 1.0)
 
 
# =============================================================================
# HELPERS  (mirrors data_migrator.py)
# =============================================================================
def _val(v):
    """None for NaN/empty, else stripped string."""
    if v is None:
        return None
    if isinstance(v, float) and __import__('math').isnan(v):
        return None
    s = str(v).strip()
    return None if s in ('', 'nan', 'NaN', 'None', 'NA') else s
 
 
def _num(v):
    """float or None."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if __import__('math').isnan(f) else f
    except (ValueError, TypeError):
        return None
 
 
def _int(v):
    n = _num(v)
    return int(n) if n is not None else None
 
 
def _acopio(crop_code, product_form, kg):
    """Return (acopio_value, acopio_unit) for a canonical kg estimate."""
    if kg is None:
        return None, None
    unit, factor = ACOPIO_CONVERSIONS.get((crop_code, product_form), DEFAULT_ACOPIO)
    return round(kg * factor, 4), unit
 
 
def _read_processed():
    if not HEADERS_CSV.exists() or not CROPS_CSV.exists():
        print(f"  ❌ Processed CSVs not found in {PROCESSED_DIR}. Run clean_estimations.py first.")
        return None, None
    h = pd.read_csv(HEADERS_CSV, dtype={'farmer_identifier': str})
    c = pd.read_csv(CROPS_CSV, dtype={'farmer_identifier': str})
    return h, c
 
 
# =============================================================================
# ORG RESOLUTION + PRE-FLIGHT
# =============================================================================
def resolve_source_org(cursor, org_code: str):
    """Resolve the source cooperative to org_id (same lookup load_farmers uses)."""
    cursor.execute(
        "SELECT org_id, org_name FROM producer_organizations WHERE org_code = %s",
        (org_code,)
    )
    result = cursor.fetchone()
    if not result:
        print(f"  ❌ Source org_code '{org_code}' not found in producer_organizations.")
        print("     Check the code (see lookup_producer_orgs.csv) and pass --source-org-code.")
        return None
    org_id, org_name = result[0], result[1]
    print(f"  ✅ Source org: {org_name} (org_code={org_code}, org_id={org_id})")
    return org_id
 
 
def report_farmer_match(cursor, headers: pd.DataFrame):
    """Report how many distinct farmer_identifier exist in farmers.national_id."""
    ids = sorted(headers['farmer_identifier'].dropna().unique())
    if not ids:
        return
    found = 0
    CHUNK = 1000
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        placeholders = ','.join(['%s'] * len(chunk))
        cursor.execute(
            f"SELECT COUNT(DISTINCT national_id) FROM farmers WHERE national_id IN ({placeholders})",
            chunk
        )
        found += cursor.fetchone()[0]
    pct = found / len(ids) * 100
    flag = '✅' if pct >= 95 else ('⚠️' if pct >= 80 else '❌')
    print(f"  {flag} farmer match: {found:,}/{len(ids):,} distinct identifiers "
          f"in farmers.national_id ({pct:.1f}%)")
    print("      (soft link — unmatched rows still load; use this to decide on a hard FK)")
 
 
def _diff_counts(cursor, table, key_cols, rows):
    """Return (insert, update, unchanged) by comparing (key -> row_hash) with the DB."""
    existing = {}
    cursor.execute(f"SELECT {', '.join(key_cols)}, row_hash FROM {table}")
    for r in cursor.fetchall():
        existing[tuple(str(x) for x in r[:-1])] = r[-1]
    ins = upd = same = 0
    for row in rows:
        key = tuple(str(row[k]) for k in key_cols)
        if key not in existing:
            ins += 1
        elif existing[key] != row['row_hash']:
            upd += 1
        else:
            same += 1
    return ins, upd, same
 
 
# =============================================================================
# LOADERS
# =============================================================================
def load_estimation_headers(headers: pd.DataFrame, org_id: int, dry_run: bool) -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        rows = headers.to_dict('records')
        if dry_run:
            ins, upd, same = _diff_counts(
                cursor, 'collection_estimations',
                ['estimation_year', 'farmer_identifier'], rows)
            print(f"  ℹ️  collection_estimations: {ins:,} insert, {upd:,} update, {same:,} unchanged")
            return True
 
        loaded = 0
        for row in rows:
            cursor.execute("""
                INSERT INTO collection_estimations (
                    estimation_year, farmer_identifier, org_id, producer_name,
                    org_first_level, org_coordination, org_base_internal, unit_code,
                    sic_name, caserio, district, province, department,
                    membership_status, member_since_year, farm_area_ha,
                    farm_area_certified_ha, cert_status, cert_status_prior,
                    source_file, row_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    org_id=VALUES(org_id), producer_name=VALUES(producer_name),
                    org_first_level=VALUES(org_first_level),
                    org_coordination=VALUES(org_coordination),
                    org_base_internal=VALUES(org_base_internal),
                    unit_code=VALUES(unit_code), sic_name=VALUES(sic_name),
                    caserio=VALUES(caserio), district=VALUES(district),
                    province=VALUES(province), department=VALUES(department),
                    membership_status=VALUES(membership_status),
                    member_since_year=VALUES(member_since_year),
                    farm_area_ha=VALUES(farm_area_ha),
                    farm_area_certified_ha=VALUES(farm_area_certified_ha),
                    cert_status=VALUES(cert_status),
                    cert_status_prior=VALUES(cert_status_prior),
                    source_file=VALUES(source_file), row_hash=VALUES(row_hash)
            """, (
                _int(row['estimation_year']), _val(row['farmer_identifier']), org_id,
                _val(row['producer_name']), _val(row['org_first_level']),
                _val(row['org_coordination']), _val(row['org_base_internal']),
                _val(row['unit_code']), _val(row['sic_name']), _val(row['caserio']),
                _val(row['district']), _val(row['province']), _val(row['department']),
                _val(row['membership_status']), _int(row['member_since_year']),
                _num(row['farm_area_ha']), _num(row['farm_area_certified_ha']),
                _val(row['cert_status']), _val(row['cert_status_prior']),
                _val(row['source_file']), _val(row['row_hash']),
            ))
            loaded += 1
        conn.commit()
        print(f"  ✅ {loaded:,} header rows upserted")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_estimation_crops(crops: pd.DataFrame, org_id: int, dry_run: bool) -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        rows = crops.to_dict('records')
        if dry_run:
            ins, upd, same = _diff_counts(
                cursor, 'collection_estimation_crops',
                ['estimation_year', 'farmer_identifier', 'crop_code'], rows)
            print(f"  ℹ️  collection_estimation_crops: {ins:,} insert, {upd:,} update, {same:,} unchanged")
            return True
 
        loaded = 0
        for row in rows:
            crop = _val(row['crop_code'])
            form = _val(row['product_form'])
            kg = _num(row['estimated_volume_kg'])
            acopio_val, acopio_unit = _acopio(crop, form, kg)
            cursor.execute("""
                INSERT INTO collection_estimation_crops (
                    estimation_year, farmer_identifier, org_id, crop_code, product_form,
                    area_total_ha, area_production_ha, area_growth_ha,
                    estimated_volume_kg, source_value, source_unit,
                    estimated_volume_acopio, acopio_unit,
                    derived_product, derived_volume_kg, derived_source_value,
                    derived_source_unit, source_file, row_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    org_id=VALUES(org_id), product_form=VALUES(product_form),
                    area_total_ha=VALUES(area_total_ha),
                    area_production_ha=VALUES(area_production_ha),
                    area_growth_ha=VALUES(area_growth_ha),
                    estimated_volume_kg=VALUES(estimated_volume_kg),
                    source_value=VALUES(source_value), source_unit=VALUES(source_unit),
                    estimated_volume_acopio=VALUES(estimated_volume_acopio),
                    acopio_unit=VALUES(acopio_unit),
                    derived_product=VALUES(derived_product),
                    derived_volume_kg=VALUES(derived_volume_kg),
                    derived_source_value=VALUES(derived_source_value),
                    derived_source_unit=VALUES(derived_source_unit),
                    source_file=VALUES(source_file), row_hash=VALUES(row_hash)
            """, (
                _int(row['estimation_year']), _val(row['farmer_identifier']), org_id,
                crop, form, _num(row['area_total_ha']), _num(row['area_production_ha']),
                _num(row['area_growth_ha']), kg, _num(row['source_value']),
                _val(row['source_unit']), acopio_val, acopio_unit,
                _val(row['derived_product']), _num(row['derived_volume_kg']),
                _num(row['derived_source_value']), _val(row['derived_source_unit']),
                _val(row['source_file']), _val(row['row_hash']),
            ))
            loaded += 1
        conn.commit()
        print(f"  ✅ {loaded:,} crop rows upserted")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
# =============================================================================
# ORCHESTRATOR
# =============================================================================
def load_estimations(source_org_code: str, dry_run: bool = True, years=None) -> bool:
    print("=" * 62)
    print(f"ESTIMATIONS — STAGE 3 LOAD{'  (DRY RUN — no writes)' if dry_run else ''}")
    print("=" * 62)
 
    headers, crops = _read_processed()
    if headers is None:
        return False
    if years:
        yset = set(years)
        headers = headers[headers['estimation_year'].isin(yset)]
        crops = crops[crops['estimation_year'].isin(yset)]
    print(f"  Loaded {len(headers):,} header + {len(crops):,} crop rows from processed CSVs")
 
    # pre-flight: resolve org + report match rate (needs a read-only connection)
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        print("\n── Pre-flight " + "─" * 34)
        org_id = resolve_source_org(cursor, source_org_code)
        if org_id is None:
            return False
        report_farmer_match(cursor, headers)
    finally:
        cursor.close()
        conn.close()
 
    steps = [
        ("Load estimation headers", lambda: load_estimation_headers(headers, org_id, dry_run)),
        ("Load estimation crops",   lambda: load_estimation_crops(crops, org_id, dry_run)),
    ]
    for name, fn in steps:
        print(f"\n── {name} {'─' * max(0, 44 - len(name))}")
        if not fn():
            print(f"\n❌ FAILED at: {name}")
            return False
 
    print("\n" + "=" * 62)
    if dry_run:
        print("✅ DRY RUN COMPLETE — re-run without --dry-run to write")
    else:
        print("✅ ESTIMATIONS LOAD COMPLETE")
    print("=" * 62)
    return True
 
 
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Load estimation CSVs into the SDL.")
    ap.add_argument('--source-org-code', required=True,
                    help="org_code in producer_organizations for the source coop (e.g. NO for Norandino -> org_id 249).")
    ap.add_argument('--dry-run', action='store_true',
                    help="Resolve org, report match rate + insert/update counts, write nothing.")
    ap.add_argument('--year', type=int, action='append',
                    help="Restrict to specific year(s); repeatable. Default: all.")
    args = ap.parse_args()
    ok = load_estimations(args.source_org_code, dry_run=args.dry_run, years=args.year)
    sys.exit(0 if ok else 1)