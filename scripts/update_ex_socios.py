"""
Update Ex-Socios — Stage 3 Post-Migration Script
==================================================
Compares the current Norandino membership file against the farmers table
and marks any Norandino farmer who no longer appears in the membership file
as 'Ex-socio'.
 
This preserves all historical data (transactions, visits, inspections)
while accurately reflecting current membership status.
 
Usage:
    python scripts/update_ex_socios.py           # preview changes only
    python scripts/update_ex_socios.py --apply   # apply updates to DB
 
Run after:
    1. Replacing the membership file in data/raw/inspections/norandino/
    2. Running python scripts/run_stage2.py  (to regenerate CSVs)
    3. Running partial Stage 3 to load new farmers
    Then run this script to mark departed members.
"""
 
import sys
import argparse
import pandas as pd
from pathlib import Path
 
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
 
from src.database.connection import create_connection
 
# ── Membership file config (must match data_integrator.py) ───────────────────
MEMBERSHIP_FILE   = project_root / 'data' / 'raw' / 'inspections' / 'norandino' / 'Membresia 14.04.26.xlsx'
MEMBERSHIP_SHEET  = 'Hoja1'
MEMBERSHIP_HEADER = 7   # 0-based = Excel row 8
DNI_COL           = 'DNI'
STATUS_COL        = 'STATUS CERTIFICACION 2026'
 
 
def _norm_id(series: pd.Series) -> pd.Series:
    """Normalise national_id to 8-digit zero-padded string."""
    return (
        series.astype(str).str.strip()
        .str.replace(r'\.0$', '', regex=True)
        .str.zfill(8)
    )
 
 
def main(apply: bool = False):
    print("=" * 60)
    print("EX-SOCIO UPDATE — Norandino Membership Reconciliation")
    print("=" * 60)
    print(f"  Mode: {'APPLY (will update DB)' if apply else 'PREVIEW (no DB changes)'}")
 
    # ── Step 1: Load current membership file ─────────────────────────────────
    print(f"\n1. Loading membership file...")
    try:
        df = pd.read_excel(
            MEMBERSHIP_FILE,
            sheet_name=MEMBERSHIP_SHEET,
            header=MEMBERSHIP_HEADER,
            dtype={DNI_COL: str},
        )
    except FileNotFoundError:
        print(f"  ❌ File not found: {MEMBERSHIP_FILE}")
        return
    except Exception as e:
        print(f"  ❌ Error reading file: {e}")
        return
 
    print(f"  ✅ Loaded {len(df)} rows")
 
    if DNI_COL not in df.columns:
        print(f"  ❌ Column '{DNI_COL}' not found. Available: {df.columns.tolist()[:10]}")
        return
 
    # Get all active national_ids from new file
    active_ids = set(
        _norm_id(df[DNI_COL].dropna())
        .replace({'': None, 'nan': None, '00000000': None})
        .dropna()
    )
    print(f"  ✅ {len(active_ids)} valid national_ids in current membership file")
 
    # ── Step 2: Load Norandino farmers from DB ────────────────────────────────
    print(f"\n2. Loading Norandino farmers from database...")
    conn = create_connection()
    if not conn:
        return
    cursor = conn.cursor()
 
    cursor.execute("""
        SELECT f.farmer_id, f.national_id, f.farmer_name, f.member_status
        FROM farmers f
        JOIN producer_organizations po ON f.org_id = po.org_id
        WHERE po.org_code = 'NO'
          AND f.national_id IS NOT NULL
    """)
    rows = cursor.fetchall()
    db_farmers = pd.DataFrame(rows, columns=['farmer_id', 'national_id', 'farmer_name', 'member_status'])
    db_farmers['national_id'] = _norm_id(db_farmers['national_id'])
 
    print(f"  ✅ {len(db_farmers)} Norandino farmers in DB")
 
    # ── Step 3: Find departed members ─────────────────────────────────────────
    print(f"\n3. Comparing...")
 
    # Farmers in DB but NOT in new membership file
    departed = db_farmers[
        ~db_farmers['national_id'].isin(active_ids) &
        (db_farmers['member_status'] != 'Ex-socio')   # don't re-tag already tagged
    ]
 
    # Farmers who were Ex-socio but are back in the file
    reinstated = db_farmers[
        db_farmers['national_id'].isin(active_ids) &
        (db_farmers['member_status'] == 'Ex-socio')
    ]
 
    # New farmers in file but not yet in DB
    db_ids   = set(db_farmers['national_id'])
    new_members = active_ids - db_ids
 
    print(f"\n  📊 Results:")
    print(f"     Farmers to mark as 'Ex-socio':    {len(departed)}")
    print(f"     Ex-socios reinstated in new file: {len(reinstated)}")
    print(f"     New members not yet in DB:        {len(new_members)}")
 
    if len(departed) > 0:
        print(f"\n  Farmers who will be marked 'Ex-socio':")
        for _, row in departed.head(20).iterrows():
            print(f"    {row['national_id']}  {row['farmer_name'] or '—':40}  "
                  f"current: {row['member_status'] or 'None'}")
        if len(departed) > 20:
            print(f"    ... and {len(departed) - 20} more")
 
    if len(reinstated) > 0:
        print(f"\n  Ex-socios reinstated (will restore their status from file):")
        for _, row in reinstated.head(10).iterrows():
            print(f"    {row['national_id']}  {row['farmer_name'] or '—'}")
 
    if len(new_members) > 0:
        print(f"\n  ⚠️  {len(new_members)} new members not yet in DB")
        print("  Run Stage 2 + partial Stage 3 to load them first.")
 
    # ── Step 4: Apply updates ─────────────────────────────────────────────────
    if not apply:
        print(f"\n  ℹ️  Preview only — run with --apply to update the database")
        cursor.close()
        conn.close()
        return
 
    print(f"\n4. Applying updates...")
 
    # Mark departed as Ex-socio
    if len(departed) > 0:
        departed_ids = tuple(departed['farmer_id'].tolist())
        if len(departed_ids) == 1:
            departed_ids = f"({departed_ids[0]})"
        cursor.execute(f"""
            UPDATE farmers
            SET member_status = 'Ex-socio'
            WHERE farmer_id IN {departed_ids}
        """)
        print(f"  ✅ Marked {len(departed)} farmers as 'Ex-socio'")
 
    # Restore reinstated members — get their current status from file
    if len(reinstated) > 0:
        status_lookup = {}
        if STATUS_COL in df.columns:
            df['_norm_id'] = _norm_id(df[DNI_COL].fillna(''))
            status_lookup = dict(zip(df['_norm_id'], df[STATUS_COL].fillna('Hábil')))
 
        for _, row in reinstated.iterrows():
            new_status = status_lookup.get(row['national_id'], 'Hábil')
            cursor.execute(
                "UPDATE farmers SET member_status = %s WHERE farmer_id = %s",
                (new_status, row['farmer_id'])
            )
        print(f"  ✅ Reinstated {len(reinstated)} Ex-socios with current status")
 
    conn.commit()
    cursor.close()
    conn.close()
 
    print(f"\n{'=' * 60}")
    print("✅ UPDATE COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Marked as Ex-socio:  {len(departed)}")
    print(f"  Reinstated:          {len(reinstated)}")
    print(f"  New members pending: {len(new_members)} (run Stage 2 + Stage 3)")
 
 
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Mark departed Norandino members as Ex-socio'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply updates to DB (default: preview only)'
    )
    args = parser.parse_args()
    main(apply=args.apply)