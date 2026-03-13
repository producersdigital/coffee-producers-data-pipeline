"""
Script to run Chirinos Inspections Cleaning

Usage:
    python scripts/clean_chirinos_inspections.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.stage1_cleaning.inspections.chirinos_inspections_cleaner import ChirinosInspectionsCleaner


def main():
    """Run the Chirinos inspections cleaning process."""
    
    print("\n" + "="*70)
    print("CHIRINOS INSPECTIONS CLEANING")
    print("="*70)
    
    # Initialize cleaner
    cleaner = ChirinosInspectionsCleaner()
    
    # Clean all years
    df = cleaner.clean_all_years()
    
    # Generate farmer IDs
    df = cleaner.generate_farmer_ids()
    
    # Get summary
    summary = cleaner.get_summary()
    
    # Save
    print(f"\nSaving to: {cleaner.output_dir}")
    output_path = cleaner.save()
    print(f"✅ Saved pickle: {output_path.name} ({len(df)} rows)")
    
    # Print summary
    print("\n" + "─"*70)
    print("SUMMARY")
    print("─"*70)
    print(f"Total inspections: {summary['total_inspections']:,}")
    print(f"Years processed: {summary['years']}")
    
    for year, count in summary['inspections_by_year'].items():
        print(f"  - {year}: {count:,} inspections")
    
    if 'unique_farmers' in summary:
        print(f"Unique farmers: {summary['unique_farmers']}")
    
    print("\n" + "="*70)
    print("✅ Chirinos inspections cleaning completed successfully!")
    print("="*70)
    
    # Preview
    print("\n\nFirst 3 inspections preview:")
    display_cols = [c for c in ['producers_direct_id_productor', 'nombre_productor', 'dni', 
                                 'base', 'area_cafe', 'inspeccion_year']  
                    if c in df.columns]
    print(df[display_cols].head(3))
    
    print(f"\nColumn names:")
    print(df.columns.tolist())
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()