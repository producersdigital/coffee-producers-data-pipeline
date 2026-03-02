"""
Runner Script: Clean Chirinos Transactions

Demonstrates how to use the ChirinosTransactionsCleaner.

Usage:
    python scripts/clean_chirinos_transactions.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.stage1_cleaning.transactions.chirinos_transactions_cleaner import ChirinosTransactionsCleaner


def main():
    """Clean Chirinos transactions data."""
    
    print("\n" + "="*70)
    print("CHIRINOS TRANSACTIONS CLEANING")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Paths to yearly transaction files
    TRANSACTION_FILES = [
        'data/raw/transactions/chirinos/ACOPIO 2020.xlsx',
        'data/raw/transactions/chirinos/ACOPIO 2021.xlsx',
        'data/raw/transactions/chirinos/ACOPIO 2022.xlsx',
        'data/raw/transactions/chirinos/ACOPIO 2023.xlsx',
        'data/raw/transactions/chirinos/ACOPIO 2024.xlsx',
    ]
    
    # Where to save the cleaned data
    OUTPUT_FILE = 'data/processed/transactions/chirinos/chirinos_transactions_clean.pkl'
    
    BASE_PATH = None  # Optional
    
    # ========================================================================
    # PROCESSING
    # ========================================================================
    
    # Check for missing files
    missing_files = [f for f in TRANSACTION_FILES if not Path(f).exists()]
    
    if missing_files:
        print(f"\n❌ ERROR: The following files were not found:")
        for f in missing_files:
            print(f"   - {f}")
        print("\nPlease check the file paths and try again.")
        return
    
    try:
        # Create cleaner instance
        print(f"\nProcessing {len(TRANSACTION_FILES)} transaction files...")
        cleaner = ChirinosTransactionsCleaner(
            file_paths=TRANSACTION_FILES,
            base_path=BASE_PATH
        )
        
        # Clean all years
        clean_data = cleaner.clean_all_years()
        
        # Display summary
        print("\n" + "─"*70)
        print("SUMMARY")
        print("─"*70)
        summary = cleaner.get_summary()
        
        print(f"Total transactions: {summary['total_transactions']:,}")
        print(f"Years processed: {summary['years']}")
        
        for year in summary['years']:
            count = summary.get(f'year_{year}_count', 0)
            print(f"  - {year}: {count:,} transactions")
        
        if 'date_range' in summary:
            print(f"Date range: {summary['date_range']}")
        
        if 'unique_farmers' in summary:
            print(f"Unique farmers: {summary['unique_farmers']:,}")
        
        # Save
        print(f"\nSaving to: {OUTPUT_FILE}")
        cleaner.save(OUTPUT_FILE)
        
        print("\n" + "="*70)
        print("✅ Chirinos transactions cleaning completed successfully!")
        print("="*70)
        
        # Display preview
        print("\n\nFirst 3 transactions preview:")
        display_cols = [c for c in ['fecha', 'campania', 'nombre_productor', 'kg', 'categoria'] 
                       if c in clean_data.columns]
        print(clean_data[display_cols].head(3))
        
        print("\nColumn names:")
        print(clean_data.columns.tolist())
        
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()