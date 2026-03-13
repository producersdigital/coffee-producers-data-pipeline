"""
Compare Chirinos Inspections Outputs

Compares the cleaner output with the notebook output (2024 file only for now).

Usage:
    python scripts/compare_chirinos_inspections.py
"""

import pandas as pd
import numpy as np


def main():
    """Compare the two pickle files"""
    
    print("\n" + "="*70)
    print("COMPARING CHIRINOS INSPECTIONS OUTPUTS")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Your notebook's 2024 inspection output (if exists)
    # UPDATE THIS PATH based on your actual notebook output
    NOTEBOOK_FILE = 'data/processed/inspections/chirinos/chirinos_2024_inspections_clean.pkl'
    
    # Cleaner's inspection output  
    CLEANER_FILE = 'data/processed/inspections/chirinos/chirinos_inspections_clean.pkl'
    
    # ========================================================================
    # LOAD FILES
    # ========================================================================
    
    print("\nLoading files...")
    
    try:
        print(f"  Notebook: {NOTEBOOK_FILE}")
        df_notebook = pd.read_pickle(NOTEBOOK_FILE)
        print(f"    ✅ Loaded: {df_notebook.shape}")
    except FileNotFoundError:
        print(f"    ⚠️  File not found! Skipping notebook comparison.")
        print(f"    (This is expected if you don't have a notebook output yet)")
        df_notebook = None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        df_notebook = None
    
    try:
        print(f"  Cleaner: {CLEANER_FILE}")
        df_cleaner = pd.read_pickle(CLEANER_FILE)
        print(f"    ✅ Loaded: {df_cleaner.shape}")
    except FileNotFoundError:
        print(f"    ❌ File not found! Run the cleaner first.")
        return
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return
    
    # ========================================================================
    # CLEANER-ONLY SUMMARY (Always show this)
    # ========================================================================
    
    print("\n" + "-"*70)
    print("CLEANER OUTPUT SUMMARY")
    print("-"*70)
    
    print(f"\nShape: {df_cleaner.shape}")
    print(f"Columns: {len(df_cleaner.columns)}")
    
    if 'inspeccion_year' in df_cleaner.columns:
        print(f"\nInspections by year:")
        for year, count in df_cleaner['inspeccion_year'].value_counts().sort_index().items():
            print(f"  {year}: {count:,}")
    
    if 'pd_farmer_id' in df_cleaner.columns:
        print(f"\nUnique farmers: {df_cleaner['pd_farmer_id'].nunique()}")
    
    print(f"\nSample rows (first 3):")
    display_cols = [c for c in ['pd_farmer_id', 'nombre_productor', 'dni', 
                                 'base', 'area_cafe', 'inspeccion_year'] 
                    if c in df_cleaner.columns]
    if display_cols:
        print(df_cleaner[display_cols].head(3).to_string(index=False))
    
    # ========================================================================
    # COMPARISON (Only if notebook file exists)
    # ========================================================================
    
    if df_notebook is None:
        print("\n" + "="*70)
        print("✅ CLEANER COMPLETED SUCCESSFULLY")
        print("   (No notebook output to compare against)")
        print("="*70 + "\n")
        return
    
    print("\n" + "-"*70)
    print("COMPARISON WITH NOTEBOOK (2024 ONLY)")
    print("-"*70)
    
    # Filter cleaner to 2024 only for fair comparison
    if 'inspeccion_year' in df_cleaner.columns:
        df_cleaner_2024 = df_cleaner[df_cleaner['inspeccion_year'] == 2024].copy()
        print(f"\nFiltered cleaner to 2024: {len(df_cleaner_2024)} rows")
    else:
        df_cleaner_2024 = df_cleaner.copy()
    
    # 1. Shape
    print("\n1. SHAPE:")
    print(f"   Notebook: {df_notebook.shape}")
    print(f"   Cleaner:  {df_cleaner_2024.shape}")
    if df_notebook.shape == df_cleaner_2024.shape:
        print("   ✅ MATCH")
    else:
        print("   ⚠️  DIFFERENT")
    
    # 2. Columns
    print("\n2. COLUMNS:")
    cols_notebook = set(df_notebook.columns)
    cols_cleaner = set(df_cleaner_2024.columns)
    
    common = cols_notebook & cols_cleaner
    only_notebook = cols_notebook - cols_cleaner
    only_cleaner = cols_cleaner - cols_notebook
    
    if cols_notebook == cols_cleaner:
        print(f"   ✅ All {len(cols_notebook)} columns match")
    else:
        print(f"   Common columns: {len(common)}")
        if only_notebook:
            print(f"   ⚠️  Only in notebook: {sorted(only_notebook)}")
        if only_cleaner:
            print(f"   ⚠️  Only in cleaner: {sorted(only_cleaner)}")
    
    # 3. Key columns check
    print("\n3. KEY COLUMNS:")
    
    key_cols = ['dni', 'nombre_productor', 'area_total_ha', 'area_cafe', 
                'latitud', 'longitud']
    
    for col in key_cols:
        if col not in common:
            if col not in df_notebook.columns:
                print(f"   ⚠️  {col} - missing in notebook")
            elif col not in df_cleaner_2024.columns:
                print(f"   ⚠️  {col} - missing in cleaner")
            continue
        
        # Check if BOTH are numeric
        nb_numeric = pd.api.types.is_numeric_dtype(df_notebook[col])
        cl_numeric = pd.api.types.is_numeric_dtype(df_cleaner_2024[col])
        
        if nb_numeric and cl_numeric:
            matches = np.isclose(
                df_notebook[col].fillna(0),
                df_cleaner_2024[col].fillna(0),
                rtol=1e-5,
                atol=1e-8,
                equal_nan=True
            ).all()
        else:
            matches = (df_notebook[col].astype(str).fillna('') == 
                      df_cleaner_2024[col].astype(str).fillna('')).all()
        
        if matches:
            print(f"   ✅ {col}")
        else:
            # Count differences
            if nb_numeric and cl_numeric:
                diff_count = (~np.isclose(
                    df_notebook[col].fillna(0),
                    df_cleaner_2024[col].fillna(0),
                    rtol=1e-5,
                    atol=1e-8,
                    equal_nan=True
                )).sum()
            else:
                diff_count = (df_notebook[col].astype(str).fillna('') != 
                             df_cleaner_2024[col].astype(str).fillna('')).sum()
            
            print(f"   ⚠️  {col} - {diff_count} rows differ")
    
    # Final verdict
    print("\n" + "="*70)
    
    if (len(df_notebook) == len(df_cleaner_2024) and 
        len(cols_notebook) == len(cols_cleaner)):
        print("✅ BASIC STRUCTURE MATCHES!")
        if only_notebook or only_cleaner:
            print("   (Some column differences exist - review above)")
    else:
        print("⚠️  SOME DIFFERENCES FOUND")
        print("   Review the details above.")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    main()