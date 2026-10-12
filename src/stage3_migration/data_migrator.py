"""
Data Migrator - Stage 3 MySQL Migration
=========================================
Loads all Stage 2 CSV outputs into the DigitalOcean MySQL SDL database.
 
CSV source: data/mysql_ready/  (relative to project root)
    master/      → farmers_data.csv, lookup_producer_orgs.csv
    operational/ → farmers_addresses.csv, farmer_level_inspections.csv,
                   plot_level_inspections.csv, farmer_level_harvests.csv,
                   plot_level_harvests.csv, acopio_transactions.csv
    lookup/      → lookup_currencies.csv, lookup_genders.csv,
                   lookup_countries.csv, lookup_product_types.csv,
                   lookup_units.csv
 
Farmer lookup strategy (used consistently across all loaders):
    Primary:   WHERE national_id = %s   — covers all 8,271 farmers
    Fallback:  WHERE pd_farmer_id = %s  — inspection farmers only
    This covers membership-only and External farmers that have no pd_farmer_id.
 
Load order (respects foreign key dependencies):
    1.  lookup_currencies
    2.  lookup_genders
    3.  lookup_product_types
    4.  lookup_units
    5.  lookup_countries           (FK → lookup_currencies)
    6.  producer_organizations     (FK → lookup_countries)
    7.  farmers                    (FK → producer_organizations, lookup_genders)
    8.  farmer_addresses           (FK → farmers, lookup_countries)
    9.  inspections_farmer_level   (FK → farmers, lookup_product_types)
    10. inspections_plot_level     (FK → farmers, lookup_product_types)
    11. harvests_farmer_level      (FK → farmers, inspections_farmer_level)
    12. harvests_plot_level        (FK → farmers, inspections_plot_level)
    13. collection_transactions    (FK → farmers, lookup_product_types, lookup_currencies)
 
Usage:
    from src.stage3_migration.data_migrator import load_all_data
    load_all_data()
 
    Or via runner:
    python scripts/run_stage3.py
"""
 
import os
import pandas as pd
from pathlib import Path
 
from src.database.connection import create_connection
from src.utils.dni_cleaner import DNICleaner
_dni_cleaner = DNICleaner(verbose=False)
 
# ---------------------------------------------------------------------------
# Paths — relative to project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent
 
MYSQL_READY  = PROJECT_ROOT / 'data' / 'mysql_ready'
MASTER       = MYSQL_READY / 'master'
OPERATIONAL  = MYSQL_READY / 'operational'
LOOKUP       = MYSQL_READY / 'lookup'
 
 
# =============================================================================
# SHARED HELPERS
# =============================================================================
 
def _val(row, col):
    """Return None for NaN/empty values, otherwise return the string value."""
    v = row.get(col)
    if v is None:
        return None
    if isinstance(v, float) and __import__('math').isnan(v):
        return None
    s = str(v).strip()
    return None if s in ('', 'nan', 'NaN', 'None', 'NA') else s
 
 
def _num(row, col):
    """Return float or None."""
    v = row.get(col)
    if v is None:
        return None
    try:
        f = float(v)
        return None if __import__('math').isnan(f) else f
    except (ValueError, TypeError):
        return None
 
 
