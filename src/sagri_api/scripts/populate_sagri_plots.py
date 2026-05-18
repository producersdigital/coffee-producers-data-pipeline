"""
Populate SAGRI Plots Table
==========================
Reads sagri_codes.xlsx and upserts all 2,695 plot records into sagri_plots.
 
For each row:
  - If plot_code already exists → UPDATE national_id, selected_crop, plot_name, farmer_id
  - If plot_code is new         → INSERT with region derived from code prefix
  - farmer_id looked up from farmers table via national_id
 
Region is derived from the plot_code prefix:
  NORCAJ → NORCAJ (Cajamarca)
  NORLAM → NORLAM (Lambayeque)
  NORPIU → NORPIU (Piura)
 
Usage:
    python scripts/populate_sagri_plots.py           # preview only
    python scripts/populate_sagri_plots.py --apply   # apply to DB
"""
 
import sys
import argparse
import pandas as pd
from pathlib import Path
 
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
 
from src.database.connection import create_connection
 
EXCEL_PATH  = project_root / 'data' / 'raw' / 'sagri' / 'sagri_codes.xlsx'
SHEET_NAME  = 'Sheet1'
 
 
def _norm_id(val) -> str:
    """Normalise national_id to 8-digit zero-padded string."""
    if pd.isna(val) or str(val).strip() in ('', 'nan'):
        return ''
    return str(val).strip().replace('.0', '').zfill(8)
 
 
def _derive_region(plot_code: str) -> str:
    """Extract region prefix from plot code e.g. NORCAJ2338 → NORCAJ."""
    if not plot_code:
        return ''
    for prefix in ['NORCAJ', 'NORLAM', 'NORPIU']:
        if plot_code.upper().startswith(prefix):
            return prefix
    return plot_code[:6].upper()
 
 
def main(apply: bool = False):
    print("=" * 60)
    print("POPULATE SAGRI PLOTS")
    print("=" * 60)
    print(f"  Mode: {'APPLY (will update DB)' if apply else 'PREVIEW (no DB changes)'}")
 
    # ── Load Excel ────────────────────────────────────────────────────────────
    print(f"\n1. Loading {EXCEL_PATH.name}...")
    if not EXCEL_PATH.exists():
        print(f"  ❌ File not found: {EXCEL_PATH}")
        return
 
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str)
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
 
    # Normalise key columns
    df['sagri_code']    = df['sagri_code'].astype(str).str.strip()
    df['national_id']   = df['national_id'].apply(_norm_id)
    df['selected_crop'] = df.get('selected_crop', pd.Series([''] * len(df))).fillna('')
    df['plot_name']     = df.get('plot_name',     pd.Series([''] * len(df))).fillna('')
 
    # Drop rows with no plot code
    df = df[df['sagri_code'].notna() & (df['sagri_code'] != '') & (df['sagri_code'] != 'nan')]
    print(f"  ✅ Loaded {len(df):,} valid rows")
 
    # ── Connect to DB ─────────────────────────────────────────────────────────
    print(f"\n2. Loading data from database...")
    conn = create_connection()
    if not conn:
        return
    cursor = conn.cursor()
 
    # Existing plot codes in DB
    cursor.execute("SELECT plot_code FROM sagri_plots")
    existing_codes = {row[0] for row in cursor.fetchall()}
    print(f"  ✅ {len(existing_codes)} plot codes currently in sagri_plots")
 
    # farmer_id lookup by national_id
    cursor.execute("SELECT national_id, farmer_id FROM farmers WHERE national_id IS NOT NULL")
    farmer_lookup = {
        str(row[0]).strip().zfill(8): row[1]
        for row in cursor.fetchall()
    }
    print(f"  ✅ {len(farmer_lookup):,} farmers available for linking")
 
    # ── Process rows ──────────────────────────────────────────────────────────
    print(f"\n3. Processing {len(df):,} rows...")
 
    to_update = []
    to_insert = []
    no_farmer = []
 
    for _, row in df.iterrows():
        code       = row['sagri_code']
        nat_id     = row['national_id']
        crop       = str(row['selected_crop']).strip() or None
        plot_name  = str(row['plot_name']).strip() or None
        farmer_id  = farmer_lookup.get(nat_id) if nat_id else None
        region     = _derive_region(code)
 
        if not farmer_id and nat_id:
            no_farmer.append((code, nat_id))
 
        if code in existing_codes:
            to_update.append((nat_id or None, crop, plot_name, farmer_id, code))
        else:
            to_insert.append((code, nat_id or None, farmer_id, region, crop, plot_name))
 
    print(f"\n  📊 Results:")
    print(f"     Rows to UPDATE (existing codes): {len(to_update):,}")
    print(f"     Rows to INSERT (new codes):      {len(to_insert):,}")
    print(f"     Rows with no farmer match:       {len(no_farmer):,}")
 
    if len(no_farmer) > 0:
        print(f"\n  ⚠️  First 5 unmatched national_ids:")
        for code, nat_id in no_farmer[:5]:
            print(f"    {code} → DNI {nat_id} not in farmers table")
 
    # Sample of new inserts
    if len(to_insert) > 0:
        print(f"\n  Sample new rows to insert (first 3):")
        for row in to_insert[:3]:
            print(f"    {row[0]} | DNI: {row[1]} | region: {row[3]} | crop: {row[4]} | plot: {row[5]}")
 
    if not apply:
        print(f"\n  ℹ️  Preview only — run with --apply to update the database")
        cursor.close()
        conn.close()
        return
 
    # ── Apply updates ─────────────────────────────────────────────────────────
    print(f"\n4. Applying changes...")
 
    updated = inserted = errors = 0
 
    # UPDATE existing rows
    for nat_id, crop, plot_name, farmer_id, code in to_update:
        try:
            cursor.execute("""
                UPDATE sagri_plots
                SET national_id   = %s,
                    selected_crop = %s,
                    plot_name     = %s,
                    farmer_id     = %s,
                    updated_at    = CURRENT_TIMESTAMP
                WHERE plot_code = %s
            """, (nat_id, crop, plot_name, farmer_id, code))
            updated += 1
        except Exception as e:
            print(f"  ⚠️  UPDATE error for {code}: {e}")
            errors += 1
 
    # INSERT new rows
    for code, nat_id, farmer_id, region, crop, plot_name in to_insert:
        try:
            cursor.execute("""
                INSERT INTO sagri_plots
                    (plot_code, national_id, farmer_id, region, selected_crop, plot_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (code, nat_id, farmer_id, region, crop, plot_name))
            inserted += 1
        except Exception as e:
            print(f"  ⚠️  INSERT error for {code}: {e}")
            errors += 1
 
    conn.commit()
 
    # Final count
    cursor.execute("SELECT COUNT(*), SUM(farmer_id IS NOT NULL) FROM sagri_plots")
    total, linked = cursor.fetchone()
 
    cursor.close()
    conn.close()
 
    print(f"\n{'=' * 60}")
    print(f"✅ COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Updated existing rows:  {updated:,}")
    print(f"  Inserted new rows:      {inserted:,}")
    print(f"  Errors:                 {errors}")
    print(f"  Total in sagri_plots:   {total:,}")
    print(f"  Rows linked to farmer:  {linked:,} / {total:,}")
    if errors == 0:
        print(f"  ✅ No errors")
 
 
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Populate sagri_plots from Excel')
    parser.add_argument('--apply', action='store_true',
                        help='Apply changes to DB (default: preview only)')
    args = parser.parse_args()
    main(apply=args.apply)