"""
migrate_eudr.py
================
Migrates EUDR tracking data (Google Sheet exported as CSV) into the SDL.
 
Tables:
  - eudr_alerts          <- EUDR_tracking_-_EUDR_farm_level_alerts.csv
  - eudr_po_compliance   <- EUDR_tracking_-_EUDR_PO_compliance.csv
 
Usage (from repo root):
  python src/eudr/scripts/migrate_eudr.py --table alerts     --csv data/raw/eudr/EUDR_tracking_-_EUDR_farm_level_alerts.csv
  python src/eudr/scripts/migrate_eudr.py --table compliance --csv data/raw/eudr/EUDR_tracking_-_EUDR_PO_compliance.csv
  Add --dry-run to clean + validate + preview only (no DB writes).
 
Idempotent: re-running never duplicates rows.
  - alerts:     UNIQUE row_hash (MD5 of identifying fields) + ON DUPLICATE KEY UPDATE
  - compliance: UNIQUE (flo_id, year) + ON DUPLICATE KEY UPDATE (refreshes metrics)
 
Requires .env with: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_SSL_CA (optional)
"""
 
import argparse
import hashlib
import os
import re
import sys
 
import pandas as pd
 
try:
    import mysql.connector
    from dotenv import load_dotenv
except ImportError:
    mysql = None  # allowed in --dry-run mode
 
# ----------------------------------------------------------------------------
# Cleaning helpers
# ----------------------------------------------------------------------------
 
NULL_TOKENS = {"", "-", "n/a", "na", "none", "null", "nan"}
 
ALERT_TYPE_MAP = {
    # singular/plural inconsistency in source
    "Farms within 200m of protected areas": "Farms within 200m of protected area",
}
 
 
def clean_str(value):
    """Collapse whitespace (incl. embedded newlines) and convert null tokens to None."""
    if pd.isna(value):
        return None
    s = re.sub(r"\s+", " ", str(value)).strip()
    if s.lower() in NULL_TOKENS:
        return None
    return s
 
 
def clean_id(value):
    """IDs must contain NO whitespace at all (source has values like 'CMS2-\\n480')."""
    if pd.isna(value):
        return None
    s = re.sub(r"\s+", "", str(value))
    if s.lower() in NULL_TOKENS:
        return None
    return s
 
 
def clean_float(value):
    if pd.isna(value):
        return None
    s = str(value).strip().replace(",", "")
    if s.lower() in NULL_TOKENS:
        return None
    try:
        return float(s)
    except ValueError:
        return None
 
 
def clean_int(value):
    f = clean_float(value)
    return int(round(f)) if f is not None else None
 
 
def clean_date_mdy(value):
    """Source dates are M/D/YYYY (e.g. 9/1/2023, 10/24/2020)."""
    s = clean_str(value)
    if s is None:
        return None
    d = pd.to_datetime(s, format="%m/%d/%Y", errors="coerce")
    if pd.isna(d):
        d = pd.to_datetime(s, errors="coerce", dayfirst=False)
    return None if pd.isna(d) else d.date()
 
 
# ----------------------------------------------------------------------------
# ALERTS
# ----------------------------------------------------------------------------
 
ALERT_HASH_FIELDS = [
    "flo_id", "farmer_identifier", "farm_unit_id",
    "farm_latitude", "farm_longitude", "alert_type", "event_id", "alert_id",
    "alert_latitude", "alert_longitude", "alert_date",
]
 