def _date(row, col):
    """Return a valid YYYY-MM-DD date string or None.
 
    Handles:
      '2025'        -> '2025-01-01'  (bare year from membership file)
      '2023-06-15'  -> '2023-06-15'  (ISO format, pass through)
      '15-06-2023'  -> '2023-06-15'  (Latin American DD-MM-YYYY with dashes)
      '15/06/2023'  -> '2023-06-15'  (Latin American DD/MM/YYYY with slashes)
      '06/15/2023'  -> '2023-06-15'  (US MM/DD/YYYY with slashes)
      ''/ None / unparseable -> None
    """
    v = _val(row, col)
    if not v:
        return None
    v = str(v).strip()
    from datetime import datetime
 
    # Bare 4-digit year — convert to Jan 1 of that year
    if v.isdigit() and len(v) == 4:
        return f"{v}-01-01"
 
    # Detect DD-MM-YYYY vs YYYY-MM-DD by checking if first segment is 2 digits
    if '-' in v:
        parts = v.split('-')
        if len(parts) == 3 and len(parts[0]) == 2:
            # Looks like DD-MM-YYYY (Latin American format with dashes)
            try:
                return datetime.strptime(v, '%d-%m-%Y').strftime('%Y-%m-%d')
            except ValueError:
                pass
 
    # Try remaining formats in order
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(v, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None
 
 
def _coord(row, col, is_lat=True):
    v = _num(row, col)
    if v is None:
        return None
    if is_lat and not (-90 <= v <= 90):
        return None
    if not is_lat and not (-180 <= v <= 180):
        return None
    return v
 
 
def _bool(value):
    """Convert TRUE/FALSE string or bool to 1/0."""
    return 1 if str(value).strip().upper() == 'TRUE' else 0
 
 
def _get_farmer_id(cursor, national_id=None, pd_farmer_id=None):
    """
    Look up MySQL farmer_id.
    Primary:  national_id  — works for all 8,271 farmers including
              membership-only (Norandino) and External (transaction-only) farmers.
    Fallback: pd_farmer_id — works for inspection farmers only (4,443).
    Returns farmer_id int or None if not found.
    """
    if national_id and str(national_id).strip() not in ('', 'nan', 'None'):
        cursor.execute(
            "SELECT farmer_id FROM farmers WHERE national_id = %s LIMIT 1",
            (str(national_id).strip(),)
        )
        result = cursor.fetchone()
        if result:
            return result[0]
 
    if pd_farmer_id and str(pd_farmer_id).strip() not in ('', 'nan', 'None'):
        cursor.execute(
            "SELECT farmer_id FROM farmers WHERE pd_farmer_id = %s LIMIT 1",
            (str(pd_farmer_id).strip(),)
        )
        result = cursor.fetchone()
        if result:
            return result[0]
 
    return None
 
 
# =============================================================================
# CLEAR DATA
# =============================================================================
 
def _ping_connection(conn):
    """Ping connection to keep it alive. Reconnects if dropped."""
    try:
        conn.ping(reconnect=True, attempts=3, delay=5)
    except Exception:
        pass
 
 
def _progress(loaded: int, skipped: int, total: int, label: str):
    done = loaded + skipped
    pct  = done / total * 100 if total else 0
    print(f"    [{pct:5.1f}%] {done:,}/{total:,} processed "
          f"— {loaded:,} loaded, {skipped:,} skipped  ({label})", flush=True)
 
 
def clear_existing_data() -> bool:
    """Delete all data from main tables in reverse FK order. Keeps lookup data."""
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        print("  Clearing main tables...")
        # technical_assistance_visits is cleared here so it can be
        # repopulated via import_kobo_visits.py after migration completes.
        # The Kobo importer looks up farmer_id by national_id at import time,
        # so it always links correctly to the freshly loaded farmers table.
        for table in [
            'technical_assistance_visits',  # FK → farmers
            'collection_transactions',      # FK → farmers
            'harvests_plot_level',          # FK → farmers
            'harvests_farmer_level',        # FK → farmers
            'inspections_plot_level',       # FK → farmers
            'inspections_farmer_level',     # FK → farmers
            'farmer_addresses',             # FK → farmers
            'farmers',                      # FK → producer_organizations
            'extensionists',                # FK → producer_organizations
            'producer_organizations',       # parent — safe to delete now
        ]:
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()
        print("  ✅ Main tables cleared")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def clear_lookup_data() -> bool:
    """Delete lookup tables (only needed for a completely fresh database)."""
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        for table in [
            'lookup_units',         # FK → lookup_countries (country_primary)
            'lookup_product_types', # no FK
            'lookup_genders',       # no FK
            'lookup_countries',     # FK → lookup_currencies
            'lookup_currencies',    # parent
        ]:
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()
        print("  ✅ Lookup tables cleared")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
# =============================================================================
# LOOKUP TABLES
# =============================================================================
 
def load_currencies() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(LOOKUP / 'lookup_currencies.csv')
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO lookup_currencies (currency_code, currency_name, currency_symbol, is_active)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE currency_name = VALUES(currency_name)
            """, (_val(row, 'currency_code'), _val(row, 'currency_name'),
                  _val(row, 'currency_symbol'), _bool(row.get('is_active', True))))
        conn.commit()
        print(f"  ✅ {len(df)} currencies")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_genders() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(LOOKUP / 'lookup_genders.csv')
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO lookup_genders (gender_code, gender_name)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE gender_name = VALUES(gender_name)
            """, (_val(row, 'gender_code'), _val(row, 'gender_name')))
        conn.commit()
        print(f"  ✅ {len(df)} genders")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_product_types() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(LOOKUP / 'lookup_product_types.csv')
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO lookup_product_types (product_code, product_name, is_active)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE product_name = VALUES(product_name)
            """, (_val(row, 'product_code'), _val(row, 'product_name'),
                  _bool(row.get('is_active', True))))
        conn.commit()
        print(f"  ✅ {len(df)} product types")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_units() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(LOOKUP / 'lookup_units.csv')
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO lookup_units (unit_code, unit_name, kg_conversion_rate, country_primary, is_active)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE unit_name = VALUES(unit_name)
            """, (_val(row, 'unit_code'), _val(row, 'unit_name'),
                  _num(row, 'kg_conversion_rate'), _val(row, 'country_primary'),
                  _bool(row.get('is_active', True))))
        conn.commit()
        print(f"  ✅ {len(df)} units")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_countries() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(LOOKUP / 'lookup_countries.csv')
        skipped = 0
        for _, row in df.iterrows():
            cursor.execute(
                "SELECT currency_id FROM lookup_currencies WHERE currency_code = %s",
                (_val(row, 'currency_code'),)
            )
            result = cursor.fetchone()
            if not result:
                print(f"    ⚠️  Currency {row['currency_code']} not found, skipping {row['country_code']}")
                skipped += 1
                continue
            cursor.execute("""
                INSERT INTO lookup_countries (country_name, country_code, currency_id, phone_country_code)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE country_name = VALUES(country_name)
            """, (_val(row, 'country_name'), _val(row, 'country_code'),
                  result[0], _val(row, 'phone_country_code')))
        conn.commit()
        print(f"  ✅ {len(df) - skipped} countries")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
