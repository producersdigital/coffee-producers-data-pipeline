"""
Compare Aprocassi Transactions Outputs
 
Compares the cleaner output with the notebook output.
 
Usage:
    python scripts/compare_aprocassi_transactions.py
"""
 
import pandas as pd
import numpy as np
 
 
def main():
    """Compare the two pickle files"""
    
    print("\n" + "="*70)
    print("COMPARING APROCASSI TRANSACTIONS OUTPUTS")
    print("="*70)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Your notebook's transaction output
    NOTEBOOK_FILE = 'data/processed/transactions/aprocassi/integrated_aprocassi_acopio.pkl'
    
    # Cleaner's transaction output  
    CLEANER_FILE = 'data/processed/transactions/aprocassi/aprocassi_transactions_clean.pkl'
    
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
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return
    
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
    
    # 3. Sort both for comparison
    sort_cols = [c for c in ['fecha', 'nombre_productor', 'kg'] if c in common]
    
    if sort_cols:
        df_n = df_notebook.sort_values(sort_cols, kind='stable').reset_index(drop=True)
        df_c = df_cleaner.sort_values(sort_cols, kind='stable').reset_index(drop=True)
    else:
        df_n = df_notebook.reset_index(drop=True)
        df_c = df_cleaner.reset_index(drop=True)
    
    # 4. Check key columns
    print("\n3. KEY COLUMNS:")
    
    key_cols = ['fecha', 'campania', 'nombre_productor', 'kg', 'qq', 
                'categoria', 'org_code', 'total_soles']
    
    for col in key_cols:
        if col not in common:
            if col not in df_n.columns:
                print(f"   ⚠️  {col} - missing in notebook")
            elif col not in df_c.columns:
                print(f"   ⚠️  {col} - missing in cleaner")
            continue
        
        # Check if BOTH are numeric (not just one!)
        nb_numeric = pd.api.types.is_numeric_dtype(df_n[col])
        cl_numeric = pd.api.types.is_numeric_dtype(df_c[col])
        
        if nb_numeric and cl_numeric:
            # Both numeric: use np.isclose
            matches = np.isclose(
                df_n[col].fillna(0),
                df_c[col].fillna(0),
                rtol=1e-5,
                atol=1e-8,
                equal_nan=True
            ).all()
        else:
            # At least one is not numeric: convert both to string
            matches = (df_n[col].astype(str).fillna('') == 
                      df_c[col].astype(str).fillna('')).all()
        
        if matches:
            print(f"   ✅ {col}")
        else:
            # Count differences
            if nb_numeric and cl_numeric:
                diff_count = (~np.isclose(
                    df_n[col].fillna(0),
                    df_c[col].fillna(0),
                    rtol=1e-5,
                    atol=1e-8,
                    equal_nan=True
                )).sum()
            else:
                diff_count = (df_n[col].astype(str).fillna('') != 
                             df_c[col].astype(str).fillna('')).sum()
            
            print(f"   ❌ {col} - {diff_count} rows differ")
    
    # 5. Summary stats
    print("\n4. SUMMARY STATISTICS:")
    
    if 'campania' in common:
        print("\n   Transactions by campaign:")
        print("   Notebook:")
        for camp, count in df_notebook['campania'].astype(str).value_counts().sort_index().items():
            print(f"     {camp}: {count:,}")
        
        print("   Cleaner:")
        for camp, count in df_cleaner['campania'].astype(str).value_counts().sort_index().items():
            print(f"     {camp}: {count:,}")
    
    if 'fecha' in common:
        print("\n   Date range:")
        try:
            nb_dates = pd.to_datetime(df_notebook['fecha'], errors='coerce').dropna()
            cl_dates = pd.to_datetime(df_cleaner['fecha'], errors='coerce').dropna()
            if len(nb_dates) > 0:
                print(f"     Notebook: {nb_dates.min()} to {nb_dates.max()}")
            if len(cl_dates) > 0:
                print(f"     Cleaner:  {cl_dates.min()} to {cl_dates.max()}")
        except Exception as e:
            print(f"     ⚠️  Could not compare date ranges: {e}")
    
    if 'kg' in common:
        print("\n   Total KG:")
        print(f"     Notebook: {df_notebook['kg'].sum():,.2f}")
        print(f"     Cleaner:  {df_cleaner['kg'].sum():,.2f}")
    
    # 6. Sample comparison
    print("\n5. SAMPLE ROWS (first 3):")
    
    display_cols = [c for c in ['fecha', 'campania', 'nombre_productor', 
                                 'kg', 'categoria'] 
                    if c in common]
    
    if display_cols:
        print("\n   Notebook:")
        print(df_notebook[display_cols].head(3).to_string(index=False))
        
        print("\n   Cleaner:")
        print(df_cleaner[display_cols].head(3).to_string(index=False))
    
    # Final verdict
    print("\n" + "="*70)
    
    if (len(df_notebook) == len(df_cleaner) and 
        len(cols_notebook) == len(cols_cleaner)):
        print("✅ OUTPUTS MATCH!")
    else:
        print("⚠️  SOME DIFFERENCES FOUND")
        print("Review the details above.")
    
    print("="*70 + "\n")
 
 
if __name__ == "__main__":
    main()
 