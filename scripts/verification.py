import pandas as pd
from pathlib import Path

# --- read the 51 unique DNIs straight from the Visits unmatched log ---
unmatched = pd.read_csv(
    'src/kobo_api/logs/import_20260826_102838/unmatched_farmers.csv',
    dtype=str
)
missing = sorted(unmatched['dni'].dropna().str.strip().unique())
missing = [d for d in missing if d not in ('', 'nan')]   # drop blank-DNI rows
print(f"unique unmatched DNIs from log: {len(missing)}")

# --- check them against the freshly rebuilt farmers_data.csv ---
fd = pd.read_csv('data/mysql_ready/master/farmers_data.csv', dtype=str)
fd['national_id'] = fd['national_id'].str.strip()

present = fd[fd['national_id'].isin(missing)]
print(f"farmers_data.csv rows: {len(fd):,}")
print(f"of {len(missing)} target DNIs, found {len(present)} in farmers_data.csv")
print(present[['national_id','farmer_name','org_code','member_status']].to_string(index=False))

not_found = sorted(set(missing) - set(present['national_id']))
if not_found:
    print("\nSTILL MISSING (investigate before loading):", not_found)
else:
    print("\n✅ all target DNIs present — safe to load")