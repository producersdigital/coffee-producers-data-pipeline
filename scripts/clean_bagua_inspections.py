"""
Runner Script: Clean Bagua Inspections (Comprehensive)

Demonstrates how to use the full-featured BaguaInspectionsCleaner.

Features:
- Complete data cleaning
- Optional farmer ID generation
- Summary statistics

Usage:
    python scripts/clean_bagua_inspections.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.stage1_cleaning.inspections.bagua_inspections_cleaner import BaguaInspectionsCleaner


def main():
    """
    Clean Bagua inspections data with full processing.
    """
    print("\n" + "="*70)
    print("BAGUA GRANDE INSPECTIONS CLEANING")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Path to the Bagua LPA file
    INPUT_FILE = 'data/raw/inspections/bagua/LPA 24.xlsx'
    
    # Where to save the cleaned data
    OUTPUT_FILE = 'data/processed/inspections/bagua/clean_bagua_LPA_NEW.pkl'
    
    # Optional: Base path for all data
    BASE_PATH = None
    
    # Whether to generate farmer IDs (cross-sheet matching)
    GENERATE_FARMER_IDS = True  # Set to False to skip this step
    
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
        cleaner = BaguaInspectionsCleaner(
            file_path=INPUT_FILE,
            base_path=BASE_PATH
        )
        
        # Step 1: Clean all sheets
        print("\n" + "─"*70)
        print("STEP 1: CLEANING DATA")
        print("─"*70)
        clean_data = cleaner.clean_all_sheets()
        
        # Display summary after cleaning
        print("\n" + "─"*70)
        print("CLEANING SUMMARY")
        print("─"*70)
        summary = cleaner.get_summary()
        print(f"Total rows: {summary['total_rows']:,}")
        print(f"  - Ecol (Orgánico): {summary['ecol_rows']:,} rows")
        print(f"  - C0: {summary['c0_rows']:,} rows")
        print(f"  - C1: {summary['c1_rows']:,} rows")
        print(f"  - C2: {summary['c2_rows']:,} rows")
        print(f"Unique farmers (by DNI): {summary['unique_farmers_dni']:,}")
        print(f"Missing DNI: {summary['missing_dni']:,}")
        
        # Step 2: Generate farmer IDs (optional)
        if GENERATE_FARMER_IDS:
            print("\n" + "─"*70)
            print("STEP 2: GENERATING FARMER IDs")
            print("─"*70)
            clean_data = cleaner.generate_farmer_ids(po_prefix='BG')
            
            # Updated summary
            summary = cleaner.get_summary()
            print(f"\nUnique farmers (global matching): {summary['unique_farmers_global']:,}")
        else:
            print("\n" + "─"*70)
            print("STEP 2: SKIPPED (Farmer ID generation disabled)")
            print("─"*70)
            print("Set GENERATE_FARMER_IDS = True to enable this feature")
        
        # Step 3: Save
        print("\n" + "─"*70)
        print("STEP 3: SAVING")
        print("─"*70)
        
        # Save as pickle (for comparison with notebook)
        print(f"Saving pickle: {OUTPUT_FILE}")
        cleaner.save(OUTPUT_FILE)

        # ALSO save as Excel (for manual inspection)
        excel_output = OUTPUT_FILE.replace('.pkl', '.xlsx')
        print(f"Saving Excel: {excel_output}")
        clean_data.to_excel(excel_output, index=False, engine='openpyxl')
        print("  ✅ Excel file created for inspection!")
        
        # Final summary
        print("\n" + "="*70)
        print("✅ BAGUA INSPECTIONS CLEANING COMPLETED SUCCESSFULLY!")
        print("="*70)
        
        print(f"\nOutput file: {OUTPUT_FILE}")
        print(f"Total records: {len(clean_data):,}")
        
        if GENERATE_FARMER_IDS:
            print(f"Unique farmers: {summary['unique_farmers_global']:,}")
        
        # Display column names
        print("\n" + "─"*70)
        print("OUTPUT COLUMNS")
        print("─"*70)
        print(f"Total columns: {len(clean_data.columns)}")
        
        # Group columns by type
        key_columns = ['nro_socio', 'dni', 'nombre_productor', 'ubicacion', 'base', 
                      'categoria', 'org_code', 'country_code']
        area_columns = [col for col in clean_data.columns if col.startswith('area_')]
        geo_columns = ['zona_utm', 'altitud', 'x_este', 'y_norte', 'latitud', 'longitud']
        harvest_columns = [col for col in clean_data.columns if 'cosecha_' in col or 'rendimiento_' in col]
        
        print("\nKey columns:")
        for col in key_columns:
            if col in clean_data.columns:
                print(f"  - {col}")
        
        print(f"\nArea columns ({len(area_columns)}):")
        for col in area_columns[:5]:
            print(f"  - {col}")
        if len(area_columns) > 5:
            print(f"  ... and {len(area_columns) - 5} more")
        
        print(f"\nGeolocation columns:")
        for col in geo_columns:
            if col in clean_data.columns:
                print(f"  - {col}")
        
        if GENERATE_FARMER_IDS:
            print(f"\nFarmer ID columns:")
            id_cols = ['nombre_estandarizado', 'dni_estandarizado', 'id_hoja', 
                      'id_global', 'producers_direct_id_productor']
            for col in id_cols:
                if col in clean_data.columns:
                    print(f"  - {col}")
        
        # Display first few rows
        print("\n" + "─"*70)
        print("SAMPLE DATA (first 3 rows)")
        print("─"*70)
        
        display_cols = ['nro_socio', 'nombre_productor', 'dni', 'categoria', 
                       'area_total_ha', 'area_cafe']
        if GENERATE_FARMER_IDS:
            display_cols.append('producers_direct_id_productor')
        
        available_cols = [col for col in display_cols if col in clean_data.columns]
        print(clean_data[available_cols].head(3).to_string(index=False))
        
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












