"""
Master Runner: Clean ALL Bagua Data (Inspections + Transactions)

This script runs both the inspections cleaner and transactions cleaner
for Bagua Grande, completing the full data cleaning pipeline.

Usage:
    python scripts/clean_bagua_complete.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.stage1_cleaning.inspections import BaguaInspectionsCleaner
from src.stage1_cleaning.transactions import BaguaTransactionsCleaner


def main():
    """
    Complete cleaning workflow for Bagua Grande:
    1. Clean inspections (LPA file)
    2. Clean transactions (Acopio files)
    """
    print("\n" + "="*70)
    print("BAGUA GRANDE - COMPLETE DATA CLEANING")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Inspections file
    INSPECTIONS_FILE = 'data/raw/BAGUA GRANDE/LPA 24.xlsx'
    INSPECTIONS_OUTPUT = 'data/processed/BAGUA GRANDE/bagua_inspections_clean.pkl'
    
    # Transaction files (multiple years)
    TRANSACTIONS_FILES = [
        'data/raw/BAGUA GRANDE/ACOPIO 2022.xlsm',
        'data/raw/BAGUA GRANDE/ACOPIO 2023.xlsm',
        'data/raw/BAGUA GRANDE/ACOPIO 2024.xlsm',
    ]
    TRANSACTIONS_OUTPUT = 'data/processed/BAGUA GRANDE/bagua_transactions_clean.pkl'
    
    BASE_PATH = None  # Optional
    
    # ========================================================================
    # PART 1: CLEAN INSPECTIONS
    # ========================================================================
    
    print("\n" + "─" * 70)
    print("PART 1: CLEANING INSPECTIONS DATA")
    print("─" * 70)
    
    if not Path(INSPECTIONS_FILE).exists():
        print(f"❌ ERROR: Inspections file not found: {INSPECTIONS_FILE}")
        print("Skipping inspections cleaning...")
        inspections_success = False
    else:
        try:
            inspections_cleaner = BaguaInspectionsCleaner(
                file_path=INSPECTIONS_FILE,
                base_path=BASE_PATH
            )
            
            inspections_data = inspections_cleaner.clean_all_sheets()
            inspections_cleaner.save(INSPECTIONS_OUTPUT)
            
            # Summary
            summary = inspections_cleaner.get_summary()
            print("\n📊 Inspections Summary:")
            print(f"   Total rows: {summary['total_rows']:,}")
            print(f"   - Ecol: {summary['ecol_rows']:,}")
            print(f"   - C0: {summary['c0_rows']:,}")
            print(f"   - C1: {summary['c1_rows']:,}")
            print(f"   - C2: {summary['c2_rows']:,}")
            print(f"   Unique farmers: {summary['unique_farmers']:,}")
            
            inspections_success = True
            print("\n✅ Inspections cleaning completed!")
            
        except Exception as e:
            print(f"\n❌ ERROR in inspections cleaning: {e}")
            import traceback
            traceback.print_exc()
            inspections_success = False
    
    # ========================================================================
    # PART 2: CLEAN TRANSACTIONS
    # ========================================================================
    
    print("\n" + "─" * 70)
    print("PART 2: CLEANING TRANSACTIONS DATA")
    print("─" * 70)
    
    # Check for missing files
    missing_files = [f for f in TRANSACTIONS_FILES if not Path(f).exists()]
    
    if missing_files:
        print(f"❌ ERROR: The following transaction files were not found:")
        for f in missing_files:
            print(f"   - {f}")
        print("Skipping transactions cleaning...")
        transactions_success = False
    else:
        try:
            transactions_cleaner = BaguaTransactionsCleaner(
                file_paths=TRANSACTIONS_FILES,
                base_path=BASE_PATH
            )
            
            transactions_data = transactions_cleaner.clean_all_years()
            transactions_cleaner.save(TRANSACTIONS_OUTPUT)
            
            # Summary
            summary = transactions_cleaner.get_summary()
            print("\n📊 Transactions Summary:")
            print(f"   Total transactions: {summary['total_transactions']:,}")
            print(f"   Years: {summary['years']}")
            for year in summary['years']:
                count = summary.get(f'year_{year}_count', 0)
                print(f"   - {year}: {count:,} transactions")
            if 'unique_farmers' in summary:
                print(f"   Unique farmers: {summary['unique_farmers']:,}")
            
            transactions_success = True
            print("\n✅ Transactions cleaning completed!")
            
        except Exception as e:
            print(f"\n❌ ERROR in transactions cleaning: {e}")
            import traceback
            traceback.print_exc()
            transactions_success = False
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    
    if inspections_success and transactions_success:
        print("\n✅ ✅ COMPLETE SUCCESS! ✅ ✅")
        print("\nBagua Grande data is fully cleaned:")
        print(f"   ✓ Inspections: {INSPECTIONS_OUTPUT}")
        print(f"   ✓ Transactions: {TRANSACTIONS_OUTPUT}")
        
    elif inspections_success:
        print("\n⚠️  PARTIAL SUCCESS")
        print("   ✓ Inspections completed")
        print("   ✗ Transactions failed or skipped")
        
    elif transactions_success:
        print("\n⚠️  PARTIAL SUCCESS")
        print("   ✗ Inspections failed or skipped")
        print("   ✓ Transactions completed")
        
    else:
        print("\n❌ BOTH CLEANERS FAILED")
        print("Please check the error messages above and fix the issues.")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()