"""
Data Integrator - Stage 2 Main Orchestrator
=============================================
Orchestrates the full Stage 2 pipeline:
 
    1.  Create lookup tables
    2.  Transform each PO into farmer-level + plot-level DataFrames
    3.  Split into identity view (1 row/farmer) and temporal view (1 row/farmer/year)
    4.  Extract inspection-based MySQL tables (farmers_data, inspections, harvests, plots)
    5.  Integrate Norandino membership (BEFORE transaction linking)
    6.  Build acopio transactions table
    7.  Link transactions → farmers (membership farmers now findable)
    8.  Add remaining unmatched transaction farmers as External
    9.  Extract farmers_addresses from complete farmers table (after all additions)
    10. Export all tables to data/mysql_ready/ as CSV
 
The identity/temporal split is the key architectural fix for Chirinos multi-year data:
 
    all_farmers_temporal  →  farmer_level_inspections, farmer_level_harvests
                             (1 row per farmer per year — Chirinos contributes 5 rows/farmer)
 
    all_farmers_identity  →  farmers_data, farmers_addresses
                             (1 row per farmer — deduplicated to latest inspection year)
 
Usage:
    from src.stage2_integration.data_integrator import create_all_mysql_ready_datasets
 
    mysql_tables = create_all_mysql_ready_datasets()
"""
 
import os
import pandas as pd
import numpy as np
from pathlib import Path
from fuzzywuzzy import fuzz, process
 
# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent
 
INSPECTIONS_DIR  = PROJECT_ROOT / 'data' / 'processed' / 'inspections'
TRANSACTIONS_DIR = PROJECT_ROOT / 'data' / 'processed' / 'transactions'
MYSQL_READY_DIR  = PROJECT_ROOT / 'data' / 'mysql_ready'
 
# Subfolders within mysql_ready — mirrors SDL database schema grouping
MYSQL_READY_MASTER      = MYSQL_READY_DIR / 'master'       # core entity tables
MYSQL_READY_OPERATIONAL = MYSQL_READY_DIR / 'operational'  # transactional tables
MYSQL_READY_LOOKUP      = MYSQL_READY_DIR / 'lookup'       # reference/lookup tables
 
# Table → subfolder routing
MYSQL_READY_ROUTING = {
    # Master: core farmer and organisation identity
    'farmers_data':             MYSQL_READY_MASTER,
    'lookup_producer_orgs':     MYSQL_READY_MASTER,
 
    # Operational: addresses, transactions, inspections, harvests
    'farmers_addresses':        MYSQL_READY_OPERATIONAL,
    'acopio_transactions':      MYSQL_READY_OPERATIONAL,
    'farmer_level_inspections': MYSQL_READY_OPERATIONAL,
    'plot_level_inspections':   MYSQL_READY_OPERATIONAL,
    'farmer_level_harvests':    MYSQL_READY_OPERATIONAL,
    'plot_level_harvests':      MYSQL_READY_OPERATIONAL,
 
    # Lookup: static reference tables
    'lookup_countries':         MYSQL_READY_LOOKUP,
    'lookup_genders':           MYSQL_READY_LOOKUP,
    'lookup_product_types':     MYSQL_READY_LOOKUP,
    'lookup_units':             MYSQL_READY_LOOKUP,
    'lookup_currencies':        MYSQL_READY_LOOKUP,
}
 
# Confirmed filenames from Stage 1 cleaners
INSPECTION_PATHS = {
    'bagua':     INSPECTIONS_DIR  / 'bagua'     / 'clean_bagua_LPA_NEW.pkl',
    'huadquina': INSPECTIONS_DIR  / 'huadquina' / 'huadquina_inspections_clean.pkl',
    'chirinos':  INSPECTIONS_DIR  / 'chirinos'  / 'chirinos_inspections_clean.pkl',
    'norandino': INSPECTIONS_DIR  / 'norandino' / 'norandino_inspections_clean.pkl',
    'aprocassi': INSPECTIONS_DIR  / 'aprocassi' / 'aprocassi_inspections_clean.pkl',
    # Wide-format Norandino file needed by plot transformer
    'norandino_wide': INSPECTIONS_DIR / 'norandino' / 'norandino_with_all_plots_data.pkl',
}
 
TRANSACTION_PATHS = {
    'bagua':     TRANSACTIONS_DIR / 'bagua'     / 'bagua_transactions_NEW.pkl',
    'huadquina': TRANSACTIONS_DIR / 'huadquina' / 'huadquina_transactions_clean.pkl',
    'chirinos':  TRANSACTIONS_DIR / 'chirinos'  / 'chirinos_transactions_clean.pkl',
    'norandino': TRANSACTIONS_DIR / 'norandino' / 'norandino_transactions_clean.pkl',
    'aprocassi': TRANSACTIONS_DIR / 'aprocassi' / 'aprocassi_transactions_clean.pkl',
}
 
# Optional membership files (only Norandino has provided this)
RAW_DIR = PROJECT_ROOT / 'data' / 'raw'
MEMBERSHIP_PATHS = {
    # File stored alongside raw inspection files as received from Norandino
    'norandino': RAW_DIR / 'inspections' / 'norandino' / 'MEMBRESIA COOP NORANDINO 13.10.25.xlsx',
}
MEMBERSHIP_SHEET   = {'norandino': 'membresia 2025'}
MEMBERSHIP_HEADER  = {'norandino': 7}   # row index 7 = Excel row 8 (0-based)
 