# =============================================================================
# MASTER TABLES
# =============================================================================
 
def load_organizations() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(MASTER / 'lookup_producer_orgs.csv')
        skipped = 0
        for _, row in df.iterrows():
            cursor.execute(
                "SELECT country_id FROM lookup_countries WHERE country_code = %s",
                (_val(row, 'country_code'),)
            )
            result = cursor.fetchone()
            if not result:
                print(f"    ⚠️  Country {row['country_code']} not found, skipping {row['org_code']}")
                skipped += 1
                continue
            cursor.execute("""
                INSERT INTO producer_organizations (org_name, country_id, org_code, flo_id)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE org_name = VALUES(org_name)
            """, (_val(row, 'org_name'), result[0],
                  _val(row, 'org_code'), _val(row, 'flo_id')))
        conn.commit()
        print(f"  ✅ {len(df) - skipped} organizations")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_farmers() -> bool:
    """
    Load all 8,271 farmers.
    national_id is the unique business key — ON DUPLICATE KEY handles conflicts
    gracefully (e.g. a farmer appearing in both inspections and membership file).
    pd_farmer_id stored as nullable reference metadata.
    """
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(MASTER / 'farmers_data.csv')
        loaded = skipped = 0
 
        # Guard against duplicate pd_farmer_id within the CSV
        # (can happen with multi-year inspections before deduplication)
        # Keep first occurrence — national_id is the true unique key
        before = len(df)
        dup_mask = (
            df['pd_farmer_id'].notna() &
            (df['pd_farmer_id'].astype(str).str.strip() != '') &
            (df['pd_farmer_id'].astype(str).str.strip() != 'nan') &
            df.duplicated(subset=['pd_farmer_id'], keep='first')
        )
        if dup_mask.sum() > 0:
            # Null out pd_farmer_id for duplicates rather than dropping rows
            # so the farmer record is still inserted, just without the duplicate ID
            df.loc[dup_mask, 'pd_farmer_id'] = None
            print(f"  ℹ️  Nulled {dup_mask.sum()} duplicate pd_farmer_id values "
                  f"(national_id remains unique key)")
 
        for _, row in df.iterrows():
            cursor.execute(
                "SELECT org_id FROM producer_organizations WHERE org_code = %s",
                (_val(row, 'org_code'),)
            )
            result = cursor.fetchone()
            if not result:
                print(f"    ⚠️  Org {row['org_code']} not found, skipping farmer")
                skipped += 1
                continue
            org_id = result[0]
 
            gender_id = None
            gender_code = _val(row, 'gender_code')
            if gender_code:
                cursor.execute(
                    "SELECT gender_id FROM lookup_genders WHERE gender_code = %s",
                    (gender_code,)
                )
                g = cursor.fetchone()
                if g:
                    gender_id = g[0]
 
            cursor.execute("""
                INSERT INTO farmers (
                    org_id, pd_farmer_id, national_id, farmer_name, telephone,
                    gender_id, birth_date, base, org_first_level, org_coordination,
                    member_status, entry_date, membership_number
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    farmer_name       = COALESCE(VALUES(farmer_name),       farmer_name),
                    telephone         = COALESCE(VALUES(telephone),         telephone),
                    member_status     = COALESCE(VALUES(member_status),     member_status),
                    base              = COALESCE(VALUES(base),              base),
                    org_first_level   = COALESCE(VALUES(org_first_level),   org_first_level),
                    org_coordination  = COALESCE(VALUES(org_coordination),  org_coordination),
                    pd_farmer_id      = COALESCE(pd_farmer_id, VALUES(pd_farmer_id))
            """, (
                org_id,
                _val(row, 'pd_farmer_id'),
                _val(row, 'national_id'),
                _val(row, 'farmer_name'),
                _val(row, 'telephone'),
                gender_id,
                _date(row, 'birth_date'),
                _val(row, 'base'),
                _val(row, 'org_first_level'),
                _val(row, 'org_coordination'),
                _val(row, 'member_status'),
                _date(row, 'entry_date'),
                _val(row, 'membership_number'),
            ))
            loaded += 1
 
            if loaded % 500 == 0:
                conn.commit()
                _progress(loaded, skipped, len(df), 'farmers')
 
        conn.commit()
        print(f"  ✅ {loaded} farmers loaded, {skipped} skipped")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
# =============================================================================
# OPERATIONAL TABLES
# =============================================================================
 
