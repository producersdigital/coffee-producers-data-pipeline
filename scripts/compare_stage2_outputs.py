"""
Stage 2 Output Comparison
==========================
Compares MySQL-ready CSV tables produced by Stage 2 (run_stage2.py)
against the reference CSVs exported from notebook_4.
 
Expected differences (all legitimate):
    farmer_level_inspections  MORE rows in Stage 2 — Chirinos now contributes
                               1 row per farmer per year (5 years) instead of 1 row total
    farmer_level_harvests     Same reason as above
    farmers_data              SAME row count — identity table, 1 row per farmer
    farmers_addresses         SAME row count — identity table, 1 row per farmer
    plot_level_inspections    SAME (Chirinos has no plots, other POs unchanged)
    plot_level_harvests       SAME
    acopio_transactions       SAME (transactions pipeline unchanged)
    lookup_*                  SAME (static tables)
 
Usage:
    python scripts/compare_stage2_outputs.py
 
    # Or point to custom directories:
    python scripts/compare_stage2_outputs.py \\
        --reference path/to/notebook4_csvs \\
        --stage2    path/to/mysql_ready
"""
 
import sys
import argparse
import pandas as pd
from pathlib import Path
 
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent
 
# Default paths — adjust if your notebook_4 CSVs are stored elsewhere
DEFAULT_REFERENCE_DIR = project_root / 'data' / 'mysql_ready_notebook4'
DEFAULT_STAGE2_DIR    = project_root / 'data' / 'mysql_ready'
 
# Tables where MORE rows in Stage 2 are expected and correct
EXPECTED_MORE_ROWS = {
    'farmer_level_inspections',
    'farmer_level_harvests',
}
 
# Tables where row counts must be identical
EXPECTED_SAME_ROWS = {
    'farmers_data',
    'farmers_addresses',
    'plot_level_inspections',
    'plot_level_harvests',
    'acopio_transactions',
    'lookup_countries',
    'lookup_producer_orgs',
    'lookup_genders',
    'lookup_product_types',
    'lookup_units',
    'lookup_currencies',
}
 
ALL_TABLES = EXPECTED_MORE_ROWS | EXPECTED_SAME_ROWS
 
# Key columns used for row-level comparison where counts match
# Maps table_name → list of columns to use as a composite key for duplicate detection
TABLE_KEYS = {
    'farmers_data':             ['pd_farmer_id', 'national_id', 'org_code'],
    'farmers_addresses':        ['pd_farmer_id', 'country_code', 'administrative_area_3'],
    'farmer_level_inspections': ['pd_farmer_id', 'inspection_year', 'org_code'],
    'plot_level_inspections':   ['pd_farmer_id', 'inspection_year', 'plot_name'],
    'farmer_level_harvests':    ['pd_farmer_id', 'harvest_year', 'product_code'],
    'plot_level_harvests':      ['pd_farmer_id', 'harvest_year', 'plot_name'],
    'acopio_transactions':      ['national_id', 'org_code', 'transaction_date', 'kg_quantity'],
}
 
 
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
 
def _load(path: Path, label: str) -> pd.DataFrame | None:
    """Load a CSV, return None if not found."""
    if not path.exists():
        print(f"  ⚠️  Not found: {path.name}  ({label})")
        return None
    df = pd.read_csv(path, low_memory=False)
    return df
 
 
def _compare_table(
    table_name: str,
    ref_df: pd.DataFrame,
    s2_df: pd.DataFrame,
) -> dict:
    """
    Compare one table between reference and Stage 2 output.
 
    Returns a result dict with keys:
        status          'OK' | 'EXPECTED_DIFF' | 'WARNING' | 'ERROR'
        ref_rows        int
        s2_rows         int
        row_diff        int (s2 - ref)
        col_diff        list of column name differences
        notes           list of human-readable observations
    """
    result = {
        'status':   'OK',
        'ref_rows': len(ref_df),
        's2_rows':  len(s2_df),
        'row_diff': len(s2_df) - len(ref_df),
        'col_diff': [],
        'notes':    [],
    }
 
    # --- Column check ---
    ref_cols = set(ref_df.columns)
    s2_cols  = set(s2_df.columns)
    only_in_ref = ref_cols - s2_cols
    only_in_s2  = s2_cols - ref_cols
 
    if only_in_ref:
        result['col_diff'].append(f"Only in reference: {sorted(only_in_ref)}")
        result['status'] = 'WARNING'
    if only_in_s2:
        result['col_diff'].append(f"Only in Stage 2:   {sorted(only_in_s2)}")
        # New columns in Stage 2 are expected (e.g. inspection_year on temporal tables)
        result['notes'].append(f"Stage 2 has {len(only_in_s2)} additional column(s) — likely intentional")
 
    # --- Row count check ---
    if result['row_diff'] == 0:
        result['notes'].append("Row count matches exactly ✅")
 
    elif table_name in EXPECTED_MORE_ROWS and result['row_diff'] > 0:
        result['status'] = 'EXPECTED_DIFF'
        chirinos_note = (
            f"Stage 2 has {result['row_diff']:+,} rows — expected "
            f"(Chirinos multi-year data: ~{result['row_diff']} extra rows from 2020–2023)"
        )
        result['notes'].append(chirinos_note)
 
    elif table_name in EXPECTED_SAME_ROWS and result['row_diff'] != 0:
        result['status'] = 'ERROR'
        result['notes'].append(
            f"❌ Row count mismatch: reference={result['ref_rows']:,}, "
            f"Stage 2={result['s2_rows']:,} (diff={result['row_diff']:+,})"
        )
 
    elif result['row_diff'] < 0:
        result['status'] = 'ERROR'
        result['notes'].append(
            f"❌ Stage 2 has FEWER rows than reference — data may be missing"
        )
 
    # --- Duplicate key check (only for tables with same row count) ---
    if result['row_diff'] == 0 and table_name in TABLE_KEYS:
        key_cols = [c for c in TABLE_KEYS[table_name] if c in s2_df.columns]
        if key_cols:
            dups = s2_df.duplicated(subset=key_cols, keep=False).sum()
            if dups > 0:
                result['status'] = 'WARNING'
                result['notes'].append(f"⚠️  {dups} duplicate rows detected on key {key_cols}")
            else:
                result['notes'].append(f"No duplicates on key {key_cols} ✅")
 
    # --- Null check on key columns ---
    if table_name in TABLE_KEYS:
        key_cols = [c for c in TABLE_KEYS[table_name][:1] if c in s2_df.columns]  # just primary key
        for col in key_cols:
            null_count = s2_df[col].isna().sum()
            if null_count > 0:
                result['status'] = 'WARNING' if result['status'] == 'OK' else result['status']
                result['notes'].append(f"⚠️  {null_count:,} null values in key column '{col}'")
 
    # --- org_code breakdown for identity tables (sanity check) ---
    if table_name in ('farmers_data', 'farmer_level_inspections') and 'org_code' in s2_df.columns:
        breakdown = s2_df['org_code'].value_counts().sort_index().to_dict()
        result['notes'].append(f"org_code breakdown: {breakdown}")
 
    # --- Chirinos year breakdown for temporal tables ---
    if table_name in EXPECTED_MORE_ROWS:
        year_col = 'inspection_year' if 'inspection_year' in s2_df.columns else 'harvest_year'
        if year_col in s2_df.columns:
            ch_mask = s2_df.get('org_code', pd.Series()) == 'CH' if 'org_code' in s2_df.columns else pd.Series(dtype=bool)
            if ch_mask.any():
                ch_years = s2_df.loc[ch_mask, year_col].value_counts().sort_index().to_dict()
                result['notes'].append(f"Chirinos rows by year: {ch_years}")
 
    return result
 
 
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
 
