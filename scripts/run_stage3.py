"""
Runner Script: Stage 3 - SDL Migration
========================================
Migrates all Stage 2 CSV outputs into the DigitalOcean MySQL SDL database.
 
Follows the same pattern as run_stage2.py.
 
Prerequisites:
    - Stage 2 must have been run: python scripts/run_stage2.py
    - CSV files must exist in data/mysql_ready/{master,operational,lookup}/
    - .env must contain DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    - config/certificates/ca-certificate.crt must exist
 
Usage:
    # Full migration (clears and reloads everything except lookup tables)
    python scripts/run_stage3.py
 
    # Resume after a failed run (skips clearing, transactions resume by index)
    python scripts/run_stage3.py --resume
 
    # Completely fresh database (clears lookup tables too)
    python scripts/run_stage3.py --fresh
"""
 
import sys
import argparse
from pathlib import Path
 
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
 
from src.stage3_migration.data_migrator import (
    load_all_data,
    MYSQL_READY,
    MASTER,
    OPERATIONAL,
    LOOKUP,
)
 
 
# Expected CSV files — used to validate Stage 2 has been run
EXPECTED_FILES = [
    MASTER      / 'farmers_data.csv',
    MASTER      / 'lookup_producer_orgs.csv',
    OPERATIONAL / 'farmers_addresses.csv',
    OPERATIONAL / 'farmer_level_inspections.csv',
    OPERATIONAL / 'plot_level_inspections.csv',
    OPERATIONAL / 'farmer_level_harvests.csv',
    OPERATIONAL / 'plot_level_harvests.csv',
    OPERATIONAL / 'acopio_transactions.csv',
    LOOKUP      / 'lookup_currencies.csv',
    LOOKUP      / 'lookup_genders.csv',
    LOOKUP      / 'lookup_countries.csv',
    LOOKUP      / 'lookup_product_types.csv',
    LOOKUP      / 'lookup_units.csv',
]
 
 
def _validate_stage2_outputs() -> bool:
    """Check all Stage 2 CSV files exist before starting."""
    missing = [f for f in EXPECTED_FILES if not f.exists()]
    if missing:
        print("\n❌ Missing Stage 2 output files:")
        for f in missing:
            print(f"   {f.relative_to(project_root)}")
        print("\n   Run Stage 2 first: python scripts/run_stage2.py")
        return False
    return True
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Stage 3: Migrate CSV outputs to MySQL SDL database"
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume after a partial run (skip clearing tables)'
    )
    parser.add_argument(
        '--fresh',
        action='store_true',
        help='Completely fresh load (also clears lookup tables)'
    )
    args = parser.parse_args()
 
    print("\n" + "=" * 60)
    print("STAGE 3: SDL MIGRATION PIPELINE")
    print("=" * 60)
 
    # Validate Stage 2 outputs exist
    print("\nChecking Stage 2 outputs...")
    if not _validate_stage2_outputs():
        sys.exit(1)
    print(f"  ✅ All {len(EXPECTED_FILES)} CSV files found")
    print(f"  Source: {MYSQL_READY}")
 
    # Determine run mode
    if args.resume:
        print("\n  Mode: RESUME (main tables not cleared, transactions resume by index)")
        clear_main   = False
        clear_lookup = False
    elif args.fresh:
        print("\n  Mode: FRESH (all tables including lookups will be cleared)")
        clear_main   = True
        clear_lookup = True
    else:
        print("\n  Mode: FULL (main tables cleared, lookup tables preserved)")
        clear_main   = True
        clear_lookup = False
 
    # Run migration
    success = load_all_data(
        clear_main=clear_main,
        clear_lookup=clear_lookup,
    )
 
    if not success:
        print("\n  Tip: Fix the error above and re-run with --resume to continue")
        print("  from where it failed without reloading completed tables.")
        sys.exit(1)
 
 
if __name__ == "__main__":
    main()