# ---------------------------------------------------------------------------
# Stage 2 module imports
# ---------------------------------------------------------------------------
from src.stage2_integration.po_transformers import (
    create_bagua_farmer_level_dataset,
    create_bagua_plot_level_dataset,
    create_huadquina_farmer_level_dataset,
    create_huadquina_plot_level_dataset,
    create_chirinos_farmer_level_dataset,
    create_norandino_farmer_level_dataset,
    create_norandino_plot_level_dataset,
    create_aprocassi_farmer_level_dataset,
    create_aprocassi_plot_level_dataset,
)
from src.stage2_integration.table_extractor import (
    extract_farmers_data_table,
    extract_farmer_addresses_table,
    extract_farmer_level_inspections_table,
    extract_plot_level_inspections_table,
    extract_farmer_level_harvests_table,
    extract_plot_level_harvests_table,
)
from src.stage2_integration.transactions_processor import create_acopio_transactions_table
from src.utils.mapping_helpers import map_gender_to_id
 
 
# =============================================================================
# LOOKUP TABLES
# =============================================================================
 
def create_lookup_tables() -> tuple:
    """
    Create all static lookup DataFrames needed for foreign key mapping.
 
    Returns:
        (lookup_countries, lookup_producer_orgs, lookup_genders,
         lookup_product_types, lookup_units, lookup_currencies)
    """
    lookup_countries = pd.DataFrame({
        'country_name':        ['Peru', 'Uganda', 'Nicaragua', 'Mexico',
                                'Honduras', 'Brazil', 'Colombia'],
        'country_code':        ['PER', 'UGA', 'NI', 'MX', 'HN', 'BR', 'CO'],
        'currency_code':       ['PEN', 'UGX', 'NIO', 'MXN', 'HNL', 'BRL', 'COP'],
        'phone_country_code':  ['+51', '+256', '+505', '+52', '+504', '+55', '+57'],
    })
 
    lookup_producer_orgs = pd.DataFrame({
        'org_name':    ['Bagua Grande', 'Huadquiña', 'Chirinos', 'Norandino', 'Aprocassi'],
        'country_code':['PER', 'PER', 'PER', 'PER', 'PER'],
        'org_code':    ['BG', 'HU', 'CH', 'NO', 'AP'],
        'flo_id':      ['859', '28000', '921', '18075', '912'],
    })
 
    lookup_genders = pd.DataFrame({
        'gender_code': ['M', 'F', 'O'],
        'gender_name': ['Male', 'Female', 'Other'],
        'is_active':   [True, True, True],
    })
 
    lookup_product_types = pd.DataFrame({
        'product_code': ['COFFEE', 'CACAO', 'PANELA', 'OTHER'],
        'product_name': ['Café', 'Cacao', 'Panela', 'Otros'],
        'is_active':    [True, True, True, True],
    })
 
    lookup_units = pd.DataFrame({
        'unit_code':          ['KG', 'QQ', 'TM'],
        'unit_name':          ['Kilogramos', 'Quintales', 'Toneladas Métricas'],
        'kg_conversion_rate': [1.0, 55.2, 1000.0],
        'country_primary':    ['PER', 'PER', 'PER'],
        'is_active':          [True, True, True],
    })
 
    lookup_currencies = pd.DataFrame({
        'currency_code':   ['USD', 'PEN', 'UGX', 'NIO', 'MXN', 'HNL', 'BRL', 'COP'],
        'currency_name':   ['US Dollar', 'Peruvian Sol', 'Ugandan Shilling',
                            'Nicaraguan Córdoba', 'Mexican Peso', 'Honduran Lempira',
                            'Brazilian Real', 'Colombian Peso'],
        'currency_symbol': ['$', 'S/', 'USh', 'C$', '$', 'L', 'R$', '$'],
        'is_active':       [True, True, True, True, True, True, True, True],
    })
 
    return (lookup_countries, lookup_producer_orgs, lookup_genders,
            lookup_product_types, lookup_units, lookup_currencies)
 
 
# =============================================================================
# INTERNAL HELPERS
# =============================================================================
 
def _load_pkl(path: Path, label: str) -> pd.DataFrame:
    """Load a pickle file with a clear error if not found."""
    if not path.exists():
        raise FileNotFoundError(
            f"❌ {label} file not found: {path}\n"
            f"   Run Stage 1 cleaners before Stage 2."
        )
    df = pd.read_pickle(path)
    print(f"  ✅ Loaded {label}: {len(df):,} rows")
    return df
 
 
def _build_plot_name_for_empty(all_plot_level_combined: pd.DataFrame) -> pd.DataFrame:
    """
    Generate 'Parcela N' names for plot rows where plot_name is empty/null.
    Mirrors notebook_4 logic exactly.
    """
    df = all_plot_level_combined.copy()
    empty_mask = df['plot_name'].isna() | (df['plot_name'] == '')
 
    for farmer_id in df[empty_mask]['pd_farmer_id'].unique():
        farmer_mask = (df['pd_farmer_id'] == farmer_id) & empty_mask
        farmer_plots = df[farmer_mask].sort_values('total_area_ha', ascending=False)
 
        for idx_pos, (original_idx, _) in enumerate(farmer_plots.iterrows(), start=1):
            df.loc[original_idx, 'plot_name'] = f"Parcela {idx_pos}"
 
    remaining = (df['plot_name'].isna() | (df['plot_name'] == '')).sum()
    print(f"  ✅ Generated plot names. Remaining empty: {remaining}")
    return df
 
 
