"""
Script to run Aprocassi Transactions Cleaning
 
Usage:
    python scripts/clean_aprocassi_transactions.py
"""
 
import sys
from pathlib import Path
 
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
 
from src.stage1_cleaning.transactions.aprocassi_transactions_cleaner import AprocassiTransactionsCleaner
 
 
def main():
    """Run the Aprocassi transactions cleaning process."""
    
    print("\n" + "="*70)
    print("APROCASSI TRANSACTIONS CLEANING")
    print("="*70)
    
    print("\nProcessing transaction files...")
    
    # Initialize cleaner
    cleaner = AprocassiTransactionsCleaner()
    
    # Clean all years
    df = cleaner.clean_all_years()
    
    # Get summary
    summary = cleaner.get_summary()
    
    # Save
    print(f"\nSaving to: {cleaner.output_dir}")
    output_path = cleaner.save()
    
    # Print summary
    print("\n" + "─"*70)
    print("SUMMARY")
    print("─"*70)
    print(f"Total transactions: {summary['total_transactions']:,}")
    print(f"Years processed: {summary['years']}")
    for year, count in summary['transactions_by_year'].items():
        print(f"  - {year}: {count:,} transactions")
    
    if 'date_range' in summary:
        print(f"Date range: {summary['date_range']}")
    
    if 'unique_farmers' in summary:
        print(f"Unique farmers: {summary['unique_farmers']}")
    
    if 'total_kg' in summary:
        print(f"Total KG: {summary['total_kg']:,.2f}")
    
    print("\n" + "="*70)
    print("✅ Aprocassi transactions cleaning completed successfully!")
    print("="*70)
    
    # Preview
    print("\n\nFirst 3 transactions preview:")
    display_cols = [c for c in ['fecha', 'campania', 'nombre_productor', 'kg', 'categoria'] 
                    if c in df.columns]
    print(df[display_cols].head(3))
    
    print(f"\nColumn names:")
    print(df.columns.tolist())
    
    print("\n" + "="*70)
 
 
if __name__ == "__main__":
    main()