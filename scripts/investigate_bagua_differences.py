"""
Investigate Bagua Transaction Differences

Shows EXACTLY which rows differ and WHY.

Usage:
    python scripts/investigate_bagua_differences.py
"""

import pandas as pd
import numpy as np


def main():
    """Investigate specific differences between notebook and cleaner"""
    
    print("\n" + "="*70)
    print("INVESTIGATING BAGUA TRANSACTION DIFFERENCES")
    print("="*70)
    
    # Load files
    notebook = pd.read_pickle('data/processed/transactions/bagua/integrated_bagua_acopio.pkl')
    cleaner = pd.read_pickle('data/processed/transactions/bagua/bagua_transactions_NEW.pkl')
    
    print(f"\nNotebook shape: {notebook.shape}")
    print(f"Cleaner shape:  {cleaner.shape}")
    
    # Sort both identically for comparison
    sort_cols = ['fecha', 'nombre_productor', 'kg']
    notebook_sorted = notebook.sort_values(sort_cols, kind='stable').reset_index(drop=True)
    cleaner_sorted = cleaner.sort_values(sort_cols, kind='stable').reset_index(drop=True)
    
    print(f"\nSorted and ready to compare...")
    
    # ========================================================================
    # INVESTIGATE FECHA DIFFERENCES
    # ========================================================================
    
    print("\n" + "="*70)
    print("1. FECHA DIFFERENCES (7 rows)")
    print("="*70)
    
    # Convert both to datetime for comparison
    nb_fecha = pd.to_datetime(notebook_sorted['fecha'], errors='coerce')
    cl_fecha = pd.to_datetime(cleaner_sorted['fecha'], errors='coerce')
    
    # Find differences
    fecha_diff = nb_fecha != cl_fecha
    
    if fecha_diff.any():
        print(f"\nFound {fecha_diff.sum()} rows with different fecha:")
        
        diff_rows = notebook_sorted[fecha_diff].index[:10]  # First 10
        
        print("\nNotebook:")
        print(notebook_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'kg', 'campania']])
        
        print("\nCleaner:")
        print(cleaner_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'kg', 'campania']])
        
        # Check if it's NaT vs valid date
        nb_nat = nb_fecha[fecha_diff].isna()
        cl_nat = cl_fecha[fecha_diff].isna()
        
        if nb_nat.any() or cl_nat.any():
            print(f"\n  Analysis:")
            print(f"    Notebook has NaT: {nb_nat.sum()}")
            print(f"    Cleaner has NaT:  {cl_nat.sum()}")
    
    # ========================================================================
    # INVESTIGATE CAMPANIA DIFFERENCES
    # ========================================================================
    
    print("\n" + "="*70)
    print("2. CAMPANIA DIFFERENCES (2 rows)")
    print("="*70)
    
    # Compare as strings
    campania_diff = (notebook_sorted['campania'].astype(str) != 
                     cleaner_sorted['campania'].astype(str))
    
    if campania_diff.any():
        print(f"\nFound {campania_diff.sum()} rows with different campania:")
        
        diff_rows = notebook_sorted[campania_diff].index
        
        print("\nNotebook:")
        print(notebook_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'campania', 'kg']])
        print(f"\nNotebook campania types: {notebook_sorted.loc[diff_rows, 'campania'].apply(type).unique()}")
        print(f"Notebook campania values: {notebook_sorted.loc[diff_rows, 'campania'].tolist()}")
        
        print("\nCleaner:")
        print(cleaner_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'campania', 'kg']])
        print(f"\nCleaner campania types: {cleaner_sorted.loc[diff_rows, 'campania'].apply(type).unique()}")
        print(f"Cleaner campania values: {cleaner_sorted.loc[diff_rows, 'campania'].tolist()}")
    
    # ========================================================================
    # INVESTIGATE NOMBRE_PRODUCTOR DIFFERENCES
    # ========================================================================
    
    print("\n" + "="*70)
    print("3. NOMBRE_PRODUCTOR DIFFERENCES (4 rows)")
    print("="*70)
    
    nombre_diff = (notebook_sorted['nombre_productor'].fillna('') != 
                   cleaner_sorted['nombre_productor'].fillna(''))
    
    if nombre_diff.any():
        print(f"\nFound {nombre_diff.sum()} rows with different nombre_productor:")
        
        diff_rows = notebook_sorted[nombre_diff].index
        
        print("\nNotebook:")
        for idx in diff_rows:
            nb_name = notebook_sorted.loc[idx, 'nombre_productor']
            print(f"  Row {idx}: '{nb_name}' (len={len(str(nb_name))})")
        
        print("\nCleaner:")
        for idx in diff_rows:
            cl_name = cleaner_sorted.loc[idx, 'nombre_productor']
            print(f"  Row {idx}: '{cl_name}' (len={len(str(cl_name))})")
        
        # Show full context
        print("\nFull context:")
        print("\nNotebook:")
        print(notebook_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'kg', 'campania']])
        print("\nCleaner:")
        print(cleaner_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'kg', 'campania']])
    
    # ========================================================================
    # INVESTIGATE KG DIFFERENCES
    # ========================================================================
    
    print("\n" + "="*70)
    print("4. KG DIFFERENCES (4 rows)")
    print("="*70)
    
    kg_diff = ~np.isclose(
        notebook_sorted['kg'].fillna(0),
        cleaner_sorted['kg'].fillna(0),
        rtol=1e-5,
        atol=1e-8,
        equal_nan=True
    )
    
    if kg_diff.any():
        print(f"\nFound {kg_diff.sum()} rows with different kg:")
        
        diff_rows = notebook_sorted[kg_diff].index
        
        print("\nNotebook:")
        print(notebook_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'kg', 'campania']])
        
        print("\nCleaner:")
        print(cleaner_sorted.loc[diff_rows, ['fecha', 'nombre_productor', 'kg', 'campania']])
        
        # Show the actual difference
        print("\nDifference magnitude:")
        for idx in diff_rows:
            nb_kg = notebook_sorted.loc[idx, 'kg']
            cl_kg = cleaner_sorted.loc[idx, 'kg']
            diff = nb_kg - cl_kg if pd.notna(nb_kg) and pd.notna(cl_kg) else 'NaN difference'
            print(f"  Row {idx}: {nb_kg} - {cl_kg} = {diff}")
    
    # ========================================================================
    # CHECK IF THESE ARE THE SAME ROWS
    # ========================================================================
    
    print("\n" + "="*70)
    print("5. OVERLAP ANALYSIS")
    print("="*70)
    
    # Check if the rows with differences overlap
    all_diff_rows = set()
    
    if fecha_diff.any():
        all_diff_rows.update(notebook_sorted[fecha_diff].index)
    if campania_diff.any():
        all_diff_rows.update(notebook_sorted[campania_diff].index)
    if nombre_diff.any():
        all_diff_rows.update(notebook_sorted[nombre_diff].index)
    if kg_diff.any():
        all_diff_rows.update(notebook_sorted[kg_diff].index)
    
    print(f"\nTotal unique rows with ANY difference: {len(all_diff_rows)}")
    print(f"  fecha differences: {fecha_diff.sum()}")
    print(f"  campania differences: {campania_diff.sum()}")
    print(f"  nombre_productor differences: {nombre_diff.sum()}")
    print(f"  kg differences: {kg_diff.sum()}")
    
    if len(all_diff_rows) < (fecha_diff.sum() + campania_diff.sum() + 
                             nombre_diff.sum() + kg_diff.sum()):
        print("\n⚠️  OVERLAPPING DIFFERENCES DETECTED!")
        print("The same rows have multiple column differences.")
        print("This suggests a systematic issue (like sorting or row matching).")
    else:
        print("\n✅ INDEPENDENT DIFFERENCES")
        print("Each difference is in a different row.")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print("\nSmall differences found:")
    print(f"  - fecha: {fecha_diff.sum()} rows")
    print(f"  - campania: {campania_diff.sum()} rows")
    print(f"  - nombre_productor: {nombre_diff.sum()} rows")
    print(f"  - kg: {kg_diff.sum()} rows")
    print(f"\nTotal unique affected rows: {len(all_diff_rows)}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()