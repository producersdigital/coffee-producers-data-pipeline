"""
Script to run Norandino Inspections Cleaning
 
This is the final and most complex cleaner in Stage 1.
Handles massive file with 2400+ columns and plot-level data aggregation.
 
Usage:
    python scripts/clean_norandino_inspections.py
"""
 
import sys
from pathlib import Path
 
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
 
from src.stage1_cleaning.inspections.norandino_inspections_cleaner import NorandinoInspectionsCleaner
 
 
def main():
    """Run the Norandino inspections cleaning process."""
    
    print("\n" + "="*70)
    print("NORANDINO INSPECTIONS CLEANING")
    print("="*70)
    
    # Initialize cleaner
    cleaner = NorandinoInspectionsCleaner()
    
    # Clean data
    cleaner.clean()
    
    # Generate farmer IDs
    print("\nGenerating unique farmer IDs...")
    cleaner.generate_farmer_ids(po_prefix='NO')
    
    # Sort by farmer ID and category
    print("  Sorting by farmer ID and category...")
    cleaner.data_with_plots = cleaner.data_with_plots.sort_values(
        ['producers_direct_id_productor', 'categoria'],
        kind='stable'
    ).reset_index(drop=True)
    
    # Create farmer-level data
    df = cleaner.drop_plot_columns()
    
    # Save both versions
    print(f"\nSaving to: {cleaner.output_dir}")
    cleaner.save()
    
    # Get summary
    summary = cleaner.get_summary()
    
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
    print("✅ Norandino inspections cleaning completed successfully!")
    print("="*70)
    
    # Preview
    print("\n\nFirst 3 inspections preview:")
    display_cols = [c for c in ['producers_direct_id_productor', 'nombre_productor', 
                                 'dni', 'categoria', 'area_cafe'] 
                    if c in df.columns]
    if display_cols:
        print(df[display_cols].head(3).to_string(index=False))
    
    print(f"\nColumn names ({len(df.columns)} total):")
    print(df.columns.tolist())
    
    print("\n" + "="*70)
 
 
if __name__ == "__main__":
    main()