def _clear_farmer_addresses() -> bool:
    """Clear farmer_addresses so it can be reloaded cleanly."""
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM farmer_addresses")
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM farmer_addresses")
        count = cursor.fetchone()[0]
        print(f"  ✅ farmer_addresses cleared ({count} rows remaining)")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_farmer_addresses() -> bool:
    """
    Load farmer addresses.
    Uses national_id (primary) or pd_farmer_id (fallback) for farmer lookup.
    Covers all 8,271 farmers including membership-only and External farmers.
    """
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(OPERATIONAL / 'farmers_addresses.csv')
        loaded = skipped = 0
 
        for _, row in df.iterrows():
            farmer_id = _get_farmer_id(
                cursor,
                national_id=_val(row, 'national_id'),
                pd_farmer_id=_val(row, 'pd_farmer_id'),
            )
            if not farmer_id:
                skipped += 1
                continue
 
            cursor.execute(
                "SELECT country_id FROM lookup_countries WHERE country_code = %s",
                (_val(row, 'country_code') or 'PER',)
            )
            result = cursor.fetchone()
            if not result:
                skipped += 1
                continue
 
            # Skip if address already exists for this farmer
            cursor.execute(
                "SELECT 1 FROM farmer_addresses WHERE farmer_id = %s LIMIT 1",
                (farmer_id,)
            )
            if cursor.fetchone():
                skipped += 1
                if (loaded + skipped) % 500 == 0:
                    _progress(loaded, skipped, len(df), 'addresses')
                continue
 
            cursor.execute("""
                INSERT INTO farmer_addresses (
                    farmer_id, country_id,
                    administrative_area_1, administrative_area_2,
                    administrative_area_3, administrative_area_4,
                    postal_code, address_line, formatted_address
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                farmer_id, result[0],
                _val(row, 'administrative_area_1'),
                _val(row, 'administrative_area_2'),
                _val(row, 'administrative_area_3'),
                _val(row, 'administrative_area_4'),
                _val(row, 'postal_code'),
                _val(row, 'address_line'),
                _val(row, 'formatted_address'),
            ))
            loaded += 1
 
            if loaded % 500 == 0:
                conn.commit()
                _ping_connection(conn)
                _progress(loaded, skipped, len(df), 'addresses')
 
        conn.commit()
        print(f"  ✅ {loaded} addresses loaded, {skipped} skipped")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_farmer_inspections() -> bool:
    """
    Load farmer-level inspections.
    Chirinos contributes 5 rows per farmer (one per year 2020–2024) — handled naturally
    since the table has no unique constraint on (farmer_id, inspection_year).
    """
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(OPERATIONAL / 'farmer_level_inspections.csv')
        loaded = skipped = 0
        has_national_id = 'national_id' in df.columns
 
        for _, row in df.iterrows():
            farmer_id = _get_farmer_id(
                cursor,
                national_id=_val(row, 'national_id') if has_national_id else None,
                pd_farmer_id=_val(row, 'pd_farmer_id'),
            )
            if not farmer_id:
                skipped += 1
                continue
 
            cursor.execute(
                "SELECT product_type_id FROM lookup_product_types WHERE product_code = %s",
                (_val(row, 'product_code') or 'COFFEE',)
            )
            result = cursor.fetchone()
            if not result:
                skipped += 1
                continue
            product_type_id = result[0]
 
            # Skip if inspection already exists for this farmer + year
            cursor.execute(
                "SELECT 1 FROM inspections_farmer_level WHERE farmer_id = %s AND inspection_year = %s LIMIT 1",
                (farmer_id, _val(row, 'inspection_year'))
            )
            if cursor.fetchone():
                skipped += 1
                continue
 
            cursor.execute("""
                INSERT INTO inspections_farmer_level (
                    farmer_id, inspection_year, internal_inspector_name, product_type_id,
                    base, category, number_of_plots,
                    total_area_ha, coffee_area_ha, growing_area_ha, conversion_area_ha,
                    other_crops_area_ha, forest_area_ha, secondary_forest_area_ha,
                    purma_area_ha, rehabilitation_area_ha, cultivable_area_ha,
                    latitude, longitude, altitude, utm_zone, x_east, y_north,
                    last_internal_control_date, internal_control_result,
                    conversion_start_date, last_external_control_date,
                    eu_previous_certification, eu_current_certification,
                    nop_current_certification, certification_seals, certification_type,
                    temporary_workers_count, female_workers_count, sampling_point
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                farmer_id, _val(row, 'inspection_year'),
                _val(row, 'internal_inspector_name'), product_type_id,
                _val(row, 'base'), _val(row, 'category'),
                _num(row, 'number_of_plots'),
                _num(row, 'total_area_ha'), _num(row, 'coffee_area_ha'),
                _num(row, 'growing_area_ha'), _num(row, 'conversion_area_ha'),
                _num(row, 'other_crops_area_ha'), _num(row, 'forest_area_ha'),
                _num(row, 'secondary_forest_area_ha'), _num(row, 'purma_area_ha'),
                _num(row, 'rehabilitation_area_ha'), _num(row, 'cultivable_area_ha'),
                _coord(row, 'latitude', is_lat=True), _coord(row, 'longitude', is_lat=False), _num(row, 'altitude'),
                _val(row, 'utm_zone'), _num(row, 'x_east'), _num(row, 'y_north'),
                _date(row, 'last_internal_control_date'),
                _val(row, 'internal_control_result'),
                _date(row, 'conversion_start_date'),
                _date(row, 'last_external_control_date'),
                _val(row, 'eu_previous_certification'),
                _val(row, 'eu_current_certification'),
                _val(row, 'nop_current_certification'),
                _val(row, 'certification_seals'),
                _val(row, 'certification_type'),
                _num(row, 'temporary_workers_count'),
                _num(row, 'female_workers_count'),
                _val(row, 'sampling_point'),
            ))
            loaded += 1
 
            total_processed = loaded + skipped
            if total_processed % 100 == 0:
                conn.commit()
                _ping_connection(conn)
            if total_processed % 500 == 0:
                _progress(loaded, skipped, len(df), 'farmer inspections')
 
        conn.commit()
        print(f"  ✅ {loaded} farmer inspections loaded, {skipped} skipped")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_plot_inspections() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(OPERATIONAL / 'plot_level_inspections.csv')
        loaded = skipped = 0
        has_national_id = 'national_id' in df.columns
 
        for _, row in df.iterrows():
            farmer_id = _get_farmer_id(
                cursor,
                national_id=_val(row, 'national_id') if has_national_id else None,
                pd_farmer_id=_val(row, 'pd_farmer_id'),
            )
            if not farmer_id:
                skipped += 1
                continue
 
            cursor.execute(
                "SELECT product_type_id FROM lookup_product_types WHERE product_code = %s",
                (_val(row, 'product_code') or 'COFFEE',)
            )
            result = cursor.fetchone()
            if not result:
                skipped += 1
                continue
            product_type_id = result[0]
 
            # Skip if plot inspection already exists for this farmer + plot + year
            cursor.execute(
                "SELECT 1 FROM inspections_plot_level WHERE farmer_id = %s AND plot_name = %s AND inspection_year = %s LIMIT 1",
                (farmer_id, _val(row, 'plot_name'), _val(row, 'inspection_year'))
            )
            if cursor.fetchone():
                skipped += 1
                continue
 
            cursor.execute("""
                INSERT INTO inspections_plot_level (
                    farmer_id, inspection_year, plot_internal_inspector_name, product_type_id,
                    plot_name, plot_category, plot_area_ha, plot_coffee_area_ha,
                    plot_other_crops_area_ha, plot_growing_area_ha, plot_conversion_area_ha,
                    plot_forest_area_ha, plot_rehabilitation_area_ha,
                    latitude, longitude, altitude, utm_zone, x_east, y_north,
                    plot_last_internal_control_date, plot_internal_control_result,
                    plot_conversion_start_date, plot_eu_previous_certification,
                    plot_eu_current_certification, plot_nop_current_certification
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                farmer_id, _val(row, 'inspection_year'),
                _val(row, 'plot_internal_inspector_name'), product_type_id,
                _val(row, 'plot_name'), _val(row, 'plot_category'),
                _num(row, 'plot_area_ha'), _num(row, 'plot_coffee_area_ha'),
                _num(row, 'plot_other_crops_area_ha'), _num(row, 'plot_growing_area_ha'),
                _num(row, 'plot_conversion_area_ha'), _num(row, 'plot_forest_area_ha'),
                _num(row, 'plot_rehabilitation_area_ha'),
                _coord(row, 'latitude', is_lat=True), _coord(row, 'longitude', is_lat=False), _num(row, 'altitude'),
                _val(row, 'utm_zone'), _num(row, 'x_east'), _num(row, 'y_north'),
                _date(row, 'plot_last_internal_control_date'),
                _val(row, 'plot_internal_control_result'),
                _date(row, 'plot_conversion_start_date'),
                _val(row, 'plot_eu_previous_certification'),
                _val(row, 'plot_eu_current_certification'),
                _val(row, 'plot_nop_current_certification'),
            ))
            loaded += 1
 
            total_processed = loaded + skipped
            if total_processed % 100 == 0:
                conn.commit()
                _ping_connection(conn)
            if total_processed % 500 == 0:
                _progress(loaded, skipped, len(df), 'plot inspections')
 
        conn.commit()
        print(f"  ✅ {loaded} plot inspections loaded, {skipped} skipped")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_farmer_harvests() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(OPERATIONAL / 'farmer_level_harvests.csv')
        loaded = skipped = 0
        has_national_id = 'national_id' in df.columns
 
        for _, row in df.iterrows():
            farmer_id = _get_farmer_id(
                cursor,
                national_id=_val(row, 'national_id') if has_national_id else None,
                pd_farmer_id=_val(row, 'pd_farmer_id'),
            )
            if not farmer_id:
                skipped += 1
                continue
 
            cursor.execute("""
                SELECT inspection_id FROM inspections_farmer_level
                WHERE farmer_id = %s AND inspection_year = %s
                ORDER BY inspection_id LIMIT 1
            """, (farmer_id, _val(row, 'harvest_year')))
            result = cursor.fetchone()
            if not result:
                skipped += 1
                continue
            inspection_id = result[0]
 
            cursor.execute(
                "SELECT product_type_id FROM lookup_product_types WHERE product_code = %s",
                (_val(row, 'product_code') or 'COFFEE',)
            )
            result = cursor.fetchone()
            if not result:
                skipped += 1
                continue
            product_type_id = result[0]
 
            unit_id = None
            unit_code = _val(row, 'unit_code')
            if unit_code:
                cursor.execute(
                    "SELECT unit_id FROM lookup_units WHERE unit_code = %s", (unit_code,)
                )
                u = cursor.fetchone()
                if u:
                    unit_id = u[0]
 
            # Skip if harvest already exists for this farmer + year
            cursor.execute(
                "SELECT 1 FROM harvests_farmer_level WHERE farmer_id = %s AND harvest_year = %s LIMIT 1",
                (farmer_id, _val(row, 'harvest_year'))
            )
            if cursor.fetchone():
                skipped += 1
                continue
 
            cursor.execute("""
                INSERT INTO harvests_farmer_level (
                    farmer_id, inspection_id, harvest_year, product_type_id, unit_id,
                    previous_year_estimate_local_unit, previous_year_estimate_kg,
                    previous_year_real_local_unit, previous_year_real_kg,
                    current_year_estimate_local_unit, current_year_estimate_kg,
                    current_year_commitment_local_unit,
                    estimated_yield_local_unit_ha, real_yield_kgha, real_yield_local_unit_ha
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                farmer_id, inspection_id, _val(row, 'harvest_year'),
                product_type_id, unit_id,
                _num(row, 'previous_year_estimate_local_unit'),
                _num(row, 'previous_year_estimate_kg'),
                _num(row, 'previous_year_real_local_unit'),
                _num(row, 'previous_year_real_kg'),
                _num(row, 'current_year_estimate_local_unit'),
                _num(row, 'current_year_estimate_kg'),
                _num(row, 'current_year_commitment_local_unit'),
                _num(row, 'estimated_yield_local_unit_ha'),
                _num(row, 'real_yield_kgha'),
                _num(row, 'real_yield_local_unit_ha'),
            ))
            loaded += 1
 
            total_processed = loaded + skipped
            if total_processed % 100 == 0:
                conn.commit()
                _ping_connection(conn)
            if total_processed % 500 == 0:
                _progress(loaded, skipped, len(df), 'farmer harvests')
 
        conn.commit()
        print(f"  ✅ {loaded} farmer harvests loaded, {skipped} skipped")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def load_plot_harvests() -> bool:
    conn = create_connection()
    if not conn:
        return False
    conn.autocommit = False
    cursor = conn.cursor()
    try:
        df = pd.read_csv(OPERATIONAL / 'plot_level_harvests.csv')
        loaded = skipped = 0
        has_national_id = 'national_id' in df.columns
 
        for _, row in df.iterrows():
            farmer_id = _get_farmer_id(
                cursor,
                national_id=_val(row, 'national_id') if has_national_id else None,
                pd_farmer_id=_val(row, 'pd_farmer_id'),
            )
            if not farmer_id:
                skipped += 1
                continue
 
            cursor.execute("""
                SELECT plot_inspection_id FROM inspections_plot_level
                WHERE farmer_id = %s AND plot_name = %s AND inspection_year = %s
                ORDER BY plot_inspection_id LIMIT 1
            """, (farmer_id, _val(row, 'plot_name'), _val(row, 'harvest_year')))
            result = cursor.fetchone()
            if not result:
                skipped += 1
                continue
            plot_inspection_id = result[0]
 
            cursor.execute(
                "SELECT product_type_id FROM lookup_product_types WHERE product_code = %s",
                (_val(row, 'product_code') or 'COFFEE',)
            )
            result = cursor.fetchone()
            if not result:
                skipped += 1
                continue
            product_type_id = result[0]
 
            unit_id = None
            unit_code = _val(row, 'unit_code')
            if unit_code:
                cursor.execute(
                    "SELECT unit_id FROM lookup_units WHERE unit_code = %s", (unit_code,)
                )
                u = cursor.fetchone()
                if u:
                    unit_id = u[0]
 
            # Skip if plot harvest already exists — use plot_inspection_id as key
            cursor.execute(
                "SELECT 1 FROM harvests_plot_level WHERE plot_inspection_id = %s LIMIT 1",
                (plot_inspection_id,)
            )
            if cursor.fetchone():
                skipped += 1
                continue
 
            cursor.execute("""
                INSERT INTO harvests_plot_level (
                    farmer_id, plot_inspection_id, harvest_year, product_type_id, unit_id,
                    plot_previous_year_estimate_local_unit, plot_previous_year_estimate_kg,
                    plot_previous_year_real_local_unit, plot_previous_year_real_kg,
                    plot_current_year_estimate_local_unit, plot_current_year_estimate_kg,
                    plot_current_year_commitment_local_unit,
                    plot_estimated_yield_kgha, plot_real_yield_kgha,
                    plot_real_yield_local_unit_ha
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                farmer_id, plot_inspection_id, _val(row, 'harvest_year'),
                product_type_id, unit_id,
                _num(row, 'plot_previous_year_estimate_local_unit'),
                _num(row, 'plot_previous_year_estimate_kg'),
                _num(row, 'plot_previous_year_real_local_unit'),
                _num(row, 'plot_previous_year_real_kg'),
                _num(row, 'plot_current_year_estimate_local_unit'),
                _num(row, 'plot_current_year_estimate_kg'),
                _num(row, 'plot_current_year_commitment_local_unit'),
                _num(row, 'plot_estimated_yield_kgha'),
                _num(row, 'plot_real_yield_kgha'),
                _num(row, 'plot_real_yield_local_unit_ha'),
            ))
            loaded += 1
 
            total_processed = loaded + skipped
            if total_processed % 100 == 0:
                conn.commit()
                _ping_connection(conn)
            if total_processed % 500 == 0:
                _progress(loaded, skipped, len(df), 'plot harvests')
 
        conn.commit()
        print(f"  ✅ {loaded} plot harvests loaded, {skipped} skipped")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
def _reconnect():
    """Create a fresh connection and cursor. Used for reconnection after timeout."""
    conn = create_connection()
    if not conn:
        raise RuntimeError("Could not reconnect to MySQL")
    cursor = conn.cursor()
    return conn, cursor
 
 
def load_transactions() -> bool:
    """
    Load all 102,789 transactions.
    3-step farmer matching: national_id → pd_farmer_id → farmer_name.
    Resumes automatically if interrupted (skips already-loaded rows by index).
    Reconnects transparently if the server drops the connection mid-load.
    """
    conn, cursor = _reconnect()
 
    df = pd.read_csv(
        OPERATIONAL / 'acopio_transactions.csv',
        low_memory=False,
        keep_default_na=True,
        na_values=['', 'nan', 'NaN', 'NA'],
    )
 
    cursor.execute("SELECT COUNT(*) FROM collection_transactions")
    already_loaded = cursor.fetchone()[0]
    if already_loaded > 0:
        print(f"    Resuming from row {already_loaded} ({already_loaded} already in DB)")
 
    loaded = no_farmer = no_currency = no_product = skipped = 0
    
 
    for idx, row in df.iterrows():
        if idx < already_loaded:
            skipped += 1
            continue
 
        # Reconnect transparently if connection was dropped
        try:
            conn.ping(reconnect=True, attempts=5, delay=3)
        except Exception:
            try:
                print("    ⚠️  Reconnecting...", flush=True)
                conn, cursor = _reconnect()
            except Exception as e:
                print(f"  ❌ Could not reconnect: {e}")
                return False

        national_id = _dni_cleaner._clean_single_dni(row.get('national_id')) or None
 
        try:
            # 3-step farmer match
            farmer_id = _get_farmer_id(
                cursor,
                national_id=national_id,
                pd_farmer_id=_val(row, 'pd_farmer_id'),
            )
            if not farmer_id:
                name = _val(row, 'farmer_name')
                if name:
                    cursor.execute(
                        "SELECT farmer_id FROM farmers WHERE UPPER(farmer_name) = UPPER(%s) LIMIT 1",
                        (name,)
                    )
                    result = cursor.fetchone()
                    if result:
                        farmer_id = result[0]
 
            if not farmer_id:
                no_farmer += 1
                continue
 
            currency_code = _val(row, 'currency_code')
            if not currency_code:
                no_currency += 1
                continue
            cursor.execute(
                "SELECT currency_id FROM lookup_currencies WHERE currency_code = %s",
                (currency_code,)
            )
            currency_result = cursor.fetchone()
            if not currency_result:
                no_currency += 1
                continue
            currency_id = currency_result[0]
 
            product_code = _val(row, 'product_code') or 'COFFEE'
            cursor.execute(
                "SELECT product_type_id FROM lookup_product_types WHERE product_code = %s",
                (product_code,)
            )
            product_result = cursor.fetchone()
            if not product_result:
                no_product += 1
                continue
            product_type_id = product_result[0]
 
            unit_id = None
            unit_code = _val(row, 'transaction_unit_code')
            if unit_code:
                cursor.execute(
                    "SELECT unit_id FROM lookup_units WHERE unit_code = %s", (unit_code,)
                )
                u = cursor.fetchone()
                if u:
                    unit_id = u[0]
 
            cursor.execute("""
                INSERT INTO collection_transactions (
                    farmer_id, transaction_date, campaign_year, national_id, category,
                    product_type_id, unit_id, local_unit_quantity, kg_quantity,
                    humidity_percentage, local_unit_qty_after_hum_percentage,
                    currency_id, local_unit_price, kg_price,
                    local_currency_total_amount, kg_ha, cup_quality, processing_yield
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                farmer_id,
                _date(row, 'transaction_date'), _num(row, 'campaign_year'),
                national_id, _val(row, 'category'),
                product_type_id, unit_id,
                _num(row, 'local_unit_quantity'), _num(row, 'kg_quantity'),
                _num(row, 'humidity_percentage'),
                _num(row, 'local_unit_qty_after_hum_percentage'),
                currency_id,
                _num(row, 'local_unit_price'), _num(row, 'kg_price'),
                _num(row, 'local_currency_total_amount'),
                _num(row, 'kg_ha'), _num(row, 'cup_quality'),
                _num(row, 'processing_yield'),
            ))
            loaded += 1
 
            if loaded % 100 == 0:
                conn.commit()
            if loaded % 500 == 0:
                done = skipped + loaded + no_farmer + no_currency + no_product
                pct  = done / len(df) * 100 if len(df) else 0
                print(f"    [{pct:5.1f}%] {done:,}/{len(df):,} — {loaded:,} loaded, {no_farmer} no-farmer", flush=True)
 
        except Exception as e:
            print(f"    ⚠️  Row {idx} error: {e} — skipping", flush=True)
            try:
                conn.rollback()
            except Exception:
                pass
            continue
 
    try:
        conn.commit()
    except Exception:
        pass
 
    print(f"  ✅ {loaded} transactions loaded (resumed past {skipped})")
    if no_farmer or no_currency or no_product:
        print(f"     Skipped: {no_farmer} no-farmer, "
              f"{no_currency} no-currency, {no_product} no-product")
    cursor.close()
    conn.close()
    return True
 
 
