import pandas as pd
df = pd.read_csv('src/kobo_api/logs/import_20260518_064408/unmatched_farmers.csv')
unique = df[['dni','producer_name_from_kobo']].drop_duplicates('dni').dropna(subset=['producer_name_from_kobo'])
unique['dni_clean'] = unique['dni'].astype(str).str.replace('.0','',regex=False).str.zfill(8)
unique = unique[['dni_clean','producer_name_from_kobo']].rename(columns={'dni_clean':'DNI','producer_name_from_kobo':'Nombre'})
unique.to_excel('data/exports/norandino_farmers_not_in_sdl.xlsx', index=False)
print(f'Exported {len(unique)} farmers')
print(unique.to_string())