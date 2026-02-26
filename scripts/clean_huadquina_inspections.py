"""
Runner Script: Clean Huadquiña Inspections

Demonstrates how to use the HuadquinaInspectionsCleaner.

Usage:
    python scripts/clean_huadquina_inspections.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.stage1_cleaning.inspections.huadquina_inspections_cleaner import HuadquinaInspectionsCleaner


def main():
    """Clean Huadquiña inspections data."""
    
    print("\n" + "="*70)
    print("HUADQUIÑA INSPECTIONS CLEANING")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Path to the Huadquiña template file
    INPUT_FILE = 'data/raw/inspections/huadquina/Plantilla de Inspecciones vf.xlsx'
    
    # Where to save the cleaned data
    OUTPUT_FILE = 'data/processed/inspections/huadquina/huadquina_inspections_clean.pkl'
    
    BASE_PATH = None
    
    # Whether to generate farmer IDs (deduplication)
    GENERATE_FARMER_IDS = True
    
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
        cleaner = HuadquinaInspectionsCleaner(
            file_path=INPUT_FILE,
            base_path=BASE_PATH
        )
        
        # Step 1: Clean the data
        print("\n" + "─"*70)
        print("STEP 1: CLEANING DATA")
        print("─"*70)
        clean_data = cleaner.clean()
        
        # Step 2: Generate farmer IDs (optional)
        if GENERATE_FARMER_IDS:
            print("\n" + "─"*70)
            print("STEP 2: GENERATING FARMER IDs")
            print("─"*70)
            clean_data = cleaner.generate_farmer_ids(po_prefix='HU')
        else:
            print("\n" + "─"*70)
            print("STEP 2: SKIPPED (Farmer ID generation disabled)")
            print("─"*70)
        
        # Display summary
        print("\n" + "─"*70)
        print("SUMMARY")
        print("─"*70)
        summary = cleaner.get_summary()
        
        print(f"Total rows: {summary['total_rows']:,}")
        print(f"Total columns: {summary['total_columns']}")
        
        if 'unique_dni' in summary:
            print(f"Unique DNIs: {summary['unique_dni']:,}")
        
        if 'missing_dni' in summary:
            print(f"Missing DNI: {summary['missing_dni']:,}")
        
        if 'unique_farmers' in summary:
            print(f"Unique farmers (after deduplication): {summary['unique_farmers']:,}")
        
        if 'categorias' in summary:
            print(f"\nRecords by categoria:")
            for cat, count in summary['categorias'].items():
                print(f"  {cat}: {count}")
        
        # Save
        print(f"\n" + "─"*70)
        print("STEP 3: SAVING")
        print("─"*70)
        print(f"Saving to: {OUTPUT_FILE}")
        cleaner.save(OUTPUT_FILE)
        
        print("\n" + "="*70)
        print("✅ HUADQUIÑA INSPECTIONS CLEANING COMPLETED SUCCESSFULLY!")
        print("="*70)
        
        print(f"\nOutput file: {OUTPUT_FILE}")
        print(f"Total records: {len(clean_data):,}")
        
        # Display first few rows
        print("\n" + "─"*70)
        print("SAMPLE DATA (first 3 rows)")
        print("─"*70)
        
        display_cols = ['dni', 'nombre_productor', 'categoria', 'area_total_ha', 'area_cafe']
        if GENERATE_FARMER_IDS:
            display_cols.append('producers_direct_id_productor')
        
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