"""
Example Runner: Clean Bagua Transactions

This script demonstrates how to use the BaguaTransactionsCleaner
to process Bagua Grande transaction (acopio) data from multiple years.

Usage:
    python scripts/clean_bagua_transactions.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.stage1_cleaning.transactions import BaguaTransactionsCleaner


def main():
    """
    Clean Bagua transactions data from multiple years.
    
    Adjust the file paths below to match your directory structure.
    """
    print("\n" + "="*70)
    print("BAGUA GRANDE TRANSACTIONS CLEANING")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION - Update these paths for your setup
    # ========================================================================
    
    # Paths to yearly transaction files
    INPUT_FILES = [
        'data/raw/transactions/bagua/ACOPIO 2022.xlsm',
        'data/raw/transactions/bagua/ACOPIO 2023.xlsm',
        'data/raw/transactions/bagua/ACOPIO 2024.xlsm',
    ]
    
    # Where to save the cleaned combined data
    OUTPUT_FILE = 'data/processed/transactions/bagua/bagua_transactions_NEW.pkl'
    
    # Optional: Base path for all data (if using relative paths)
    BASE_PATH = None  # Set to your data directory if needed
    
    # ========================================================================
    # PROCESSING
    # ========================================================================
    
    # Check if input files exist
    missing_files = []
    for file_path in INPUT_FILES:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ ERROR: The following files were not found:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("\nPlease update the INPUT_FILES paths in this script.")
        return
    
    # Create cleaner instance
    cleaner = BaguaTransactionsCleaner(
        file_paths=INPUT_FILES,
        base_path=BASE_PATH
    )
    
    # Clean all years
    try:
        clean_data = cleaner.clean_all_years()
        
        # Display summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        summary = cleaner.get_summary()
        
        print(f"Total transactions: {summary['total_transactions']:,}")
        print(f"Years processed: {summary['years']}")
        
        for year in summary['years']:
            count = summary.get(f'year_{year}_count', 0)
            print(f"  - {year}: {count:,} transactions")
        
        if 'unique_farmers' in summary:
            print(f"Unique farmers: {summary['unique_farmers']:,}")
        
        if 'missing_dni' in summary:
            print(f"Missing DNI: {summary['missing_dni']:,}")
        
        if 'date_range' in summary:
            print(f"Date range: {summary['date_range']}")
        
        # Save cleaned data
        print(f"\nSaving to: {OUTPUT_FILE}")
        cleaner.save(OUTPUT_FILE)
        
        print("\n✅ Bagua transactions cleaning completed successfully!")
        print("="*70 + "\n")
        
        # Optional: Display first few rows
        print("\nFirst 3 transactions preview:")
        print(clean_data.head(3))
        
        print("\nColumn names:")
        print(clean_data.columns.tolist())
        
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
        print("\nMake sure the file paths are correct and the files exist.")
        
    except Exception as e:
        print(f"\n❌ ERROR during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()












