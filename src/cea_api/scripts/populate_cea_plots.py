"""
Populate CEA Plot Codes in Farmers Table
=========================================
Reads sagri_codes.xlsx (which contains national_ids) and:
1. Updates farmers.cea_plot_code for all 2,695 CEA project farmers
2. Exports src/cea_api/data/cea_plot_codes.csv (no DNIs — safe for GitHub/Streamlit)
 
This script does NOT touch sagri_plots — that table is managed separately
by sagri_api/scripts/populate_sagri_plots.py
 
Usage:
    python src/cea_api/scripts/populate_cea_plots.py           # preview only
    python src/cea_api/scripts/populate_cea_plots.py --apply   # apply to DB
"""
 
import sys
import argparse
import pandas as pd
from pathlib import Path
 
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
 
from src.database.connection import create_connection
 
EXCEL_PATH = project_root / "data" / "raw" / "sagri" / "sagri_codes.xlsx"
SHEET_NAME = "Sheet1"
WEBAPP_CSV = Path(__file__).parent.parent / "data" / "cea_plot_codes.csv"
 
 
def _norm_id(val) -> str:
    if pd.isna(val) or str(val).strip() in ("", "nan"):
        return ""
    return str(val).strip().replace(".0", "").zfill(8)
 
 
def _export_webapp_csv(df: pd.DataFrame) -> None:
    WEBAPP_CSV.parent.mkdir(parents=True, exist_ok=True)
    clean_df = df[["sagri_code", "selected_crop", "plot_name"]].copy()
    clean_df.columns = ["cea_code", "selected_crop", "plot_name"]
    clean_df = clean_df[
        clean_df["cea_code"].notna() &
        (clean_df["cea_code"] != "") &
        (clean_df["cea_code"] != "nan")
    ].drop_duplicates(subset=["cea_code"])
    clean_df.to_csv(WEBAPP_CSV, index=False)
    print(f"  ✅ Webapp CSV: {len(clean_df):,} rows, no DNIs → safe for GitHub")
    print(f"     {WEBAPP_CSV}")
 
 
def main(apply: bool = False):
    print("=" * 60)
    print("POPULATE CEA PLOT CODES IN FARMERS TABLE")
    print("=" * 60)
    print(f"  Mode: {'APPLY' if apply else 'PREVIEW (no DB changes)'}")
 
    print(f"\n1. Loading {EXCEL_PATH.name}...")
    if not EXCEL_PATH.exists():
        print(f"  ❌ File not found: {EXCEL_PATH}")
        return
 
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["sagri_code"]    = df["sagri_code"].astype(str).str.strip()
    df["national_id"]   = df["national_id"].apply(_norm_id)
    df["selected_crop"] = df.get("selected_crop", pd.Series([""] * len(df))).fillna("")
    df["plot_name"]     = df.get("plot_name",     pd.Series([""] * len(df))).fillna("")
 
    valid = df[
        df["sagri_code"].notna() & (df["sagri_code"] != "") & (df["sagri_code"] != "nan") &
        (df["national_id"] != "")
    ].copy()
    no_dni = df[(df["sagri_code"] != "") & (df["national_id"] == "")]
 
    print(f"  ✅ Total rows: {len(df):,}")
    print(f"  ✅ Rows with DNI (can update farmers): {len(valid):,}")
    print(f"  ⚠️  Rows without DNI (skipped):        {len(no_dni):,}")
 
    if not apply:
        print(f"\n  Would update farmers.cea_plot_code for {len(valid):,} farmers")
        print("  Sample (first 5):")
        for _, row in valid.head(5).iterrows():
            print(f"    DNI {row['national_id']} → {row['sagri_code']}")
        print("\n  ℹ️  Preview only — run with --apply to update DB")
        _export_webapp_csv(df)
        return
 
    print("\n2. Connecting to database...")
    conn = create_connection()
    if not conn:
        return
    cursor = conn.cursor()
 
    print(f"\n3. Updating farmers.cea_plot_code for {len(valid):,} rows...")
    updated = not_found = errors = 0
 
    for _, row in valid.iterrows():
        try:
            cursor.execute(
                "UPDATE farmers SET cea_plot_code = %s WHERE national_id = %s",
                (row["sagri_code"], row["national_id"])
            )
            if cursor.rowcount > 0:
                updated += 1
            else:
                not_found += 1
        except Exception as e:
            print(f"  ⚠️  Error {row['sagri_code']}: {e}")
            errors += 1
 
    conn.commit()
    cursor.close()
    conn.close()
 
    print(f"\n{'=' * 60}")
    print(f"✅ COMPLETE")
    print(f"{'=' * 60}")
    print(f"  farmers updated:           {updated:,}")
    print(f"  DNIs not in farmers:       {not_found:,}")
    if errors:
        print(f"  ❌ Errors: {errors}")
 
    _export_webapp_csv(df)
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    main(apply=args.apply)