# =============================================================================
# RESULTS
# =============================================================================
 
def show_results() -> bool:
    conn = create_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        print("\n" + "=" * 60)
        print("FINAL TABLE COUNTS")
        print("=" * 60)
        tables = [
            'lookup_currencies', 'lookup_genders', 'lookup_product_types',
            'lookup_units', 'lookup_countries', 'producer_organizations',
            'farmers', 'farmer_addresses',
            'inspections_farmer_level', 'inspections_plot_level',
            'harvests_farmer_level', 'harvests_plot_level',
            'collection_transactions',
        ]
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table:<35} {count:>9,}")
        return True
    except Exception as e:
        print(f"  ❌ {e}")
        return False
    finally:
        cursor.close()
        conn.close()
 
 
# =============================================================================
# ORCHESTRATOR
# =============================================================================
 
def load_all_data(
    clear_main: bool = True,
    clear_lookup: bool = False,
) -> bool:
    """
    Run the full Stage 3 migration in dependency order.
 
    Args:
        clear_main:    Delete and reload all non-lookup tables (default True).
                       Set False to resume after a partial run without losing progress.
        clear_lookup:  Also delete and reload lookup tables (default False).
                       Only needed for a completely fresh database.
 
    To skip individual steps after a partial failure, comment out the
    relevant tuple in the steps list below — each loader is independent.
    """
    print("=" * 60)
    print("STAGE 3: SDL MIGRATION")
    print("=" * 60)
 
    steps = [
        # ── Clear main tables FIRST (before lookups — FK constraint order) ─
        # ("Clear main tables",         clear_existing_data,      clear_main),
        # ── Clear lookup tables (safe now that main tables are empty) ────
        # ("Clear lookup tables",       clear_lookup_data,        clear_lookup),
        # ── Reload lookup tables ─────────────────────────────────────────
        # ("Load currencies",           load_currencies,          True),
        # ("Load genders",              load_genders,             True),
        # ("Load product types",        load_product_types,       True),
        # ("Load countries",            load_countries,           True),
        # ("Load units",                load_units,               True),
        # ── Master ───────────────────────────────────────────────────────
        # ("Load organizations",        load_organizations,       True),
        #  ("Load farmers",              load_farmers,             True),  # done
        # ── Operational ──────────────────────────────────────────────────
        #  ("Load farmer addresses",     load_farmer_addresses,    True),  # done
        # ("Load farmer inspections",   load_farmer_inspections,  True),  # done
        # ("Load plot inspections",     load_plot_inspections,    True),
        # ("Load farmer harvests",      load_farmer_harvests,     True),
        # ("Load plot harvests",        load_plot_harvests,       True),
        # ("Load transactions",         load_transactions,        True),
        # ── Summary ──────────────────────────────────────────────────────
        ("Show results",              show_results,             True),
    ]
 
    for step_name, step_func, should_run in steps:
        if not should_run:
            print(f"\n  ⏭  Skipping: {step_name}")
            continue
        print(f"\n── {step_name} {'─' * max(0, 44 - len(step_name))}")
        if not step_func():
            print(f"\n❌ FAILED at: {step_name}")
            print("   Fix the issue and re-run with clear_main=False to resume.")
            return False
 
    print("\n" + "=" * 60)
    print("✅ STAGE 3 MIGRATION COMPLETE")
    print("=" * 60)
    return True