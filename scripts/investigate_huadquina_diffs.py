"""
Investigate Huadquiña Inspections Differences
"""

import pandas as pd
import numpy as np

# Load files
notebook = pd.read_pickle('data/processed/inspections/huadquina/new_clean_huadquiña_template_LPA.pkl')
cleaner = pd.read_pickle('data/processed/inspections/huadquina/huadquina_inspections_clean.pkl')

# Sort both
notebook = notebook.sort_values(['dni', 'nombre_productor']).reset_index(drop=True)
cleaner = cleaner.sort_values(['dni', 'nombre_productor']).reset_index(drop=True)

# Find differences in DNI
dni_diff = notebook['dni'] != cleaner['dni']
if dni_diff.any():
    print(f"Rows with different DNI: {dni_diff.sum()}")
    print("\nNotebook DNIs:")
    print(notebook.loc[dni_diff, ['dni', 'nombre_productor', 'categoria', 'area_total_ha']])
    print("\nCleaner DNIs:")
    print(cleaner.loc[dni_diff, ['dni', 'nombre_productor', 'categoria', 'area_total_ha']])

# Find differences in nombre_productor
name_diff = notebook['nombre_productor'] != cleaner['nombre_productor']
if name_diff.any():
    print(f"\n\nRows with different nombre_productor: {name_diff.sum()}")
    print("\nNotebook names:")
    print(notebook.loc[name_diff, ['dni', 'nombre_productor']])
    print("\nCleaner names:")
    print(cleaner.loc[name_diff, ['dni', 'nombre_productor']])

# Find differences in categoria
cat_diff = notebook['categoria'] != cleaner['categoria']
if cat_diff.any():
    print(f"\n\nRows with different categoria: {cat_diff.sum()}")
    print("\nNotebook:")
    print(notebook.loc[cat_diff, ['dni', 'nombre_productor', 'categoria']])
    print("\nCleaner:")
    print(cleaner.loc[cat_diff, ['dni', 'nombre_productor', 'categoria']])

# Find differences in area_total_ha
area_diff = ~np.isclose(notebook['area_total_ha'], cleaner['area_total_ha'], rtol=1e-5, equal_nan=True)
if area_diff.any():
    print(f"\n\nRows with different area_total_ha: {area_diff.sum()}")
    print("\nNotebook:")
    print(notebook.loc[area_diff, ['dni', 'nombre_productor', 'area_total_ha']])
    print("\nCleaner:")
    print(cleaner.loc[area_diff, ['dni', 'nombre_productor', 'area_total_ha']])