ALERT_DB_COLUMNS = ALERT_HASH_FIELDS + ["po_name", "spo_next_steps", "row_hash"]
 
 
def row_hash(row: dict) -> str:
    parts = [str(row.get(f)) if row.get(f) is not None else "" for f in ALERT_HASH_FIELDS]
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
 
 
def clean_alerts(csv_path: str) -> pd.DataFrame:
    raw = pd.read_csv(csv_path, dtype=str)
    print(f"Read {len(raw):,} raw alert rows")
 
    df = pd.DataFrame()
    df["flo_id"] = raw["floid"].map(clean_int)
    df["po_name"] = raw["po_name"].map(clean_str)
    df["farmer_identifier"] = raw["farmer_id"].map(clean_id)
    df["farm_unit_id"] = raw["farm_unit_id"].map(clean_id)
    df["farm_latitude"] = raw["farm_latitude"].map(clean_float)
    df["farm_longitude"] = raw["farm_longitude"].map(clean_float)
    df["alert_type"] = raw["alert_type"].map(clean_str).replace(ALERT_TYPE_MAP)
    df["event_id"] = raw["event_id"].map(clean_id)
    df["alert_id"] = raw["alert_id"].map(clean_id)
    df["alert_latitude"] = raw["alert_latitude"].map(clean_float)
    df["alert_longitude"] = raw["alert_longitude"].map(clean_float)
    df["alert_date"] = raw["alert_date"].map(clean_date_mdy)
    df["spo_next_steps"] = raw["spo_next_steps"].map(clean_str)
 
    # ---- Validations -------------------------------------------------------
    bad_coords = df[df["farm_latitude"].isna() | df["farm_longitude"].isna()]
    if len(bad_coords):
        print(f"WARNING: {len(bad_coords)} rows with invalid farm coordinates -> skipped")
        df = df.drop(bad_coords.index)
 
    missing_key = df[df["flo_id"].isna() | df["farmer_identifier"].isna()]
    if len(missing_key):
        print(f"WARNING: {len(missing_key)} rows without flo_id or farmer_identifier -> skipped")
        df = df.drop(missing_key.index)
 
    # ---- Drop completely duplicated rows (identical in ALL columns) --------
    # Confirmed in source: same farmer + same event_id + same alert_id + same
    # date + same coordinates repeated verbatim (Satelligence export artifact).
    before = len(df)
    df = df.drop_duplicates()
    print(f"Dropped {before - len(df):,} exact duplicate rows (identical in all columns)")
 
    # ---- Idempotency hash ---------------------------------------------------
    # Hash EXCLUDES spo_next_steps so that editing next-steps text in the sheet
    # UPDATES the existing row instead of inserting a near-duplicate.
    df["row_hash"] = df.apply(lambda r: row_hash(r.to_dict()), axis=1)
    dup_hash = df["row_hash"].duplicated().sum()
    if dup_hash:
        print(f"NOTE: {dup_hash} rows share identical identifying fields "
              f"(differ only in spo_next_steps) -> keeping last occurrence")
        df = df.drop_duplicates("row_hash", keep="last")
 
    print(f"Clean alert rows ready: {len(df):,}")
    print("\nRows per PO:")
    print(df.groupby(["flo_id", "po_name"]).size().to_string())
    return df
 
 
# ----------------------------------------------------------------------------
# COMPLIANCE
# ----------------------------------------------------------------------------
 
COMPLIANCE_DB_COLUMNS = [
    "flo_id", "po_name", "year", "compliance_level", "excluded_farms",
    "members", "monitored_area_ha", "farms_count", "points", "polygons",
    "deforestation_farms_count", "deforestation_ha", "alert_farms_count",
    "alert_count", "protected_area_farms_count", "current_validation_status",
    "last_validation_date", "last_updated",
]
 
 
def clean_compliance(csv_path: str) -> pd.DataFrame:
    raw = pd.read_csv(csv_path, dtype=str)
    print(f"Read {len(raw):,} raw compliance rows")
 
    df = pd.DataFrame()
    df["flo_id"] = raw["flo_id"].map(clean_int)
    df["po_name"] = raw["po_name"].map(clean_str)
    df["year"] = raw["year"].map(clean_int)
    df["compliance_level"] = raw["compliance_level"].map(clean_str)
    # 'xyz' is a known placeholder until real links are added in the sheet
    df["excluded_farms"] = raw["excluded_farms"].map(clean_str).replace({"xyz": None})
    df["members"] = raw["members"].map(clean_int)
    df["monitored_area_ha"] = raw["monitored_area_ha"].map(clean_float)
    df["farms_count"] = raw["farms_count"].map(clean_int)
    df["points"] = raw["points"].map(clean_int)
    df["polygons"] = raw["polygons"].map(clean_int)
    df["deforestation_farms_count"] = raw["deforestation_farms_count"].map(clean_int)
    df["deforestation_ha"] = raw["deforestation_ha"].map(clean_float)
    df["alert_farms_count"] = raw["alert_farms_count"].map(clean_int)
    df["alert_count"] = raw["alert_count"].map(clean_int)
    df["protected_area_farms_count"] = raw["protected_area_farms_count"].map(clean_int)
    df["current_validation_status"] = raw["current_validation_status"].map(clean_str)
    df["last_validation_date"] = raw["last_validation_date"].map(clean_date_mdy)
    df["last_updated"] = raw["last_updated"].map(clean_date_mdy)
 
    df = df.dropna(subset=["flo_id", "year"])
 
    # Detect natural-key conflicts BEFORE touching the DB
    dups = df[df.duplicated(["flo_id", "year"], keep=False)]
    if len(dups):
        print("\n*** DATA ERROR: duplicated (flo_id, year) combinations in the sheet ***")
        print(dups[["flo_id", "po_name", "year"]].to_string())
        print("Fix these in the Google Sheet, re-export, and run again. Aborting.")
        sys.exit(1)
 
    print(f"Clean compliance rows ready: {len(df):,}")
    return df
 
 
