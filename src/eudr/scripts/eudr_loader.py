"""
EUDR Loader
===========
Cleans and loads the EUDR tracking sheets (exported as CSV) into the SDL.

Unlike the PO Excel files, the EUDR sheets already arrive integrated — every
producer organization (including POs from other countries) is in a single sheet
— so there is no stage1/2/3 split. This module does light cleaning (data types,
ID standardization, dropping exact duplicates) and loads directly, the same way
data_migrator.py loads its CSVs. The sheets are re-exported and re-loaded
periodically; both loaders are idempotent so re-running is always safe.

CSV source: src/eudr/data/  (relative to project root)
    EUDR_farm_level_alerts.csv  → eudr_satelligence_alerts
    EUDR_PO_compliance.csv      → eudr_po_compliance

    IMPORTANT: always export the two sheet tabs to these exact filenames
    (underscores, no spaces). The loader looks for them by name.

Idempotency:
    eudr_satelligence_alerts  UNIQUE row_hash (MD5 of identifying fields)
    eudr_po_compliance        UNIQUE (flo_id, year)
    both load with ON DUPLICATE KEY UPDATE — re-running never duplicates rows.

Prerequisite (run once in MySQL Workbench before the first load):
    - lookup_countries seeded with the EUDR countries
    - producer_organizations seeded with every flo_id in the sheets
    - eudr_satelligence_alerts and eudr_po_compliance tables created

Usage:
    cd src/eudr/scripts
    python eudr_loader.py              # clean + load both sheets
    python eudr_loader.py --dry-run    # clean + write *_CLEAN_PREVIEW.csv, no DB writes
"""

import argparse
import hashlib
import math
import re
import sys

import pandas as pd
from pathlib import Path

# Add project root to path (scripts/ → eudr → src → root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import create_connection

# ---------------------------------------------------------------------------
# Paths — relative to project root
# ---------------------------------------------------------------------------
EUDR_DATA      = PROJECT_ROOT / 'src' / 'eudr' / 'data'
ALERTS_CSV     = EUDR_DATA / 'EUDR_farm_level_alerts.csv'
COMPLIANCE_CSV = EUDR_DATA / 'EUDR_PO_compliance.csv'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NULL_TOKENS = {'', '-', 'n/a', 'na', 'none', 'null', 'nan'}

# Batch size for executemany. Smaller batches survive flaky remote connections
# better; the win over row-by-row comes from the round trips, not the size.
BATCH_SIZE = 500

# Source uses both singular and plural for the same alert type — standardize.
ALERT_TYPE_MAP = {
    'Farms within 200m of protected areas': 'Farms within 200m of protected area',
}

# Fields that define a unique alert. spo_next_steps is deliberately EXCLUDED so
# that editing next-steps text in the sheet updates the row instead of inserting
# a near-duplicate.
ALERT_HASH_FIELDS = [
    'flo_id', 'farmer_identifier', 'farm_unit_id',
    'farm_latitude', 'farm_longitude', 'alert_type', 'event_id', 'alert_id',
    'alert_latitude', 'alert_longitude', 'alert_date',
]


# =============================================================================
# SHARED HELPERS
# =============================================================================

def _val(value):
    """Return None for NaN/empty/placeholder values, else a stripped string.
    Collapses internal whitespace (including newlines) to single spaces."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    s = re.sub(r'\s+', ' ', str(value)).strip()
    return None if s.lower() in NULL_TOKENS else s


def _id(value):
    """Like _val but removes ALL whitespace — IDs sometimes contain embedded
    newlines in the source (e.g. 'CMS2-\\n480'). An ID must never contain spaces.

    Returns a STRING. Use this for every varchar ID column in the SDL, including
    flo_id — _int would strip leading zeros and silently break the FK match.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    s = re.sub(r'\s+', '', str(value))
    return None if s.lower() in NULL_TOKENS else s


def _num(value):
    """Return float or None."""
    if value is None:
        return None
    try:
        f = float(str(value).replace(',', '').strip())
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _int(value):
    f = _num(value)
    return int(round(f)) if f is not None else None


