"""
Compare Cleaner Output to Notebook Output

Compares the output from the cleaner with your notebook's output.

Usage:
    python scripts/compare_bagua_outputs.py
"""

import pandas as pd
import numpy as np


def main():
    """Compare the two pickle files"""
    
    print("\n" + "="*70)
    print("COMPARING BAGUA OUTPUTS")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION - Update if your paths differ
    # ========================================================================
    
    # Your notebook's original output
    NOTEBOOK_FILE = 'data/processed/inspections/bagua/clean_bagua_LPA.pkl'
    
    # The cleaner's new output
    CLEANER_FILE = 'data/processed/inspections/bagua/clean_bagua_LPA_NEW.pkl'
    
    # ========================================================================
    # LOAD FILES
    # ========================================================================
    
    print("\nLoading files...")
    
    try:
        print(f"  Notebook: {NOTEBOOK_FILE}")
        df_notebook = pd.read_pickle(NOTEBOOK_FILE)
        print(f"    ✅ Loaded: {df_notebook.shape}")
    except FileNotFoundError:
        print(f"    ❌ File not found!")
        return
    
    try:
        print(f"  Cleaner: {CLEANER_FILE}")
        df_cleaner = pd.read_pickle(CLEANER_FILE)
        print(f"    ✅ Loaded: {df_cleaner.shape}")
    except FileNotFoundError:
        print(f"    ❌ File not found! Run the cleaner first.")
        return
    
    # ========================================================================
    # COMPARE
    # ========================================================================
    
    print("\n" + "-"*70)
    print("COMPARISON RESULTS")
    print("-"*70)
    
    # 1. Shape
    print("\n1. SHAPE:")
    print(f"   Notebook: {df_notebook.shape}")
    print(f"   Cleaner:  {df_cleaner.shape}")
    if df_notebook.shape == df_cleaner.shape:
        print("   ✅ MATCH")
    else:
        print("   ❌ DIFFERENT")
    
    # 2. Columns
    print("\n2. COLUMNS:")
    cols_notebook = set(df_notebook.columns)
    cols_cleaner = set(df_cleaner.columns)
    
    if cols_notebook == cols_cleaner:
        print(f"   ✅ All {len(cols_notebook)} columns match")
    else:
        only_notebook = cols_notebook - cols_cleaner
        only_cleaner = cols_cleaner - cols_notebook
        
        if only_notebook:
            print(f"   ⚠️  Only in notebook: {only_notebook}")
        if only_cleaner:
            print(f"   ⚠️  Only in cleaner: {only_cleaner}")
    
    # 3. Sort both for comparison
    common_cols = cols_notebook & cols_cleaner
    sort_cols = [c for c in ['nro_socio', 'categoria'] if c in common_cols]
    
    if sort_cols:
        df_n = df_notebook.sort_values(sort_cols).reset_index(drop=True)
        df_c = df_cleaner.sort_values(sort_cols).reset_index(drop=True)
    else:
        df_n = df_notebook.reset_index(drop=True)
        df_c = df_cleaner.reset_index(drop=True)
    
    # 4. Check key columns
    print("\n3. KEY COLUMNS:")
    
    key_cols = ['dni', 'nombre_productor', 'categoria', 'area_total_ha', 'org_code']
    
    for col in key_cols:
        if col not in common_cols:
            continue
        
        # Check if values match
        if pd.api.types.is_numeric_dtype(df_n[col]):
            # Numeric: allow tiny differences
            matches = np.isclose(
                df_n[col].fillna(0),
                df_c[col].fillna(0),
                rtol=1e-5,
                atol=1e-8,
                equal_nan=True
            ).all()
        else:
            # Non-numeric: exact match
            matches = (df_n[col].fillna('') == df_c[col].fillna('')).all()
        
        if matches:
            print(f"   ✅ {col}")
        else:
            # Count differences
            if pd.api.types.is_numeric_dtype(df_n[col]):
                diff_count = (~np.isclose(
                    df_n[col].fillna(0),
                    df_c[col].fillna(0),
                    rtol=1e-5,
                    atol=1e-8,
                    equal_nan=True
                )).sum()
            else:
                diff_count = (df_n[col].fillna('') != df_c[col].fillna('')).sum()
            
            print(f"   ❌ {col} - {diff_count} rows differ")
    
    # 5. Summary stats
    print("\n4. SUMMARY STATISTICS:")
    
    if 'categoria' in common_cols:
        print("\n   Counts by categoria:")
        print("   Notebook:")
        for cat, count in df_notebook['categoria'].value_counts().sort_index().items():
            print(f"     {cat}: {count}")
        
        print("   Cleaner:")
        for cat, count in df_cleaner['categoria'].value_counts().sort_index().items():
            print(f"     {cat}: {count}")
    
    if 'dni' in common_cols:
        print("\n   Unique DNIs:")
        print(f"     Notebook: {df_notebook['dni'].nunique()}")
        print(f"     Cleaner:  {df_cleaner['dni'].nunique()}")
    
    # 6. Sample comparison
    print("\n5. SAMPLE ROWS (first 3):")
    
    display_cols = [c for c in ['nro_socio', 'dni', 'nombre_productor', 'categoria', 'area_total_ha'] if c in common_cols]
    
    print("\n   Notebook:")
    print(df_notebook[display_cols].head(3).to_string(index=False))
    
    print("\n   Cleaner:")
    print(df_cleaner[display_cols].head(3).to_string(index=False))
    
    # Final verdict
    print("\n" + "="*70)
    
    if (df_notebook.shape == df_cleaner.shape and 
        cols_notebook == cols_cleaner and
        all((df_n[col].fillna('') == df_c[col].fillna('')).all() 
            for col in key_cols if col in common_cols and not pd.api.types.is_numeric_dtype(df_n[col]))):
        print("✅ OUTPUTS MATCH!")
    else:
        print("⚠️  SOME DIFFERENCES FOUND")
        print("Review the details above.")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    main()