"""
Cafédirect Contracts Loader
===========================
Loads the Cafédirect commercial contracts sheet into eudr_contracts.

One row per contract line, keyed on Cafedirect PO (Cafédirect's purchase order
number — NOT a producer organization; the EUDR sheets use "PO" for that and the
two must never be joined).

Purchase Ref is NOT unique: several contract lines can share one reference.

KEY JOIN: purchase_ref_norm matches eudr_osapiens_assessments.doc_id_normalized.
The broker runs an Osapiens assessment per contract, so this is what links a
shipment to the plots that supplied it.

MONTHS ARE MIXED ENGLISH AND SPANISH: May-26, Ago-26, Set-26, Dic-26, Ene-27.
Stored as the first of the month.

flo_id is resolved by name against producer_organizations.org_name (note: the
column is org_name, not po_name). The sheet uses short forms that differ from
the canonical names — Frontera is COOPAFSI, Huadquina lacks the ñ, Tzotzil is
stored as 'Tzeltal Tzotzil' — so CONTRACT_PO_ALIASES maps them. Unmapped rows
still load with a NULL flo_id and are reported.

CSV source: src/eudr/data/EUDR_Comercial_CD_2026.csv

Usage:
    cd src/eudr/scripts
    python contracts_loader.py
    python contracts_loader.py --dry-run
"""

import argparse
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import create_connection
from eudr_loader import _val, _id, _num, _upsert_sql, _upsert_batches

EUDR_DATA     = PROJECT_ROOT / 'src' / 'eudr' / 'data'
CONTRACTS_CSV = EUDR_DATA / 'EUDR_Comercial_CD_2026.csv'

# Sheet spelling -> exact org_name in producer_organizations.
# Keys are upper-cased and accent-stripped before lookup.
CONTRACT_PO_ALIASES = {
    'CHIRINOS':             'Chirinos',
    'APROCASSI':            'Aprocassi',
    'FRONTERA':             'COOPAFSI',   # Frontera San Ignacio = COOPAFSI (922)
    'FRONTERA SAN IGNACIO': 'COOPAFSI',
    'COOPAFSI':             'COOPAFSI',
    'HUADQUINA':            'Huadquiña',
    'BAGUA GRANDE':         'Bagua Grande',
    'CECOVASA':             'CECOVASA',
    'PANGOA':               'Pangoa',
    'NORANDINO':            'Norandino',
    'SAN JUAN DEL ORO':     'San Juan del Oro',
    'SJO':                  'San Juan del Oro',
    'TZOTZIL':              'Tzeltal Tzotzil',
    'TZELTAL TZOTZIL':      'Tzeltal Tzotzil',
    'SAN FERNANDO':         'San Fernando',
}

MONTH_MAP = {
    'ENE': 1,  'JAN': 1,
    'FEB': 2,
    'MAR': 3,
    'ABR': 4,  'APR': 4,
    'MAY': 5,
    'JUN': 6,
    'JUL': 7,
    'AGO': 8,  'AUG': 8,
    'SET': 9,  'SEP': 9,
    'OCT': 10,
    'NOV': 11,
    'DIC': 12, 'DEC': 12,
}

CONTRACT_COLUMNS = [
    'cafedirect_po', 'flo_id', 'po_name_raw', 'trader',
    'sales_contract_ref', 'purchase_ref', 'purchase_ref_norm', 'kgs',
    'ship_month', 'land_month', 'pod', 'shipping_status',
    'is_fairtrade', 'is_organic', 'species', 'quality',
]


# =============================================================================
# HELPERS
# =============================================================================

def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', str(s))
                   if unicodedata.category(c) != 'Mn')


def _month_year(value):
    """Parse 'May-26' / 'Ago-26' / 'Ene-27' to the first of that month."""
    s = _val(value)
    if not s:
        return None
    m = re.match(r'^([A-Za-zÁÉÍÓÚáéíóú]{3,4})[-/\s](\d{2,4})$', s)
    if not m:
        return None
    month = MONTH_MAP.get(_strip_accents(m.group(1)).upper()[:3])
    if not month:
        return None
    year = int(m.group(2))
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, 1).strftime('%Y-%m-%d')
    except ValueError:
        return None


def _normalize_ref(value):
    """Numeric core of a purchase reference, to match Osapiens doc_id_normalized.

    P2600647 -> 2600647 ; 14-50809 -> 50809 ; CPPE-14561 -> 14561
    """
    s = _val(value)
    if not s:
        return None
    runs = re.findall(r'\d+', s)
    if not runs:
        return None
    longest = max(runs, key=len)
    return longest if len(longest) >= 4 else None


def _yes_no(value, truthy):
    s = _val(value)
    if s is None:
        return 0
    return 1 if s.strip().upper() in truthy else 0


def _po_lookup():
    """canonical org_name (upper, accent-stripped) -> flo_id, from the SDL."""
    conn = create_connection()
    if not conn:
        return {}
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT flo_id, org_name FROM producer_organizations")
        return {
            _strip_accents(name).upper().strip(): str(flo)
            for flo, name in cursor.fetchall() if name
        }
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# CLEANING
# =============================================================================