def _date(value):
    """Parse EUDR dates, which are M/D/YYYY (e.g. 10/18/2024 → 2024-10-18).

    NOTE: this is EUDR-specific and intentionally differs from the stage3 _date
    helper, which tries DD/MM/YYYY before MM/DD/YYYY. That order would misread an
    ambiguous EUDR date like 05/08/2024 (intended May 8) as August 5. Satelligence
    is always M/D/YYYY, so this parses it explicitly.

    WARNING for the future Osapiens loader: Osapiens dates are DAY-first
    (31/12/2025). Do NOT reuse this helper there.
    """
    from datetime import datetime
    s = _val(value)
    if not s:
        return None
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def _coord(value, is_lat=True):
    v = _num(value)
    if v is None:
        return None
    if is_lat and not (-90 <= v <= 90):
        return None
    if not is_lat and not (-180 <= v <= 180):
        return None
    return v


def _row_hash(values: dict) -> str:
    """MD5 over ALERT_HASH_FIELDS — enables idempotent re-runs."""
    parts = [str(values.get(f)) if values.get(f) is not None else '' for f in ALERT_HASH_FIELDS]
    return hashlib.md5('|'.join(parts).encode('utf-8')).hexdigest()


def _progress(loaded: int, total: int, label: str):
    pct = loaded / total * 100 if total else 0
    print(f"    [{pct:5.1f}%] {loaded:,}/{total:,} processed  ({label})", flush=True)


def _upsert_batches(conn, cursor, sql, rows, label):
    """Send rows in batches, reconnecting and retrying once if the connection drops.

    Remote hosts drop long-running connections; a single failed batch should not
    cost the whole load. Returns (conn, cursor, loaded) — the connection objects
    are returned because a reconnect replaces them.
    """
    total  = len(rows)
    loaded = 0

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        try:
            cursor.executemany(sql, batch)
            conn.commit()
        except Exception as e:
            print(f"  \u26a0\ufe0f  Batch at row {i:,} failed ({e}) \u2192 reconnecting and retrying once")
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
            conn = create_connection()
            if not conn:
                raise RuntimeError("Reconnection failed")
            cursor = conn.cursor()
            cursor.executemany(sql, batch)
            conn.commit()
        loaded += len(batch)
        _progress(loaded, total, label)

    return conn, cursor, loaded


# =============================================================================
# CLEANING
# =============================================================================

