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
    - Optional: Membership files for configured POs (see MEMBERSHIP_CONFIGS in data_integrator.py)
 
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
    MEMBERSHIP_CONFIGS,
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
 
 
def _check_membership_files() -> None:
    """Report which membership files are available for integration."""
    for po_key, config in MEMBERSHIP_CONFIGS.items():
        if config['path'].exists():
            print(f"  ✅ {config['org_code']} membership file found: {config['path'].name}")
        else:
            print(f"  ⏭  {config['org_code']} no membership file — will use inspections only")
 
 
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
    print("\nChecking membership files...")
    _check_membership_files()
 
    # -----------------------------------------------------------------------
    # Run the full Stage 2 pipeline
    # -----------------------------------------------------------------------
    mysql_tables = create_all_mysql_ready_datasets(
        export_csv=True,
        bagua_fuzzy_threshold=0.85,
        bagua_bad_matches=['AREVALO IZQUIERDO MARLO'],
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