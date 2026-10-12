"""
Osapiens Loader
===============
Cleans and loads the Osapiens EUDR due-diligence export into the SDL.

The source file is ONE ROW PER PLOT, but most columns describe the ASSESSMENT
(the cooperative-level due-diligence run) and repeat identically on every row.
Only Land_plot_ID, monitored_area and non-compliance_area vary per plot. So the
file splits into two tables:

    eudr_osapiens_assessments    one row per assessment  (deduplicated here)
    eudr_osapiens_plot_findings  one row per plot within an assessment

CSV source: src/eudr/data/EUDR_Osapiens_farm_level_alerts.csv

DATES ARE DAY-FIRST (31/12/2025). Satelligence is month-first. Do not mix the
two parsers — _date_dmy here, _date in eudr_loader.py.

IDENTIFIER RESOLUTION IS DEFERRED. Land_plot_ID arrives in a different format
per cooperative and the mapping to Satelligence IDs is reverse-engineered, not
documented. We store the raw value; resolved_farmer_id / resolved_farm_unit_id /
match_method stay NULL until farm_plots exists and can resolve them properly.

Usage:
    cd src/eudr/scripts
    python osapiens_loader.py
    python osapiens_loader.py --dry-run
"""

import argparse
import hashlib
import sys
import re 
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import create_connection
from eudr_loader import _val, _id, _num, _upsert_sql, _upsert_batches

EUDR_DATA   = PROJECT_ROOT / 'src' / 'eudr' / 'data'
OSAPIENS_CSV = EUDR_DATA / 'EUDR_Osapiens_farm_level_alerts.csv'


def _date_dmy(value):
    """Osapiens dates are DAY-first (31/12/2025, 02/07/2026)."""
    s = _val(value)
    if not s:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


SCORE_MAP = {
    'tax_anticorruption':        'tax_anticorruption',
    '3th_parties_rights':        'third_parties_rights',
    'Biological_diversity':      'biological_diversity',
    'Employee_rights':           'employee_rights',
    'Environm_Protection':       'environmental_protection',
    'LUR':                       'land_use_rights',
    'Rights_IIPP':               'rights_iipp',
    'Deforest_degrad':           'deforestation_degradation',
    'Intern_HHRR_protect':       'intern_hhrr_protect',
}

# What makes an assessment distinct. Scores and status are attributes that
# update in place, so they are NOT in the hash.
ASSESSMENT_KEY_FIELDS = [
    'flo_id', 'doc_id', 'item_id', 'report_creation_date', 'assess_date',
]

ASSESSMENT_COLUMNS = [
    'assessment_hash', 'flo_id', 'po_name',
    'report_creation_date', 'assess_date', 'product', 'refer_type',
    'doc_id', 'doc_id_normalized', 'item_id', 'compliance_status', 'risk_asess_id', 'harvest_dates',
] + list(SCORE_MAP.values())

FINDING_COLUMNS = [
    'assessment_hash', 'flo_id', 'land_plot_id_raw',
    'monitored_area', 'non_compliance_area',
]

def _normalize_doc_id(value):
    """Extract the contract number from the Doc_ID.

    Osapiens sends three formats for what appears to be the same reference as
    the contracts sheet's Purchase Ref:
        14-49052          -> 49052
        IACH 49309A       -> 49309
        IACL_PO49939_FOB  -> 49939
    Rule: take the longest run of digits. The '14' prefix is the trader's
    series, not the contract number.
    """
    s = _val(value)
    if not s:
        return None
    runs = re.findall(r'\d+', s)
    if not runs:
        return None
    longest = max(runs, key=len)
    return longest if len(longest) >= 4 else None


def _assessment_hash(row: dict) -> str:
    parts = [str(row.get(f)) if row.get(f) is not None else '' for f in ASSESSMENT_KEY_FIELDS]
    return hashlib.md5('|'.join(parts).encode('utf-8')).hexdigest()