def _clean_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Raw alerts sheet → clean dataframe ready for eudr_satelligence_alerts."""
    out = pd.DataFrame()
    out['flo_id']            = df['floid'].map(_id)
    out['po_name']           = df['po_name'].map(_val)
    out['farmer_identifier'] = df['farmer_id'].map(_id)
    out['farm_unit_id']      = df['farm_unit_id'].map(_id)
    out['farm_latitude']     = df['farm_latitude'].map(lambda v: _coord(v, is_lat=True))
    out['farm_longitude']    = df['farm_longitude'].map(lambda v: _coord(v, is_lat=False))
    out['alert_type']        = df['alert_type'].map(_val).replace(ALERT_TYPE_MAP)
    out['event_id']          = df['event_id'].map(_id)
    out['alert_id']          = df['alert_id'].map(_id)
    out['alert_latitude']    = df['alert_latitude'].map(lambda v: _coord(v, is_lat=True))
    out['alert_longitude']   = df['alert_longitude'].map(lambda v: _coord(v, is_lat=False))
    out['alert_date']        = df['alert_date'].map(_date)
    # New alert attributes (may be empty until Satelligence starts populating them).
    # These are NOT part of ALERT_HASH_FIELDS: they are measurements/descriptions of
    # an alert, not its identity, so they update in place rather than creating new rows.
    # Note for future polygon data: a polygon-type alert may have empty alert_lat/long
    # (location lives in alert_polygons); revisit the hash strength when that arrives.
    out['alert_geolocation_type'] = df['alert_geolocation_type'].map(_val) if 'alert_geolocation_type' in df.columns else None
    out['alert_polygons']         = df['alert_polygons'].map(_val) if 'alert_polygons' in df.columns else None
    out['monitored_area']         = df['monitored_area'].map(_num) if 'monitored_area' in df.columns else None
    out['deforestation_area']     = df['deforestation_area'].map(_num) if 'deforestation_area' in df.columns else None
    out['spo_next_steps']    = df['spo_next_steps'].map(_val)

    # Drop rows missing the essentials (FK + farm location + identifier)
    before = len(out)
    out = out.dropna(subset=['flo_id', 'farmer_identifier', 'farm_latitude', 'farm_longitude'])
    if before - len(out):
        print(f"  \u2139\ufe0f  Dropped {before - len(out)} rows missing flo_id / farmer_identifier / farm coordinates")

    # Drop rows identical in ALL columns (confirmed export artifact in the sheet)
    before = len(out)
    out = out.drop_duplicates()
    print(f"  \u2139\ufe0f  Dropped {before - len(out):,} exact duplicate rows (identical in all columns)")

    # Idempotency hash; keep last when identifying fields match but next-steps differ
    out['row_hash'] = out.apply(lambda r: _row_hash(r.to_dict()), axis=1)
    dup_hash = out['row_hash'].duplicated().sum()
    if dup_hash:
        print(f"  \u2139\ufe0f  {dup_hash} rows share identifying fields (differ only in "
              f"spo_next_steps) \u2192 keeping last")
        out = out.drop_duplicates('row_hash', keep='last')

    # Fill rate of the newer Satelligence columns — tells you at a glance whether
    # the export actually carries them yet.
    print("  \u2139\ufe0f  Fill rate of optional alert columns:")
    for col in ['alert_geolocation_type', 'alert_polygons', 'monitored_area', 'deforestation_area']:
        print(f"       {col:<24} {out[col].notna().sum():,} / {len(out):,}")

    return out.reset_index(drop=True)


def _clean_compliance(df: pd.DataFrame):
    """Raw compliance sheet → clean dataframe ready for eudr_po_compliance.
    Returns None if the sheet has a duplicated (flo_id, year) key (a sheet error).

    NOTE: the sheet also has 'compliance_id' (the sheet's own row number) and
    'country' columns. Both are intentionally ignored: compliance_id is redundant
    with the table's own auto-increment PK, and country is derived via
    flo_id -> producer_organizations -> lookup_countries (avoids the 'Brasil'
    vs 'Brazil' spelling drift present in the sheet).
    """
    out = pd.DataFrame()
    out['flo_id']                     = df['flo_id'].map(_id)
    out['po_name']                    = df['po_name'].map(_val)
    out['year']                       = df['year'].map(_int)
    out['compliance_level']           = df['compliance_level'].map(_val)
    out['excluded_farms']             = df['excluded_farms'].map(_val).replace({'xyz': None})
    out['members']                    = df['members'].map(_int)
    out['monitored_area_ha']          = df['monitored_area_ha'].map(_num)
    out['farms_count']                = df['farms_count'].map(_int)
    out['points']                     = df['points'].map(_int)
    out['polygons']                   = df['polygons'].map(_int)
    out['deforestation_farms_count']  = df['deforestation_farms_count'].map(_int)
    out['deforestation_ha']           = df['deforestation_ha'].map(_num)
    out['alert_farms_count']          = df['alert_farms_count'].map(_int)
    out['alert_count']                = df['alert_count'].map(_int)
    out['protected_area_farms_count'] = df['protected_area_farms_count'].map(_int)
    out['current_validation_status']  = df['current_validation_status'].map(_val)
    out['last_validation_date']       = df['last_validation_date'].map(_date)
    out['last_updated']               = df['last_updated'].map(_date)

    out = out.dropna(subset=['flo_id', 'year'])

    # (flo_id, year) is the unique key — a conflict is a sheet error, not
    # something to silently merge. Abort so it gets fixed at the source.
    dups = out[out.duplicated(['flo_id', 'year'], keep=False)]
    if len(dups):
        print("  \u274c DATA ERROR: duplicated (flo_id, year) in the compliance sheet:")
        print(dups[['flo_id', 'po_name', 'year']].to_string(index=False))
        print("     Fix these in the Google Sheet, re-export, and run again.")
        return None

    return out.reset_index(drop=True)


# =============================================================================
# LOADERS
# =============================================================================

ALERT_COLUMNS = [
    'flo_id', 'po_name', 'farmer_identifier', 'farm_unit_id',
    'farm_latitude', 'farm_longitude', 'alert_type', 'event_id', 'alert_id',
    'alert_latitude', 'alert_longitude', 'alert_date',
    'alert_geolocation_type', 'alert_polygons', 'monitored_area', 'deforestation_area',
    'spo_next_steps', 'row_hash',
]

COMPLIANCE_COLUMNS = [
    'flo_id', 'po_name', 'year', 'compliance_level', 'excluded_farms',
    'members', 'monitored_area_ha', 'farms_count', 'points', 'polygons',
    'deforestation_farms_count', 'deforestation_ha', 'alert_farms_count',
    'alert_count', 'protected_area_farms_count', 'current_validation_status',
    'last_validation_date', 'last_updated',
]


def _upsert_sql(table: str, columns: list) -> str:
    cols   = ', '.join(f"`{c}`" for c in columns)
    ph     = ', '.join(['%s'] * len(columns))
    update = ', '.join(f"`{c}` = VALUES(`{c}`)" for c in columns)
    return f"INSERT INTO {table} ({cols}) VALUES ({ph}) ON DUPLICATE KEY UPDATE {update}"


def load_eudr_alerts(dry_run: bool = False) -> bool:
    """Clean and load the farm-level alerts sheet into eudr_satelligence_alerts."""
    df = _clean_alerts(pd.read_csv(ALERTS_CSV, dtype=str))
    print(f"  Clean alert rows ready: {len(df):,}")

    if dry_run:
        out = ALERTS_CSV.with_name(ALERTS_CSV.stem + '_CLEAN_PREVIEW.csv')
        df.to_csv(out, index=False)
        print(f"  \u2139\ufe0f  DRY RUN — no DB writes. Preview saved to {out.name}")
        return True

    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        sql = _upsert_sql('eudr_satelligence_alerts', ALERT_COLUMNS)
        rows = [
            tuple(None if pd.isna(row[c]) else row[c] for c in ALERT_COLUMNS)
            for _, row in df.iterrows()
        ]
        conn, cursor, loaded = _upsert_batches(conn, cursor, sql, rows, 'alerts')
        print(f"  \u2705 {loaded:,} alerts upserted")
        return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"  \u274c {e}")
        return False
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


def load_eudr_compliance(dry_run: bool = False) -> bool:
    """Clean and load the PO compliance sheet into eudr_po_compliance."""
    df = _clean_compliance(pd.read_csv(COMPLIANCE_CSV, dtype=str))
    if df is None:
        return False
    print(f"  Clean compliance rows ready: {len(df):,}")

    if dry_run:
        out = COMPLIANCE_CSV.with_name(COMPLIANCE_CSV.stem + '_CLEAN_PREVIEW.csv')
        df.to_csv(out, index=False)
        print(f"  \u2139\ufe0f  DRY RUN — no DB writes. Preview saved to {out.name}")
        return True

    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        sql = _upsert_sql('eudr_po_compliance', COMPLIANCE_COLUMNS)
        rows = [
            tuple(None if pd.isna(row[c]) else row[c] for c in COMPLIANCE_COLUMNS)
            for _, row in df.iterrows()
        ]
        conn, cursor, loaded = _upsert_batches(conn, cursor, sql, rows, 'compliance')
        print(f"  \u2705 {loaded:,} compliance rows upserted")
        return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"  \u274c {e}")
        return False
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


# =============================================================================
# RESULTS
# =============================================================================

def show_results() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        print("\n" + "=" * 60)
        print("EUDR TABLE COUNTS")
        print("=" * 60)
        for table in ['eudr_satelligence_alerts', 'eudr_po_compliance']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table:<28} {cursor.fetchone()[0]:>9,}")
        return True
    except Exception as e:
        print(f"  \u274c {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# ORCHESTRATOR
# =============================================================================

def load_all_eudr(dry_run: bool = False) -> bool:
    """Run the full EUDR load. Idempotent — safe to re-run.

    To run only one part (e.g. a PO just sent an updated alerts export), comment
    out the step you don't need below. Re-running everything is harmless thanks
    to the ON DUPLICATE KEY UPDATE logic.
    """
    print("=" * 60)
    print(f"EUDR LOAD{'  (DRY RUN)' if dry_run else ''}")
    print("=" * 60)

    steps = [
        ("Load EUDR alerts",     lambda: load_eudr_alerts(dry_run),     True),
        ("Load EUDR compliance", lambda: load_eudr_compliance(dry_run), True),
        ("Show results",         show_results,                          not dry_run),
    ]

    for step_name, step_func, should_run in steps:
        if not should_run:
            print(f"\n  \u23ed  Skipping: {step_name}")
            continue
        print(f"\n\u2500\u2500 {step_name} {'\u2500' * max(0, 44 - len(step_name))}")
        if not step_func():
            print(f"\n\u274c FAILED at: {step_name}")
            return False

    print("\n" + "=" * 60)
    print(f"\u2705 EUDR LOAD COMPLETE{'  (DRY RUN)' if dry_run else ''}")
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(description='Clean and load EUDR tracking sheets into the SDL')
    parser.add_argument('--dry-run', action='store_true',
                        help='Clean and write *_CLEAN_PREVIEW.csv without inserting into the database')
    args = parser.parse_args()
    load_all_eudr(dry_run=args.dry_run)


if __name__ == '__main__':
    main()