#!/usr/bin/env python3
"""
Populate extensionists table from the mapping CSV.

Usage:
    python src/kobo_api/scripts/populate_extensionists.py
"""

import csv
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import create_connection

CSV_PATH = project_root / "src/kobo_api/data_helpers/extensionists_mapping.csv"

# Read CSV
to_insert = []
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['status'] == 'MISSING' and row['extensionist_name'].strip():
            to_insert.append({
                'code': row['extensionist_code'],
                'name': row['extensionist_name'].strip(),
                'org_id': int(row['org_id'])
            })

if not to_insert:
    print("Nothing to insert")
    sys.exit(0)

print(f"Inserting {len(to_insert)} extensionists...")

# Insert into database
conn = create_connection()
cursor = conn.cursor()

for ext in to_insert:
    cursor.execute(
        "INSERT INTO extensionists (extensionist_code, extensionist_name, org_id, is_active) VALUES (%s, %s, %s, 1)",
        (ext['code'], ext['name'], ext['org_id'])
    )

conn.commit()
cursor.close()
conn.close()

print(f"Done. Inserted {len(to_insert)} extensionists")