def _clean_osapiens(df: pd.DataFrame):
    """Raw Osapiens sheet → (assessments, findings) dataframes."""
    base = pd.DataFrame()
    base['flo_id']               = df['floid'].map(_id)
    base['po_name']              = df['po_name'].map(_val)
    base['report_creation_date'] = df['report_creation_date'].map(_date_dmy)
    base['assess_date']          = df['Assess_date'].map(_date_dmy)
    base['product']              = df['Product'].map(_val)
    base['refer_type']           = df['Refer_type'].map(_val)
    base['doc_id']               = df['Doc_ID'].map(_id)
    base['doc_id_normalized']    = df['Doc_ID'].map(_normalize_doc_id)
    base['item_id']              = df['Item_ID'].map(_id)
    base['compliance_status']    = df['Compliance status'].map(_val)
    base['risk_asess_id']        = df['Risk_asess_ID'].map(_id)
    base['harvest_dates']        = df['Hasvest_dates'].map(_val)

    for src_col, db_col in SCORE_MAP.items():
        base[db_col] = df[src_col].map(_num) if src_col in df.columns else None

    base['land_plot_id_raw']    = df['Land_plot_ID'].map(_id)
    base['monitored_area']      = df['monitored_area'].map(_num)
    base['non_compliance_area'] = df['non-compliance_area'].map(_num)

    before = len(base)
    base = base.dropna(subset=['flo_id'])
    if before - len(base):
        print(f"  \u2139\ufe0f  Dropped {before - len(base):,} rows with no flo_id")

    base['assessment_hash'] = base.apply(lambda r: _assessment_hash(r.to_dict()), axis=1)

    assessments = base[ASSESSMENT_COLUMNS].drop_duplicates('assessment_hash').reset_index(drop=True)

    findings = base[FINDING_COLUMNS].copy()
    before = len(findings)
    findings = findings.dropna(subset=['land_plot_id_raw'])
    if before - len(findings):
        print(f"  \u2139\ufe0f  Dropped {before - len(findings):,} rows with no Land_plot_ID")
    findings = findings.drop_duplicates(['assessment_hash', 'land_plot_id_raw']).reset_index(drop=True)

    print(f"  \u2139\ufe0f  {len(assessments):,} distinct assessments across {base['flo_id'].nunique()} cooperatives")
    print("  \u2139\ufe0f  Assessments per cooperative:")
    print(assessments.groupby(['flo_id', 'po_name']).size().to_string())
    print("  \u2139\ufe0f  Doc_ID -> normalized:")
    print(assessments[['doc_id', 'doc_id_normalized']].drop_duplicates().to_string(index=False))
    print(f"  \u2139\ufe0f  Compliance status: "
          f"{assessments['compliance_status'].value_counts().to_dict()}")

    return assessments, findings


def load_osapiens(dry_run: bool = False) -> bool:
    assessments, findings = _clean_osapiens(pd.read_csv(OSAPIENS_CSV, dtype=str))
    print(f"  Clean assessment rows ready: {len(assessments):,}")
    print(f"  Clean finding rows ready:    {len(findings):,}")

    if dry_run:
        a_out = OSAPIENS_CSV.with_name('OSAPIENS_assessments_CLEAN_PREVIEW.csv')
        f_out = OSAPIENS_CSV.with_name('OSAPIENS_findings_CLEAN_PREVIEW.csv')
        assessments.to_csv(a_out, index=False)
        findings.to_csv(f_out, index=False)
        print(f"  \u2139\ufe0f  DRY RUN — no DB writes. Previews: {a_out.name}, {f_out.name}")
        return True

    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        # Assessments FIRST — findings have an FK to them.
        sql = _upsert_sql('eudr_osapiens_assessments', ASSESSMENT_COLUMNS)
        rows = [tuple(None if pd.isna(r[c]) else r[c] for c in ASSESSMENT_COLUMNS)
                for _, r in assessments.iterrows()]
        conn, cursor, n = _upsert_batches(conn, cursor, sql, rows, 'assessments')
        print(f"  \u2705 {n:,} assessments upserted")

        sql = _upsert_sql('eudr_osapiens_plot_findings', FINDING_COLUMNS)
        rows = [tuple(None if pd.isna(r[c]) else r[c] for c in FINDING_COLUMNS)
                for _, r in findings.iterrows()]
        conn, cursor, n = _upsert_batches(conn, cursor, sql, rows, 'findings')
        print(f"  \u2705 {n:,} plot findings upserted")
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


def show_results() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        print("\n" + "=" * 60)
        print("OSAPIENS TABLE COUNTS")
        print("=" * 60)
        for table in ['eudr_osapiens_assessments', 'eudr_osapiens_plot_findings']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table:<32} {cursor.fetchone()[0]:>9,}")
        return True
    except Exception as e:
        print(f"  \u274c {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Clean and load the Osapiens EUDR export into the SDL')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print("=" * 60)
    print(f"OSAPIENS LOAD{'  (DRY RUN)' if args.dry_run else ''}")
    print("=" * 60)

    if not load_osapiens(args.dry_run):
        print("\n\u274c FAILED")
        return
    if not args.dry_run:
        show_results()
    print("\n\u2705 OSAPIENS LOAD COMPLETE")


if __name__ == '__main__':
    main()