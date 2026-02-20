"""
Compare Bagua transaction outputs
"""

import pandas as pd
import numpy as np

# Your notebook's transaction output
NOTEBOOK_FILE = 'data/processed/transactions/bagua/integrated_bagua_acopio.pkl'

# Cleaner's transaction output  
CLEANER_FILE = 'data/processed/transactions/bagua/bagua_transactions_NEW.pkl'

print("\nComparing Bagua Transactions...")

notebook = pd.read_pickle(NOTEBOOK_FILE)
cleaner = pd.read_pickle(CLEANER_FILE)

print(f"\nNotebook: {notebook.shape}")
print(f"Cleaner: {cleaner.shape}")

if notebook.shape == cleaner.shape:
    print("✅ Shapes match!")
else:
    print("❌ Shapes differ!")
    
    # Show which columns are different
    print("\n🔍 Column Comparison:")
    notebook_cols = set(notebook.columns)
    cleaner_cols = set(cleaner.columns)
    
    only_in_notebook = notebook_cols - cleaner_cols
    only_in_cleaner = cleaner_cols - notebook_cols
    common = notebook_cols & cleaner_cols
    
    print(f"  Common columns: {len(common)}")
    
    if only_in_notebook:
        print(f"  ⚠️  Only in notebook: {sorted(only_in_notebook)}")
    
    if only_in_cleaner:
        print(f"  ⚠️  Only in cleaner: {sorted(only_in_cleaner)}")
    
    print("\n  All notebook columns:")
    for col in sorted(notebook.columns):
        print(f"    - {col}")
    
    print("\n  All cleaner columns:")
    for col in sorted(cleaner.columns):
        print(f"    - {col}")

# Check key columns
key_cols = ['dni', 'nombre_productor', 'campania', 'kg', 'org_code']

for col in key_cols:
    if col in notebook.columns and col in cleaner.columns:
        matches = (notebook[col].fillna('') == cleaner[col].fillna('')).all()
        if matches:
            print(f"✅ {col}")
        else:
            print(f"❌ {col} differs")