# ----------------------------------------------------------------------------
# DB load
# ----------------------------------------------------------------------------
 
def get_connection():
    load_dotenv()
    cfg = dict(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "25060")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
    ssl_ca = os.getenv("DB_SSL_CA")
    if ssl_ca:
        cfg["ssl_ca"] = ssl_ca
    return mysql.connector.connect(**cfg)
 
 
def load_dataframe(df: pd.DataFrame, table: str, columns: list, batch_size: int = 1000):
    conn = get_connection()
    cursor = conn.cursor()
 
    placeholders = ", ".join(["%s"] * len(columns))
    col_list = ", ".join(f"`{c}`" for c in columns)
    update_clause = ", ".join(f"`{c}` = VALUES(`{c}`)" for c in columns)
    sql = (f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {update_clause}")
 
    rows = [tuple(None if pd.isna(v) else v for v in rec)
            for rec in df[columns].itertuples(index=False, name=None)]
 
    processed = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            cursor.executemany(sql, batch)
            conn.commit()
        except mysql.connector.Error as e:
            print(f"Batch {i // batch_size} failed: {e} -> reconnecting and retrying once")
            conn = get_connection()
            cursor = conn.cursor()
            cursor.executemany(sql, batch)
            conn.commit()
        processed += len(batch)
        print(f"  {processed:,}/{len(rows):,} rows processed", end="\r")
 
    print(f"\nDone. {len(rows):,} rows upserted into `{table}`.")
    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
    print(f"`{table}` now contains {cursor.fetchone()[0]:,} rows.")
    cursor.close()
    conn.close()
 
 
# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
 
def main():
    parser = argparse.ArgumentParser(description="Migrate EUDR data to the SDL")
    parser.add_argument("--table", choices=["alerts", "compliance"], required=True)
    parser.add_argument("--csv", required=True, help="Path to the exported CSV")
    parser.add_argument("--dry-run", action="store_true",
                        help="Clean + validate + report only; no DB writes")
    args = parser.parse_args()
 
    if args.table == "alerts":
        df = clean_alerts(args.csv)
        table, columns = "eudr_alerts", ALERT_DB_COLUMNS
    else:
        df = clean_compliance(args.csv)
        table, columns = "eudr_po_compliance", COMPLIANCE_DB_COLUMNS
 
    if args.dry_run:
        out = os.path.splitext(args.csv)[0] + "_CLEAN_PREVIEW.csv"
        df.to_csv(out, index=False)
        print(f"\n[dry-run] No DB writes. Clean preview saved to: {out}")
        return
 
    if mysql is None:
        print("mysql-connector-python / python-dotenv not installed. "
              "Run: pip install mysql-connector-python python-dotenv")
        sys.exit(1)
 
    load_dataframe(df, table, columns)
 
 
if __name__ == "__main__":
    main()