def _deduplicate_and_disambiguate_plots(
    plot_table: pd.DataFrame,
    expected_counts: pd.DataFrame,
    label: str
) -> pd.DataFrame:
    """
    For each farmer:
      - If actual == expected: disambiguate duplicate plot names with '#N' suffix
      - If actual >  expected: remove exact-duplicate rows
      - If actual <  expected: log as data issue (missing plots)
 
    Used for both plot_level_inspections and plot_level_harvests.
    """
    if plot_table.empty:
        return plot_table
 
    df = plot_table.copy()
    df['plot_name'] = df['plot_name'].str.strip().str.title()
 
    true_dups_removed  = 0
    plots_disambiguated = 0
    mismatches         = []
 
    # Columns used to identify true duplicates (inspections vs harvests differ)
    if 'plot_area_ha' in df.columns:
        dup_subset = ['pd_farmer_id', 'plot_name', 'inspection_year',
                      'product_code', 'latitude', 'longitude', 'plot_area_ha']
    else:
        dup_subset = ['pd_farmer_id', 'plot_name', 'harvest_year',
                      'product_code', 'unit_code']
 
    for farmer_id in df['pd_farmer_id'].unique():
        farmer_plots   = df[df['pd_farmer_id'] == farmer_id]
        expected_row   = expected_counts[expected_counts['pd_farmer_id'] == farmer_id]['number_of_plots'].values
        expected_count = int(expected_row[0]) if len(expected_row) > 0 and pd.notna(expected_row[0]) else None
        actual_count   = len(farmer_plots)
 
        if expected_count is None:
            continue
 
        if actual_count == expected_count:
            # Disambiguate duplicate names within this farmer's plots
            dup_names = farmer_plots.groupby('plot_name').size()
            dup_names = dup_names[dup_names > 1].index
 
            for dup_name in dup_names:
                dup_mask    = (df['pd_farmer_id'] == farmer_id) & (df['plot_name'] == dup_name)
                dup_indices = df[dup_mask].index
                for i, idx in enumerate(dup_indices, 1):
                    if i > 1:
                        df.loc[idx, 'plot_name'] = f"{dup_name} #{i}"
                        plots_disambiguated += 1
 
        elif actual_count > expected_count:
            # Remove exact duplicates
            farmer_mask = df['pd_farmer_id'] == farmer_id
            farmer_data = df[farmer_mask]
            existing_dup_subset = [c for c in dup_subset if c in df.columns]
            dup_mask    = farmer_data.duplicated(subset=existing_dup_subset, keep='first')
            removed     = int(dup_mask.sum())
            true_dups_removed += removed
 
            df = df[~((df['pd_farmer_id'] == farmer_id) &
                       df.index.isin(farmer_data[dup_mask].index))]
 
        else:
            mismatches.append({
                'farmer_id': farmer_id,
                'expected':  expected_count,
                'actual':    actual_count,
                'missing':   expected_count - actual_count,
            })
 
    print(f"  ✅ [{label}] True duplicates removed: {true_dups_removed}")
    print(f"  ✅ [{label}] Plots disambiguated: {plots_disambiguated}")
    if mismatches:
        print(f"  ⚠️  [{label}] {len(mismatches)} farmers have fewer plots than expected:")
        for m in mismatches[:10]:
            print(f"      Farmer {m['farmer_id']}: expected {m['expected']}, "
                  f"found {m['actual']} (missing {m['missing']})")
 
    return df
 
 
