"""
Script to run Aprocassi Inspections Cleaning
 
Usage:
    python scripts/clean_aprocassi_inspections.py
"""
 
import sys
from pathlib import Path
 
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
 
from src.stage1_cleaning.inspections.aprocassi_inspections_cleaner import AprocassiInspectionsCleaner
 
 
def main():
    """Run the Aprocassi inspections cleaning process."""
    
    print("\n" + "="*70)
    print("APROCASSI INSPECTIONS CLEANING")
    print("="*70)
    
    # Initialize cleaner
    cleaner = AprocassiInspectionsCleaner()
    
    # Clean data
    df = cleaner.clean()
    
    # Generate farmer IDs
    df = cleaner.generate_farmer_ids()
    
    # Get summary
    summary = cleaner.get_summary()
    
    # Save
    print(f"\nSaving to: {cleaner.output_dir}")
    output_path = cleaner.save()
    
    # Print summary
    print("\n" + "─"*70)
    print("SUMMARY")
    print("─"*70)
    print(f"Total inspections: {summary['total_inspections']:,}")
    
    if 'unique_farmers' in summary:
        print(f"Unique farmers: {summary['unique_farmers']}")
    
    if 'by_category' in summary:
        print(f"\nBy category:")
        for cat, count in summary['by_category'].items():
            print(f"  {cat}: {count}")
    
    if 'total_area_ha' in summary:
        print(f"\nTotal area: {summary['total_area_ha']:,.2f} hectares")
    
    print("\n" + "="*70)
    print("✅ Aprocassi inspections cleaning completed successfully!")
    print("="*70)
    
    # Preview
    print("\n\nFirst 3 inspections preview:")
    display_cols = [c for c in ['producers_direct_id_productor', 'nombre_productor', 
                                 'dni', 'base', 'area_cafe'] 
                    if c in df.columns]
    print(df[display_cols].head(3).to_string(index=False))
    
    print(f"\nColumn names:")
    print(df.columns.tolist())
    
    print("\n" + "="*70)
 
 
if __name__ == "__main__":
    main()