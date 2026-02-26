"""
Check raw data for MAINICTA NINA ANAMELBA
"""

import pandas as pd

# Load raw data
raw = pd.read_excel('data/raw/inspections/huadquina/Plantilla de Inspecciones vf.xlsx', 
                    sheet_name='Hoja1', 
                    header=0)

# Find this farmer
mask = raw['nombre_productor'].str.contains('MAINICTA', case=False, na=False)

if mask.any():
    print("Found MAINICTA in raw data:")
    print("\nRaw DNI value:")
    print(raw.loc[mask, ['nombre_productor', 'dni']])
    print("\nDNI type:", type(raw.loc[mask, 'dni'].iloc[0]))
    print("DNI value:", repr(raw.loc[mask, 'dni'].iloc[0]))
else:
    print("MAINICTA not found in raw data")

# Also check notebook output
notebook = pd.read_pickle('data/processed/inspections/huadquina/new_clean_huadquiña_template_LPA.pkl')
mask_nb = notebook['nombre_productor'].str.contains('MAINICTA', case=False, na=False)

if mask_nb.any():
    print("\n\nFound MAINICTA in notebook output:")
    print(notebook.loc[mask_nb, ['nombre_productor', 'dni', 'dni_estandarizado']])

# Check cleaner output
cleaner = pd.read_pickle('data/processed/inspections/huadquina/huadquina_inspections_clean.pkl')
mask_cl = cleaner['nombre_productor'].str.contains('MAINICTA', case=False, na=False)

if mask_cl.any():
    print("\n\nFound MAINICTA in cleaner output:")
    print(cleaner.loc[mask_cl, ['nombre_productor', 'dni', 'dni_estandarizado']])
