def _link_transactions_to_farmers(
    transactions_df: pd.DataFrame,
    farmers_data_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Attach pd_farmer_id to every transaction row using a 3-stage matching strategy:
        Match 1: national_id (DNI) exact match
        Match 2: exact farmer_name + org_code match
        Match 3: fuzzy farmer_name match per org (threshold 90%)
 
    Returns transactions DataFrame with pd_farmer_id column populated where possible.
    """
    df = transactions_df.copy()
    df['pd_farmer_id'] = None
 
    # --- Match 1: national_id ---
    print("  Matching by national_id...")
    has_id = df['national_id'].notna() & (df['national_id'] != '')
 
    if has_id.sum() > 0:
        farmers_lookup = (
            farmers_data_df[['national_id', 'pd_farmer_id']]
            .dropna(subset=['national_id'])
            # Deduplicate national_id — prefer rows with a real pd_farmer_id
            # (membership farmers have pd_farmer_id=None; inspection farmers have real IDs)
            .sort_values('pd_farmer_id', na_position='last')
            .drop_duplicates(subset=['national_id'], keep='first')
        )
        merged = df[has_id].merge(
            farmers_lookup, on='national_id', how='left', suffixes=('', '_matched')
        )
        id_col = 'pd_farmer_id_matched' if 'pd_farmer_id_matched' in merged.columns else 'pd_farmer_id'
        df.loc[has_id, 'pd_farmer_id'] = merged[id_col].values
        matched = df.loc[has_id, 'pd_farmer_id'].notna().sum()
        print(f"  ✅ Matched {matched:,} transactions by national_id")
 
    # --- Match 2: exact name + org_code ---
    print("  Matching by exact name + org_code...")
    no_match = df['pd_farmer_id'].isna()
 
    if no_match.sum() > 0:
        df['_name_norm']         = df['farmer_name'].str.upper().str.strip()
        farmers_tmp              = farmers_data_df.copy()
        farmers_tmp['_name_norm'] = farmers_tmp['farmer_name'].str.upper().str.strip()
 
        name_merged = df[no_match].merge(
            farmers_tmp[['_name_norm', 'org_code', 'pd_farmer_id']],
            on=['_name_norm', 'org_code'], how='left', suffixes=('', '_matched')
        )
        id_col = 'pd_farmer_id_matched' if 'pd_farmer_id_matched' in name_merged.columns else 'pd_farmer_id'
        for idx, farmer_id in zip(name_merged.index, name_merged[id_col]):
            if pd.notna(farmer_id):
                df.at[idx, 'pd_farmer_id'] = farmer_id
 
        df.drop(columns=['_name_norm'], inplace=True, errors='ignore')
        name_matched = (~no_match & df['pd_farmer_id'].notna()).sum() - (has_id & df['pd_farmer_id'].notna()).sum()
        print(f"  ✅ Matched {name_matched:,} additional transactions by exact name")
 
    # --- Match 3: fuzzy name per org (90% threshold) ---
    print("  Attempting fuzzy name matching (threshold: 90%)...")
    still_no_match = df['pd_farmer_id'].isna()
 
    if still_no_match.sum() > 0:
        fuzzy_matched = 0
 
        for org_code in ['BG', 'HU', 'CH', 'NO', 'AP']:
            org_mask = still_no_match & (df['org_code'] == org_code)
            if org_mask.sum() == 0:
                continue
 
            org_farmers = farmers_data_df[
                (farmers_data_df['org_code'] == org_code) &
                farmers_data_df['farmer_name'].notna()
            ].copy()
            if len(org_farmers) == 0:
                continue
 
            farmer_names = org_farmers['farmer_name'].str.upper().str.strip().tolist()
            name_to_id   = dict(zip(
                org_farmers['farmer_name'].str.upper().str.strip(),
                org_farmers['pd_farmer_id']
            ))
 
            for idx in df[org_mask].index:
                tx_name = df.at[idx, 'farmer_name']
                if pd.isna(tx_name):
                    continue
                best = process.extractOne(
                    str(tx_name).upper().strip(), farmer_names, scorer=fuzz.ratio
                )
                if best and best[1] >= 90:
                    df.at[idx, 'pd_farmer_id'] = name_to_id[best[0]]
                    fuzzy_matched += 1
 
        print(f"  ✅ Matched {fuzzy_matched:,} additional transactions by fuzzy name")
 
    total_matched   = df['pd_farmer_id'].notna().sum()
    total_unmatched = df['pd_farmer_id'].isna().sum()
    print(f"\n  📊 Linking summary:")
    print(f"     ✅ Transactions with pd_farmer_id: {total_matched:,}")
    print(f"     ⚠️  Transactions without pd_farmer_id: {total_unmatched:,}")
 
    return df
 
 
def _add_new_farmers_from_transactions(
    transactions_df: pd.DataFrame,
    farmers_data_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Identify transactions still unmatched after all linking attempts.
    Create minimal farmer records for them and append to farmers_data.
 
    Returns:
        (updated_transactions_df, updated_farmers_data_df)
    """
    final_unmatched = transactions_df['pd_farmer_id'].isna()
    print(f"  Found {final_unmatched.sum():,} transactions with no farmer match")
 
    if final_unmatched.sum() == 0:
        return transactions_df, farmers_data_df
 
    new_farmers_raw = (
        transactions_df[final_unmatched][['national_id', 'farmer_name', 'org_code']]
        .drop_duplicates()
    )
    print(f"  Unique new farmers to add: {len(new_farmers_raw)}")
    print(f"\n  Breakdown by org:")
    print(new_farmers_raw['org_code'].value_counts().to_string())
 
    existing_ids      = set(farmers_data_df['national_id'].dropna())
    unknown_counters  = {'BG': 0, 'HU': 0, 'CH': 0, 'NO': 0, 'AP': 0}
    new_farmers_list  = []
    skipped_count     = 0
 
    for _, row in new_farmers_raw.iterrows():
        nat_id = row['national_id']
        org    = row['org_code']
 
        if pd.isna(nat_id) or nat_id == '':
            unknown_counters[org] += 1
            synthetic_id = f"UNKNOWN_{org}_{unknown_counters[org]}"
        else:
            synthetic_id = nat_id
            if synthetic_id in existing_ids:
                skipped_count += 1
                continue
 
        new_farmers_list.append({
            'pd_farmer_id':    None,
            'national_id':     synthetic_id,
            'farmer_name':     row['farmer_name'] if pd.notna(row['farmer_name']) else None,
            'org_code':        org,
            'telephone':       None,
            'gender_code':     None,
            'birth_date':      None,
            'base':            None,
            'member_status':   'External',
            'entry_date':      None,
            'membership_number': None,
        })
        existing_ids.add(synthetic_id)
 
    if skipped_count > 0:
        print(f"  ℹ️  Skipped {skipped_count} already-existing national_ids (found via membership/inspections)")
 
    if new_farmers_list:
        updated_farmers = pd.concat(
            [farmers_data_df, pd.DataFrame(new_farmers_list)],
            ignore_index=True
        )
        print(f"  ✅ Added {len(new_farmers_list)} new farmers")
        print(f"  Farmers table now has {len(updated_farmers):,} records")
 
        if sum(unknown_counters.values()) > 0:
            print(f"\n  Unknown farmers created:")
            for org, count in unknown_counters.items():
                if count > 0:
                    print(f"    {org}: {count} synthetic IDs")
    else:
        updated_farmers = farmers_data_df
        print(f"  ℹ️  No new farmers to add (all were duplicates)")
 
    return transactions_df, updated_farmers
 
 
 
def _integrate_norandino_membership(
    farmers_data_df: pd.DataFrame,
    membership_df: pd.DataFrame,
    lookup_genders: pd.DataFrame,
) -> pd.DataFrame:
    """
    Integrate Norandino membership file into farmers_data table.
 
    Source file: 'MEMBRESIA COOP NORANDINO 13.10.25.xlsx'
    Sheet:       'membresia 2025'
    Header row:  7 (index 6)
 
    Columns used from membership file (others are dropped):
        'Cédula,  Némero o Código del Productor ' → national_id
        'Nombre Productor '                        → farmer_name
        'Teléfono'                                 → telephone
        'Sexo'                                     → gender (mapped to gender_code)
        'Fecha Nacimiento'                         → birth_date
        'Fecha Incorporación'                      → entry_date
        'Estatus de miembro (hábil, inhábil...)'   → member_status
        'Distrito'                                 → district  (for farmers_addresses)
        'Provincia'                                → province  (for farmers_addresses)
        'Departamento'                             → department (for farmers_addresses)
 
    Three scenarios handled:
        B: Farmer already in farmers_data with member_status='External'
           → Correct status to actual value from membership file
        C: Member in membership file but not in farmers_data at all
           → Add as new farmer record (addresses handled in extract_farmer_addresses_table)
 
    Args:
        farmers_data_df:  Current farmers_data table
        membership_df:    Raw Norandino membership DataFrame (already loaded from Excel)
 
    Returns:
        Updated farmers_data DataFrame.
    """
    print(f"  Input: {len(farmers_data_df):,} farmers in table, "
          f"{len(membership_df):,} Norandino members in file")
 
    # ------------------------------------------------------------------
    # Step 1: Normalise column names
    # Strip whitespace AND normalise unicode (handles accents from Excel)
    # ------------------------------------------------------------------
    import unicodedata
 
    def _norm_col(s: str) -> str:
        """Strip whitespace and normalise unicode for column matching."""
        s = str(s).strip()
        # Normalise unicode — handles cases where accented chars differ in encoding
        s = unicodedata.normalize('NFC', s)
        return s
 
    membership_df = membership_df.copy()
    # Apply normalisation to all column names
    membership_df.columns = [_norm_col(c) for c in membership_df.columns]
 
    # Columns to keep and their target names
    # Keys are also normalised so they match the normalised column names above
    COLUMN_MAP = {
        _norm_col('Cédula,  Némero o Código del Productor'): 'national_id',
        _norm_col('Nombre Productor'):                        'farmer_name',
        _norm_col('Teléfono'):                                'telephone',
        _norm_col('Sexo'):                                    'gender',
        _norm_col('Fecha Nacimiento'):                        'birth_date',
        _norm_col('Fecha Incorporación'):                     'entry_date',
        _norm_col('Estatus de miembro (hábil, inhábil, pre socio, etc.)'): 'member_status',
        _norm_col('Distrito'):                                'district',
        _norm_col('Provincia'):                               'province',
        _norm_col('Departamento'):                            'department',
    }
 
    # Keep only columns we need, rename them
    existing_map = {k: v for k, v in COLUMN_MAP.items() if k in membership_df.columns}
    missing = [k for k in COLUMN_MAP if k not in membership_df.columns]
    if missing:
        print(f"  ⚠️  These expected membership columns were not found (after normalisation):")
        for m in missing:
            print(f"    '{m}'")
        print(f"  ℹ️  Check the printed column list above and update COLUMN_MAP if needed.")
 
    if not existing_map:
        print("  ❌ No membership columns could be matched — skipping membership integration")
        return farmers_data_df
 
    membership_df = membership_df[list(existing_map.keys())].rename(columns=existing_map)
 
    # ------------------------------------------------------------------
    # Step 2: Clean national_id
    # ------------------------------------------------------------------
    membership_df['national_id'] = (
        membership_df['national_id']
        .astype(str).str.strip()
        .str.replace(r'\.0$', '', regex=True)   # remove float .0 suffix if read as numeric
        .str.zfill(8)
    )
    # Guard: national_id column must exist after rename
    if 'national_id' not in membership_df.columns:
        print("  ❌ national_id column not found after rename — skipping membership integration")
        return farmers_data_df
 
    # Drop rows with no usable ID
    membership_df = membership_df[
        membership_df['national_id'].notna() &
        (membership_df['national_id'] != '') &
        (membership_df['national_id'] != '00000000') &
        (membership_df['national_id'] != 'nan')
    ].copy()
 
    # Clean farmer_name
    if 'farmer_name' in membership_df.columns:
        membership_df['farmer_name'] = (
            membership_df['farmer_name'].astype(str).str.strip().str.upper()
        )
 
    # Map gender text → gender_code using the shared lookup table
    if 'gender' in membership_df.columns:
        membership_df['gender_code'] = map_gender_to_id(
            membership_df['gender'].astype(str), lookup_genders
        )
        membership_df.drop(columns=['gender'], inplace=True)
 
    membership_df['org_code']     = 'NO'
    membership_df['country_code'] = 'PER'
 
    print(f"  Membership file after cleaning: {len(membership_df):,} valid records")
 
    # ------------------------------------------------------------------
    # Step 3: Scenario B — fix 'External' status for known members
    # farmers_data national_id is already canonical (8-digit string from DNICleaner).
    # membership_df national_id was normalised to match in Step 2 above.
    # Do NOT re-normalise farmers_data — it is the authoritative source.
    # ------------------------------------------------------------------
    scenario_b_fixed = 0
    if 'member_status' in membership_df.columns:
        status_lookup = dict(zip(membership_df['national_id'], membership_df['member_status']))
 
        b_mask = (
            (farmers_data_df['org_code'] == 'NO') &
            (farmers_data_df['member_status'] == 'External') &
            farmers_data_df['national_id'].isin(status_lookup)
        )
        farmers_data_df.loc[b_mask, 'member_status'] = (
            farmers_data_df.loc[b_mask, 'national_id'].map(status_lookup)
        )
        scenario_b_fixed = int(b_mask.sum())
    print(f"  ✅ Scenario B: {scenario_b_fixed} 'External' statuses corrected")
 
    # ------------------------------------------------------------------
    # Step 5: Scenario C — add members not yet in farmers_data at all
    # ------------------------------------------------------------------
    existing_no_ids = set(
        farmers_data_df[farmers_data_df['org_code'] == 'NO']['national_id'].dropna()
    )
    new_members = membership_df[
        ~membership_df['national_id'].isin(existing_no_ids)
    ].copy()
 
    # Deduplicate membership file itself — some files list the same farmer twice
    before_dedup = len(new_members)
    new_members = new_members.drop_duplicates(subset=['national_id'], keep='first')
    if len(new_members) < before_dedup:
        print(f"  ℹ️  Removed {before_dedup - len(new_members)} duplicate national_ids from membership file")
 
    print(f"  Scenario C: {len(new_members):,} members not yet in farmers_data")
 
    if len(new_members) > 0:
        # Columns that belong in farmers_data (not farmers_addresses)
        FARMERS_DATA_COLS = [
            'national_id', 'farmer_name', 'telephone', 'gender_code',
            'birth_date', 'entry_date', 'member_status',
            'org_code', 'country_code',
        ]
        keep = [c for c in FARMERS_DATA_COLS if c in new_members.columns]
        new_records = new_members[keep].copy()
        new_records['pd_farmer_id']      = None
        new_records['membership_number'] = None
        new_records['base']              = None
 
        # Carry district/province/department so farmers_addresses can use them
        # (they travel as extra columns — extract_farmer_addresses_table reads them)
        for addr_col in ['district', 'province', 'department']:
            if addr_col in new_members.columns:
                new_records[addr_col] = new_members[addr_col].values
 
        farmers_data_df = pd.concat(
            [farmers_data_df, new_records], ignore_index=True
        )
        print(f"  ✅ Scenario C: {len(new_records):,} new Norandino members added")
 
    print(f"  Farmers table after membership integration: {len(farmers_data_df):,} records")
    return farmers_data_df
 
 
# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================
 
def create_all_mysql_ready_datasets(
    export_csv: bool = True,
    bagua_fuzzy_threshold: float = 0.85,
    bagua_bad_matches: list[str] | None = None,
    norandino_membership_df: 'pd.DataFrame | None' = None,
) -> dict:
    """
    Full Stage 2 pipeline: load → transform → extract → link → export.
 
    Args:
        export_csv:                 Save all tables as CSV to data/mysql_ready/ (default True)
        bagua_fuzzy_threshold:      Fuzzy match threshold for Bagua DNI resolution (default 0.85)
        bagua_bad_matches:          Known false-positive names to clear after Bagua fuzzy match
        norandino_membership_df:    Optional Norandino membership DataFrame. When provided,
                                    corrects 'External' statuses for known members (Scenario B)
                                    and adds members with no inspections/transactions (Scenario C).
                                    Load with: pd.read_excel(MEMBERSHIP_PATHS['norandino'])
                                    Pass None to skip this step (default).
 
    Returns:
        Dictionary of all MySQL-ready DataFrames:
            farmers_data, farmers_addresses,
            farmer_level_inspections, plot_level_inspections,
            farmer_level_harvests, plot_level_harvests,
            acopio_transactions,
            lookup_countries, lookup_producer_orgs, lookup_genders,
            lookup_product_types, lookup_units, lookup_currencies
    """
    print("=" * 70)
    print("STAGE 2: CREATING ALL MYSQL-READY DATASETS")
    print("=" * 70)
 
    # -----------------------------------------------------------------------
    # Step 1: Load all Stage 1 outputs
    # -----------------------------------------------------------------------
    print("\n── Step 1: Loading Stage 1 outputs ──────────────────────────────────")
 
    bagua_inspections_df     = _load_pkl(INSPECTION_PATHS['bagua'],     'Bagua inspections')
    hu_inspections_df        = _load_pkl(INSPECTION_PATHS['huadquina'], 'Huadquiña inspections')
    chirinos_inspections_df  = _load_pkl(INSPECTION_PATHS['chirinos'],  'Chirinos inspections')
    norandino_inspections_df = _load_pkl(INSPECTION_PATHS['norandino'], 'Norandino inspections')
    aprocassi_inspections_df = _load_pkl(INSPECTION_PATHS['aprocassi'], 'Aprocassi inspections')
 
    bagua_acopio_df     = _load_pkl(TRANSACTION_PATHS['bagua'],     'Bagua transactions')
    hu_acopio_df        = _load_pkl(TRANSACTION_PATHS['huadquina'], 'Huadquiña transactions')
    chirinos_acopio_df  = _load_pkl(TRANSACTION_PATHS['chirinos'],  'Chirinos transactions')
    norandino_acopio_df = _load_pkl(TRANSACTION_PATHS['norandino'], 'Norandino transactions')
    aprocassi_acopio_df = _load_pkl(TRANSACTION_PATHS['aprocassi'], 'Aprocassi transactions')
 
    # -----------------------------------------------------------------------
    # Step 2: Create lookup tables
    # -----------------------------------------------------------------------
    print("\n── Step 2: Creating lookup tables ───────────────────────────────────")
    (lookup_countries, lookup_producer_orgs, lookup_genders,
     lookup_product_types, lookup_units, lookup_currencies) = create_lookup_tables()
    print("  ✅ Lookup tables created")
 
    # -----------------------------------------------------------------------
    # Step 3: PO transformer — farmer-level datasets
    # -----------------------------------------------------------------------
    print("\n── Step 3: Creating farmer-level datasets per PO ────────────────────")
    bagua_farmers,     bagua_needs_plots     = create_bagua_farmer_level_dataset(bagua_inspections_df, lookup_genders)
    hu_farmers,        hu_needs_plots        = create_huadquina_farmer_level_dataset(hu_inspections_df, lookup_genders)
    chirinos_farmers,  _                     = create_chirinos_farmer_level_dataset(chirinos_inspections_df, lookup_genders)
    norandino_farmers                        = create_norandino_farmer_level_dataset(norandino_inspections_df, lookup_genders)
    aprocassi_farmers, aprocassi_needs_plots = create_aprocassi_farmer_level_dataset(aprocassi_inspections_df, lookup_genders)
    print("  ✅ All PO farmer datasets created")
 
    # -----------------------------------------------------------------------
    # Step 4: PO transformer — plot-level datasets
    # -----------------------------------------------------------------------
    print("\n── Step 4: Creating plot-level datasets per PO ──────────────────────")
    plot_tables = []
 
    if bagua_needs_plots:
        print("  Creating Bagua Grande plots...")
        bagua_plots = create_bagua_plot_level_dataset(bagua_inspections_df, lookup_genders)
        plot_tables.append(bagua_plots)
        print(f"  ✅ Bagua plots: {len(bagua_plots):,} records")
 
    if hu_needs_plots:
        print("  Creating Huadquiña plots...")
        hu_plots = create_huadquina_plot_level_dataset(hu_inspections_df, lookup_genders)
        plot_tables.append(hu_plots)
        print(f"  ✅ Huadquiña plots: {len(hu_plots):,} records")
 
    # Chirinos: no plot-level data — create_chirinos_plot_level_dataset returns empty df
    # (intentionally not called here)
 
    print("  Creating Norandino plots (unpivot wide format)...")
    norandino_plots = create_norandino_plot_level_dataset(
        INSPECTION_PATHS['norandino_wide'], lookup_genders
    )
    plot_tables.append(norandino_plots)
    print(f"  ✅ Norandino plots: {len(norandino_plots):,} records")
 
    if aprocassi_needs_plots:
        print("  Creating Aprocassi plots...")
        aprocassi_plots = create_aprocassi_plot_level_dataset(aprocassi_inspections_df, lookup_genders)
        plot_tables.append(aprocassi_plots)
        print(f"  ✅ Aprocassi plots: {len(aprocassi_plots):,} records")
 
    # -----------------------------------------------------------------------
    # Step 5: Combine — temporal (all years) and identity (latest year)
    # -----------------------------------------------------------------------
    print("\n── Step 5: Combining farmer datasets ────────────────────────────────")
 
    # Temporal: all rows from all POs (Chirinos contributes N rows/farmer)
    all_farmers_temporal = pd.concat(
        [bagua_farmers, hu_farmers, chirinos_farmers, norandino_farmers, aprocassi_farmers],
        ignore_index=True
    )
 
    # Remove Pasivo farmers with duplicate membership numbers
    print("  Cleaning duplicate membership numbers for Pasivo farmers...")
    if 'membership_number' in all_farmers_temporal.columns and 'member_status' in all_farmers_temporal.columns:
        dup_memberships = all_farmers_temporal[
            all_farmers_temporal.duplicated(subset=['membership_number'], keep=False)
        ]['membership_number'].unique()
 
        all_farmers_temporal = all_farmers_temporal[
            ~((all_farmers_temporal['member_status'] == 'Pasivo') &
              (all_farmers_temporal['membership_number'].isin(dup_memberships)))
        ].copy()
        print(f"  ✅ Removed Pasivo farmers with duplicate membership numbers")
 
    # Identity: 1 row per farmer — latest inspection year (for farmers_data, farmers_addresses)
    # sort descending so keep='first' keeps the most recent year
    all_farmers_identity = (
        all_farmers_temporal
        .sort_values('inspection_year', ascending=False)
        .drop_duplicates(subset=['pd_farmer_id'], keep='first')
        .reset_index(drop=True)
    )
 
    print(f"  ✅ all_farmers_temporal: {len(all_farmers_temporal):,} rows "
          f"({all_farmers_temporal['pd_farmer_id'].nunique():,} unique farmers)")
    print(f"  ✅ all_farmers_identity: {len(all_farmers_identity):,} rows "
          f"(1 per farmer, latest year)")
 
 
 
    # Combine plot tables
    if plot_tables:
        all_plots_combined = pd.concat(plot_tables, ignore_index=True)
 
        # Generate names for empty plot_name values
        print("  Generating plot names for empty plot_name values...")
        all_plots_combined = _build_plot_name_for_empty(all_plots_combined)
 
        print(f"  ✅ all_plots_combined: {len(all_plots_combined):,} plot records")
    else:
        all_plots_combined = pd.DataFrame()
        print("  ℹ️  No plot-level data detected across any PO")
 
    # -----------------------------------------------------------------------
    # Step 6: Extract inspection-based MySQL tables
    # -----------------------------------------------------------------------
    print("\n── Step 6: Extracting inspection-based MySQL tables ─────────────────")
 
    # farmers_data first — from inspections only at this point
    mysql_farmers_data = extract_farmers_data_table(all_farmers_identity)
 
    # Temporal-based tables (1 row per farmer per year)
    mysql_farmer_inspections  = extract_farmer_level_inspections_table(all_farmers_temporal)
    mysql_farmer_harvests     = extract_farmer_level_harvests_table(all_farmers_temporal)
 
    # Plot-based tables
    mysql_plot_inspections    = extract_plot_level_inspections_table(all_plots_combined)
    mysql_plot_harvests       = extract_plot_level_harvests_table(all_plots_combined)
 
    # Validate + deduplicate plot tables
    print("\n  🔍 Validating and deduplicating plot tables...")
    expected_counts = mysql_farmer_inspections[['pd_farmer_id', 'number_of_plots']].dropna(
        subset=['number_of_plots']
    ).copy()
 
    if not mysql_plot_inspections.empty:
        mysql_plot_inspections = _deduplicate_and_disambiguate_plots(
            mysql_plot_inspections, expected_counts, label='plot_level_inspections'
        )
    if not mysql_plot_harvests.empty:
        mysql_plot_harvests = _deduplicate_and_disambiguate_plots(
            mysql_plot_harvests, expected_counts, label='plot_level_harvests'
        )
 
    # -----------------------------------------------------------------------
    # Step 6b: Integrate Norandino membership file (optional)
    # Runs BEFORE transaction linking so membership farmers are findable by national_id
    # -----------------------------------------------------------------------
    if norandino_membership_df is not None:
        print("\n── Step 6b: Integrating Norandino membership file ───────────────────")
        mysql_farmers_data = _integrate_norandino_membership(
            mysql_farmers_data, norandino_membership_df, lookup_genders
        )
        print("  ✅ Norandino membership integration complete")
    else:
        print("\n── Step 6b: Norandino membership file not provided — skipping ────────")
 
    # -----------------------------------------------------------------------
    # Step 7: Build acopio transactions table
    # -----------------------------------------------------------------------
    print("\n── Step 7: Building acopio transactions table ───────────────────────")
    mysql_transactions = create_acopio_transactions_table(
        bagua_acopio_df        = bagua_acopio_df,
        hu_acopio_df           = hu_acopio_df,
        chirinos_acopio_df     = chirinos_acopio_df,
        norandino_acopio_df    = norandino_acopio_df,
        aprocassi_acopio_df    = aprocassi_acopio_df,
        bagua_inspections_df   = bagua_inspections_df,
        similarity_threshold   = bagua_fuzzy_threshold,
        bagua_bad_matches      = bagua_bad_matches,
    )
 
    # -----------------------------------------------------------------------
    # Step 8: Link transactions to farmers
    # Membership farmers are now in mysql_farmers_data → better Norandino match rate
    # -----------------------------------------------------------------------
    print("\n── Step 8: Linking transactions to farmers ──────────────────────────")
    mysql_transactions = _link_transactions_to_farmers(mysql_transactions, mysql_farmers_data)
 
    # -----------------------------------------------------------------------
    # Step 9: Add remaining unmatched transaction farmers as External
    # For Norandino: only truly non-member sellers reach here now
    # -----------------------------------------------------------------------
    print("\n── Step 9: Adding new farmers from unmatched transactions ───────────")
    mysql_transactions, mysql_farmers_data = _add_new_farmers_from_transactions(
        mysql_transactions, mysql_farmers_data
    )
 
    # -----------------------------------------------------------------------
    # Step 9b: Extract farmers_addresses from complete farmers table
    # Must run AFTER steps 6b and 9 so all farmers (inspection + membership +
    # transaction) have address records built.
    # -----------------------------------------------------------------------
    print("\n── Step 9b: Building farmers_addresses from complete farmers table ──")
    # Rebuild the full identity DataFrame to include membership and transaction farmers
    # For new farmers (membership/transaction only), address cols come from their records
    mysql_farmers_addresses = extract_farmer_addresses_table(mysql_farmers_data)
 
    # -----------------------------------------------------------------------
    # Step 10: Final summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("FINAL MYSQL TABLES SUMMARY")
    print("=" * 70)
    table_summary = {
        'farmers_data':               mysql_farmers_data,
        'farmers_addresses':          mysql_farmers_addresses,
        'farmer_level_inspections':   mysql_farmer_inspections,
        'plot_level_inspections':     mysql_plot_inspections,
        'farmer_level_harvests':      mysql_farmer_harvests,
        'plot_level_harvests':        mysql_plot_harvests,
        'acopio_transactions':        mysql_transactions,
        'lookup_countries':           lookup_countries,
        'lookup_producer_orgs':       lookup_producer_orgs,
        'lookup_genders':             lookup_genders,
        'lookup_product_types':       lookup_product_types,
        'lookup_units':               lookup_units,
        'lookup_currencies':          lookup_currencies,
    }
 
    for name, df in table_summary.items():
        if isinstance(df, pd.DataFrame):
            print(f"  📊 {name}: {len(df):,} records")
        else:
            print(f"  📊 {name}: (empty)")
 
    # -----------------------------------------------------------------------
    # Step 11: Export to CSV
    # -----------------------------------------------------------------------
    if export_csv:
        print(f"\n── Step 11: Exporting to CSV → {MYSQL_READY_DIR} ───────────────────")
 
        # Create all subfolders
        for folder in [MYSQL_READY_MASTER, MYSQL_READY_OPERATIONAL, MYSQL_READY_LOOKUP]:
            folder.mkdir(parents=True, exist_ok=True)
 
        for name, df in table_summary.items():
            if not isinstance(df, pd.DataFrame) or len(df) == 0:
                continue
            subfolder = MYSQL_READY_ROUTING.get(name, MYSQL_READY_DIR)
            csv_path  = subfolder / f"{name}.csv"
            df.to_csv(csv_path, index=False)
            print(f"  ✅ {subfolder.name}/{name}.csv")
 
        print(f"\n  ✅ All tables exported to {MYSQL_READY_DIR}")
 
    print("\n" + "=" * 70)
    print("✅ STAGE 2 COMPLETE")
    print("=" * 70)
 
    return table_summary