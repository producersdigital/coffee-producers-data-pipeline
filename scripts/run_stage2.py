"""
Runner Script: Stage 2 - Data Integration
==========================================
Loads all Stage 1 cleaned outputs, integrates them into MySQL-ready tables,
and exports CSVs to data/mysql_ready/.
 
Follows the same pattern as Stage 1 runner scripts (clean_*.py).
 
Usage:
    python scripts/run_stage2.py
 
Prerequisites:
    - All Stage 1 cleaners must have been run successfully
    - Processed pkl files must exist in data/processed/inspections/ and data/processed/transactions/
    - Optional: Norandino membership file at data/raw/inspections/norandino/MEMBRESIA COOP NORANDINO 13.10.25.xlsx
 
Outputs:
    data/mysql_ready/
    ├── farmers_data.csv
    ├── farmers_addresses.csv
    ├── farmer_level_inspections.csv
    ├── plot_level_inspections.csv
    ├── farmer_level_harvests.csv
    ├── plot_level_harvests.csv
    ├── acopio_transactions.csv
    ├── lookup_countries.csv
    ├── lookup_producer_orgs.csv
    ├── lookup_genders.csv
    ├── lookup_product_types.csv
    ├── lookup_units.csv
    └── lookup_currencies.csv
"""
 
import sys
import pandas as pd
from pathlib import Path
 
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
 
from src.stage2_integration.data_integrator import (
    create_all_mysql_ready_datasets,
    INSPECTION_PATHS,
    TRANSACTION_PATHS,
    MEMBERSHIP_PATHS,
    MEMBERSHIP_SHEET,
    MEMBERSHIP_HEADER,
    MYSQL_READY_DIR,
)
 
 
def _validate_stage1_outputs() -> bool:
    """
    Check all Stage 1 pkl files exist before starting.
    Prints a clear error for any missing file.
 
    Returns:
        True if all files present, False otherwise.
    """
    all_paths = {**INSPECTION_PATHS, **TRANSACTION_PATHS}
    # norandino_wide is checked separately (optional for plot table)
    missing = []
 
    for label, path in all_paths.items():
        if label == 'norandino_wide':
            # Warn but don't block — plot table will be skipped if missing
            if not path.exists():
                print(f"  ⚠️  norandino_wide not found (plot table will be skipped): {path}")
            continue
        if not path.exists():
            missing.append((label, path))
 
    if missing:
        print("\n❌ Missing Stage 1 output files:")
        for label, path in missing:
            print(f"   {label}: {path}")
        print("\n   Run Stage 1 cleaners before Stage 2.")
        return False
 
    return True
 
 
def _load_norandino_membership() -> 'pd.DataFrame | None':
    """
    Load Norandino membership file if it exists.
 
    Returns:
        DataFrame if file found, None otherwise.
    """
    path = MEMBERSHIP_PATHS['norandino']
 
    if not path.exists():
        print(f"  ℹ️  Norandino membership file not found — skipping membership integration")
        print(f"     Expected at: {path}")
        return None
 
    print(f"  Loading Norandino membership file...")
    df = pd.read_excel(
        path,
        sheet_name=MEMBERSHIP_SHEET['norandino'],
        header=MEMBERSHIP_HEADER['norandino'],
    )
    print(f"  ✅ Loaded membership file: {len(df):,} records")
    return df
 
 
def main():
    print("\n" + "=" * 70)
    print("STAGE 2: DATA INTEGRATION PIPELINE")
    print("=" * 70)
 
    # -----------------------------------------------------------------------
    # Validate Stage 1 outputs exist
    # -----------------------------------------------------------------------
    print("\nChecking Stage 1 outputs...")
    if not _validate_stage1_outputs():
        sys.exit(1)
    print("  ✅ All Stage 1 output files found")
 
    # -----------------------------------------------------------------------
    # Load optional Norandino membership file
    # -----------------------------------------------------------------------
    print("\nChecking Norandino membership file...")
    norandino_membership_df = _load_norandino_membership()
 
    # -----------------------------------------------------------------------
    # Run the full Stage 2 pipeline
    # -----------------------------------------------------------------------
    mysql_tables = create_all_mysql_ready_datasets(
        export_csv=True,
        bagua_fuzzy_threshold=0.85,
        bagua_bad_matches=['AREVALO IZQUIERDO MARLO'],
        norandino_membership_df=norandino_membership_df,
    )
 
    # -----------------------------------------------------------------------
    # Final confirmation
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"✅ Stage 2 complete — {len(mysql_tables)} tables exported")
    print(f"   Output directory: {MYSQL_READY_DIR}")
    print(f"{'=' * 70}\n")
 
 
if __name__ == "__main__":
    main()