def _clean_contracts(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out['cafedirect_po']      = df['Cafedirect PO'].map(_id)
    out['po_name_raw']        = df['Producer/Cooperative'].map(_val)
    out['trader']             = df['Trader'].map(_val)
    out['sales_contract_ref'] = df['Sales/ Contract Ref'].map(_val)
    out['purchase_ref']       = df['Purchase Ref'].map(_val)
    out['purchase_ref_norm']  = df['Purchase Ref'].map(_normalize_ref)
    out['kgs']                = df['Kgs'].map(_num)
    out['ship_month']         = df['Ship'].map(_month_year)
    out['land_month']         = df['Land'].map(_month_year)
    out['pod']                = df['POD'].map(_val)
    out['shipping_status']    = df['Shipping status'].map(_val)
    out['is_fairtrade']       = df['FT'].map(lambda v: _yes_no(v, {'FT', 'YES', 'SI', 'Y'}))
    out['is_organic']         = df['Organic'].map(lambda v: _yes_no(v, {'ORGANIC', 'ORGANICO', 'YES', 'SI'}))
    out['species']            = df['Arabica / Robusta'].map(_val)
    out['quality']            = df['Quality'].map(_val)

    before = len(out)
    out = out.dropna(subset=['cafedirect_po', 'po_name_raw'])
    if before - len(out):
        print(f"  \u2139\ufe0f  Dropped {before - len(out):,} rows with no Cafedirect PO or cooperative")

    before = len(out)
    out = out.drop_duplicates('cafedirect_po', keep='last')
    if before - len(out):
        print(f"  \u2139\ufe0f  Dropped {before - len(out):,} rows with a duplicate Cafedirect PO (kept last)")

    # Resolve flo_id: sheet spelling -> canonical org_name -> flo_id
    po_map = _po_lookup()
    if not po_map:
        print("  \u26a0\ufe0f  Could not read producer_organizations — flo_id will be NULL on every row")

    def resolve(name):
        key = _strip_accents(name).upper().strip()
        canonical = CONTRACT_PO_ALIASES.get(key, name)
        return po_map.get(_strip_accents(canonical).upper().strip())

    out['flo_id'] = out['po_name_raw'].map(resolve)

    unmapped = out[out['flo_id'].isna()]['po_name_raw'].unique()
    if len(unmapped):
        print(f"  \u26a0\ufe0f  {len(unmapped)} cooperative name(s) did not resolve to a flo_id: "
              f"{list(unmapped)}")
        print("       These rows still load, with flo_id NULL. Add them to CONTRACT_PO_ALIASES.")

    print("  \u2139\ufe0f  Contracts per cooperative:")
    print(out.groupby(['po_name_raw', 'flo_id'], dropna=False).size().to_string())
    print(f"  \u2139\ufe0f  Total volume: {out['kgs'].sum():,.0f} kg")
    print(f"  \u2139\ufe0f  Ship months parsed: {out['ship_month'].notna().sum():,} / {len(out):,}")
    print(f"  \u2139\ufe0f  Land months parsed: {out['land_month'].notna().sum():,} / {len(out):,}")
    print(f"  \u2139\ufe0f  Purchase refs normalized: {out['purchase_ref_norm'].notna().sum():,} / {len(out):,}")
    print(f"  \u2139\ufe0f  Traders: {out['trader'].value_counts().to_dict()}")
    print(f"  \u2139\ufe0f  Fairtrade: {int(out['is_fairtrade'].sum()):,} / {len(out):,}  "
          f"Organic: {int(out['is_organic'].sum()):,} / {len(out):,}")

    return out[CONTRACT_COLUMNS].reset_index(drop=True)


# =============================================================================
# LOAD
# =============================================================================

def load_contracts(dry_run: bool = False) -> bool:
    df = _clean_contracts(pd.read_csv(CONTRACTS_CSV, dtype=str))
    print(f"  Clean contract rows ready: {len(df):,}")

    if dry_run:
        out = CONTRACTS_CSV.with_name('CONTRACTS_CLEAN_PREVIEW.csv')
        df.to_csv(out, index=False)
        print(f"  \u2139\ufe0f  DRY RUN — no DB writes. Preview saved to {out.name}")
        return True

    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        sql = _upsert_sql('eudr_contracts', CONTRACT_COLUMNS)
        rows = [tuple(None if pd.isna(r[c]) else r[c] for c in CONTRACT_COLUMNS)
                for _, r in df.iterrows()]
        conn, cursor, n = _upsert_batches(conn, cursor, sql, rows, 'contracts')
        print(f"  \u2705 {n:,} contracts upserted")
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
        print("CONTRACTS")
        print("=" * 60)
        cursor.execute("SELECT COUNT(*) FROM eudr_contracts")
        print(f"  eudr_contracts {cursor.fetchone()[0]:>12,}")

        cursor.execute("SELECT COUNT(*) FROM eudr_contracts WHERE flo_id IS NULL")
        print(f"  rows with no flo_id {cursor.fetchone()[0]:>7,}")

        # Does the contract -> Osapiens assessment join actually land?
        cursor.execute("""
            SELECT COUNT(DISTINCT c.cafedirect_po)
            FROM eudr_contracts c
            JOIN eudr_osapiens_assessments a
              ON a.doc_id_normalized = c.purchase_ref_norm
        """)
        print(f"  contracts matching an Osapiens assessment: {cursor.fetchone()[0]:,}")
        return True
    except Exception as e:
        print(f"  \u274c {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Load the Cafédirect contracts sheet into the SDL')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print("=" * 60)
    print(f"CONTRACTS LOAD{'  (DRY RUN)' if args.dry_run else ''}")
    print("=" * 60)

    if not load_contracts(args.dry_run):
        print("\n\u274c FAILED")
        return
    if not args.dry_run:
        show_results()
    print("\n\u2705 CONTRACTS LOAD COMPLETE")


if __name__ == '__main__':
    main()