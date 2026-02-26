"""
Runner Script: Clean Huadquiña Transactions

Demonstrates how to use the HuadquinaTransactionsCleaner.

Usage:
    python scripts/clean_huadquina_transactions.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.stage1_cleaning.transactions.huadquina_transactions_cleaner import HuadquinaTransactionsCleaner


def main():
    """Clean Huadquiña transactions data."""
    
    print("\n" + "="*70)
    print("HUADQUIÑA TRANSACTIONS CLEANING")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Path to the Huadquiña template file
    INPUT_FILE = 'data/raw/transactions/huadquina/Plantilla de Acopio vf.xlsx'
    
    # Where to save the cleaned data
    OUTPUT_FILE = 'data/processed/transactions/huadquina/huadquina_transactions_clean.pkl'
    
    BASE_PATH = None
    
    # ========================================================================
    # PROCESSING
    # ========================================================================
    
    # Check if input file exists
    if not Path(INPUT_FILE).exists():
        print(f"\n❌ ERROR: Input file not found: {INPUT_FILE}")
        print("\nPlease update the INPUT_FILE path in this script.")
        return
    
    try:
        # Create cleaner instance
        print(f"\nInput file: {INPUT_FILE}")
        cleaner = HuadquinaTransactionsCleaner(
            file_path=INPUT_FILE,
            base_path=BASE_PATH
        )
        
        # Clean the data
        clean_data = cleaner.clean()
        
        # Display summary
        print("\n" + "─"*70)
        print("SUMMARY")
        print("─"*70)
        summary = cleaner.get_summary()
        
        print(f"Total transactions: {summary['total_transactions']:,}")
        
        if 'unique_farmers' in summary:
            print(f"Unique farmers: {summary['unique_farmers']:,}")
        
        if 'missing_dni' in summary:
            print(f"Missing DNI: {summary['missing_dni']:,}")
        
        if 'date_range' in summary:
            print(f"Date range: {summary['date_range']}")
        
        if 'campaigns' in summary:
            print(f"Campaigns: {summary['campaigns']}")
        
        # Save
        print(f"\n" + "─"*70)
        print("SAVING")
        print("─"*70)
        print(f"Saving to: {OUTPUT_FILE}")
        cleaner.save(OUTPUT_FILE)
        
        print("\n" + "="*70)
        print("✅ HUADQUIÑA TRANSACTIONS CLEANING COMPLETED SUCCESSFULLY!")
        print("="*70)
        
        print(f"\nOutput file: {OUTPUT_FILE}")
        print(f"Total records: {len(clean_data):,}")
        
        # Display first few rows
        print("\n" + "─"*70)
        print("SAMPLE DATA (first 3 rows)")
        print("─"*70)
        
        display_cols = ['fecha', 'campania', 'nombre_productor', 'kg', 'categoria']
        available_cols = [col for col in display_cols if col in clean_data.columns]
        print(clean_data[available_cols].head(3).to_string(index=False))
        
        print("\nColumn names:")
        print(clean_data.columns.tolist())
        
        print("\n" + "="*70 + "\n")
        
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
        print("\nMake sure the file path is correct and the file exists.")
        
    except Exception as e:
        print(f"\n❌ ERROR during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()