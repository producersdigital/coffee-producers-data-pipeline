import pandas as pd
import numpy as np

# Load both files
nb = pd.read_pickle('data/processed/inspections/aprocassi/clean_aprocassi_LPA.pkl')
cl = pd.read_pickle('data/processed/inspections/aprocassi/aprocassi_inspections_clean.pkl')

# Sort both the same way
nb = nb.sort_values(['producers_direct_id_productor', 'categoria']).reset_index(drop=True)
cl = cl.sort_values(['producers_direct_id_productor', 'categoria']).reset_index(drop=True)

# Compare first 5 longitude values
print("Notebook longitude (first 5):")
print(nb['longitud'].head(5))

print("\nCleaner longitude (first 5):")
print(cl['longitud'].head(5))

print("\nDifference (first 5):")
print((nb['longitud'].head(5) - cl['longitud'].head(5)))

# Check data types
print(f"\nNotebook longitud dtype: {nb['longitud'].dtype}")
print(f"Cleaner longitud dtype: {cl['longitud'].dtype}")