def main(reference_dir: Path, stage2_dir: Path):
    print("\n" + "=" * 70)
    print("STAGE 2 OUTPUT COMPARISON")
    print("=" * 70)
    print(f"  Reference (notebook_4): {reference_dir}")
    print(f"  Stage 2 output:         {stage2_dir}")
 
    if not reference_dir.exists():
        print(f"\n❌ Reference directory not found: {reference_dir}")
        print("   Export notebook_4 CSVs there first, then re-run this script.")
        sys.exit(1)
 
    if not stage2_dir.exists():
        print(f"\n❌ Stage 2 output directory not found: {stage2_dir}")
        print("   Run scripts/run_stage2.py first.")
        sys.exit(1)
 
    results      = {}
    ok_count     = 0
    expected_count = 0
    warning_count  = 0
    error_count    = 0
    missing_count  = 0
 
    print("\n" + "─" * 70)
 
    for table_name in sorted(ALL_TABLES):
        ref_path = reference_dir / f"{table_name}.csv"
        s2_path  = stage2_dir    / f"{table_name}.csv"
 
        ref_df = _load(ref_path, 'reference')
        s2_df  = _load(s2_path,  'stage2')
 
        if ref_df is None or s2_df is None:
            missing_count += 1
            results[table_name] = {'status': 'MISSING'}
            continue
 
        result = _compare_table(table_name, ref_df, s2_df)
        results[table_name] = result
 
        # Count by status
        if   result['status'] == 'OK':            ok_count += 1
        elif result['status'] == 'EXPECTED_DIFF': expected_count += 1
        elif result['status'] == 'WARNING':       warning_count += 1
        elif result['status'] == 'ERROR':         error_count += 1
 
        # Print result
        status_icon = {
            'OK':            '✅',
            'EXPECTED_DIFF': '📊',
            'WARNING':       '⚠️ ',
            'ERROR':         '❌',
        }.get(result['status'], '?')
 
        print(f"\n{status_icon} {table_name}")
        print(f"   Rows: reference={result['ref_rows']:,}  →  stage2={result['s2_rows']:,}  "
              f"(diff={result['row_diff']:+,})")
 
        if result['col_diff']:
            for cd in result['col_diff']:
                print(f"   Columns: {cd}")
 
        for note in result['notes']:
            print(f"   {note}")
 
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  ✅ OK (exact match):          {ok_count}")
    print(f"  📊 Expected difference:       {expected_count}  (Chirinos multi-year)")
    print(f"  ⚠️  Warnings:                 {warning_count}")
    print(f"  ❌ Errors (unexpected diff):  {error_count}")
    print(f"  Missing files:                {missing_count}")
 
    if error_count == 0 and missing_count == 0:
        print("\n✅ Stage 2 output looks correct — all differences are expected.")
    else:
        print(f"\n❌ {error_count + missing_count} issue(s) require investigation.")
        sys.exit(1)
 
    print("=" * 70 + "\n")
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare Stage 2 outputs vs notebook_4 reference CSVs")
    parser.add_argument(
        '--reference',
        type=Path,
        default=DEFAULT_REFERENCE_DIR,
        help=f"Path to notebook_4 CSV exports (default: {DEFAULT_REFERENCE_DIR})"
    )
    parser.add_argument(
        '--stage2',
        type=Path,
        default=DEFAULT_STAGE2_DIR,
        help=f"Path to Stage 2 CSV exports (default: {DEFAULT_STAGE2_DIR})"
    )
    args = parser.parse_args()
    main(args.reference, args.stage2)
 