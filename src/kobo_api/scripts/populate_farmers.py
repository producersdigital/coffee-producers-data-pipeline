#!/usr/bin/env python3
"""
Populate farmers table from the mapping CSV.

Usage:
    python src/kobo_api/scripts/populate_farmers.py
"""

import csv
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import create_connection

CSV_PATH = project_root / "src/kobo_api/data_helpers/farmers_mapping.csv"

# Read CSV
to_insert = []
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['status'] == 'MISSING' and row['org_id'].strip() and row['farmer_name_from_kobo'].strip():
            to_insert.append({
                'national_id': row['national_id'].strip(),
                'farmer_name': row['farmer_name_from_kobo'].strip(),
                'org_id': int(row['org_id']),
                'telephone': row['telephone'].strip() if row['telephone'].strip() else None,
                'gender_id': int(row['gender_id']) if row['gender_id'].strip() else None,
                'birth_date': row['birth_date'].strip() if row['birth_date'].strip() else None,
            })

if not to_insert:
    print("Nothing to insert (org_id required)")
    sys.exit(0)

print(f"Inserting {len(to_insert)} farmers...")

# Insert into database
conn = create_connection()
cursor = conn.cursor()

for farmer in to_insert:
    cursor.execute(
        """INSERT INTO farmers (national_id, farmer_name, org_id, telephone, gender_id, birth_date)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (farmer['national_id'], farmer['farmer_name'], farmer['org_id'],
         farmer['telephone'], farmer['gender_id'], farmer['birth_date'])
    )

conn.commit()
cursor.close()
conn.close()

print(f"Done. Inserted {len(to_insert)} farmers")
