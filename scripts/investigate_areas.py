"""
Investigate area_total_ha differences
"""

import pandas as pd
import numpy as np

notebook = pd.read_pickle('data/processed/inspections/bagua/clean_bagua_LPA.pkl')
cleaner = pd.read_pickle('data/processed/inspections/bagua/clean_bagua_LPA_NEW.pkl')

# Sort both
notebook = notebook.sort_values(['nro_socio', 'categoria']).reset_index(drop=True)
cleaner = cleaner.sort_values(['nro_socio', 'categoria']).reset_index(drop=True)

# Find differences
mask = ~np.isclose(
    notebook['area_total_ha'].fillna(0),
    cleaner['area_total_ha'].fillna(0),
    rtol=1e-5,
    atol=1e-8
)

print(f"Rows with different area_total_ha: {mask.sum()}")
print("\nNotebook values:")
print(notebook.loc[mask, ['nro_socio', 'nombre_productor', 'categoria', 'area_total_ha']])
print("\nCleaner values:")
print(cleaner.loc[mask, ['nro_socio', 'nombre_productor', 'categoria', 'area_total_ha']])