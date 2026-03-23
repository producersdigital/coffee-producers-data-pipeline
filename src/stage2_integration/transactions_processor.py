"""
Transactions Processor - Stage 2 Integration
=============================================
Handles the creation of the unified acopio_transactions MySQL table from all 5 PO
transaction files, including the Bagua-specific DNI matching step.
 
Bagua Grande transactions don't include national_id (DNI) in their source files.
This module resolves that by matching Bagua farmer names against the inspections
dataset using exact + fuzzy string matching.
 
Functions (in call order):
    standardize_name()              - Unicode/accent normalization for name matching
    match_dni_by_name()             - Exact + fuzzy DNI matching for Bagua
    display_matching_results()      - Print matching diagnostics
    remove_bad_matches()            - Remove known false positives after fuzzy match
    clean_excel_errors()            - Strip Excel error strings (#ERROR!, #N/A, etc.)
    standardize_all_data_types()    - Enforce dtypes on combined transactions DataFrame
    create_acopio_transactions_table() - Main function: combine all 5 POs into one table
 
Usage:
    from src.stage2_integration.transactions_processor import create_acopio_transactions_table
"""
 
import re
import unicodedata
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz, process
 
from src.utils.mapping_helpers import map_unit_to_id
 
 
# =============================================================================
# NAME STANDARDISATION (for Bagua DNI matching)
# =============================================================================
 
def standardize_name(name) -> str:
    """
    Normalize a farmer name for string matching.
    Removes accents, punctuation, collapses whitespace, uppercases.
    """
    if pd.isna(name) or name == '':
        return ''
 
    name = str(name)
    # Strip accents
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    name = name.upper().strip()
    # Keep only letters, digits, spaces
    name = re.sub(r'[^\w\s]', '', name)
    name = ' '.join(name.split())
    return name
 
 
# =============================================================================
# BAGUA DNI MATCHING
# =============================================================================
 
def match_dni_by_name(
    bagua_acopio_df: pd.DataFrame,
    bagua_inspections_df: pd.DataFrame,
    similarity_threshold: float = 0.85
) -> tuple[pd.DataFrame, dict]:
    """
    Match DNI values from Bagua inspections to Bagua acopio records using name matching.
    Bagua transaction files don't include DNI, so we infer it from farmer names.
 
    Stage 1: Exact match on standardised name.
    Stage 2: Fuzzy match (fuzzywuzzy ratio) above similarity_threshold for remainder.
 
    Args:
        bagua_acopio_df:        Bagua transactions DataFrame (no DNI column)
        bagua_inspections_df:   Bagua inspections DataFrame (has DNI + nombre_productor)
        similarity_threshold:   Minimum similarity score 0–1 (default 0.85)
 
    Returns:
        (updated_acopio_df, stats_dict)
    """
    acopio_work       = bagua_acopio_df.copy()
    inspections_work  = bagua_inspections_df.copy()
 
    # Initialise empty DNI column
    acopio_work['dni'] = ''
 
    print("  📝 Standardizing names...")
    acopio_work['nombre_normalizado']      = acopio_work['nombre_productor'].apply(standardize_name)
    inspections_work['nombre_normalizado'] = inspections_work['nombre_productor'].apply(standardize_name)
 
    # Deduplicate inspections by normalised name (same farmer may appear multiple times)
    inspections_unique = inspections_work.drop_duplicates(subset=['nombre_normalizado'], keep='first')
 
    print(f"  🔍 Acopio records to match:      {len(acopio_work)}")
    print(f"  🔍 Unique farmers in inspections: {len(inspections_unique)}")
 
    stats = {
        'total_acopio_records':    len(acopio_work),
        'total_unique_inspections': len(inspections_unique),
        'exact_matches':           0,
        'fuzzy_matches':           0,
        'no_matches':              0,
        'exact_match_details':     [],
        'fuzzy_match_details':     [],
        'unmatched_names':         [],
    }
 
    # ------------------------------------------------------------------
    # Stage 1: Exact match
    # ------------------------------------------------------------------
    print("\n  🎯 Stage 1: Exact name matching...")
    exact_lookup = dict(zip(inspections_unique['nombre_normalizado'], inspections_unique['dni']))
    exact_mask   = acopio_work['nombre_normalizado'].isin(exact_lookup)
    acopio_work.loc[exact_mask, 'dni'] = acopio_work.loc[exact_mask, 'nombre_normalizado'].map(exact_lookup)
 
    stats['exact_matches'] = int(exact_mask.sum())
    print(f"     ✅ Exact matches: {stats['exact_matches']}")
 
    exact_detail = (
        acopio_work[exact_mask][['nombre_productor', 'nombre_normalizado', 'dni']]
        .drop_duplicates()
    )
    stats['exact_match_details'] = exact_detail.to_dict('records')
 
    # ------------------------------------------------------------------
    # Stage 2: Fuzzy match for remaining unmatched records
    # ------------------------------------------------------------------
    remaining = (~exact_mask).sum()
    print(f"\n  🔍 Stage 2: Fuzzy matching for {remaining} remaining records...")
 
    unmatched_acopio = acopio_work[~exact_mask].copy()
 
    if len(unmatched_acopio) > 0:
        available_names       = inspections_unique['nombre_normalizado'].tolist()
        name_to_dni           = dict(zip(inspections_unique['nombre_normalizado'],
                                         inspections_unique['dni']))
        name_to_original      = dict(zip(inspections_unique['nombre_normalizado'],
                                         inspections_unique['nombre_productor']))
        fuzzy_match_details   = []
        threshold_scaled      = similarity_threshold * 100  # fuzzywuzzy uses 0–100
 
        for idx, row in unmatched_acopio.iterrows():
            acopio_name = row['nombre_normalizado']
            if acopio_name == '':
                continue
 
            best_match = process.extractOne(acopio_name, available_names, scorer=fuzz.ratio)
 
            if best_match and best_match[1] >= threshold_scaled:
                matched_name  = best_match[0]
                matched_dni   = name_to_dni[matched_name]
                score         = best_match[1] / 100
 
                acopio_work.loc[idx, 'dni'] = matched_dni
                stats['fuzzy_matches'] += 1
 
                fuzzy_match_details.append({
                    'acopio_name':       row['nombre_productor'],
                    'acopio_normalized': acopio_name,
                    'matched_name':      name_to_original.get(matched_name, matched_name),
                    'matched_normalized': matched_name,
                    'matched_dni':       matched_dni,
                    'similarity_score':  score,
                })
 
        stats['fuzzy_match_details'] = fuzzy_match_details
        print(f"     ✅ Fuzzy matches: {stats['fuzzy_matches']} (threshold: {similarity_threshold})")
 
    # ------------------------------------------------------------------
    # Stage 3: Identify still-unmatched
    # ------------------------------------------------------------------
    final_unmatched     = acopio_work[acopio_work['dni'] == '']
    stats['no_matches'] = len(final_unmatched)
    stats['unmatched_names'] = (
        final_unmatched[['nombre_productor', 'nombre_normalizado']]
        .drop_duplicates()
        .to_dict('records')
    )
 
    total_matched = stats['exact_matches'] + stats['fuzzy_matches']
    pct = total_matched / stats['total_acopio_records'] * 100
    print(f"\n  📊 MATCHING SUMMARY:")
    print(f"     ✅ Exact matches:  {stats['exact_matches']}")
    print(f"     🔍 Fuzzy matches:  {stats['fuzzy_matches']}")
    print(f"     ❌ No match:       {stats['no_matches']}")
    print(f"     📈 Total matched:  {total_matched} / {stats['total_acopio_records']} ({pct:.1f}%)")
 
    acopio_final = acopio_work.drop(columns=['nombre_normalizado'])
    return acopio_final, stats
 
 
def display_matching_results(stats: dict, show_details: bool = True, max_details: int = 10):
    """Print a human-readable summary of match_dni_by_name results."""
    print("\n" + "=" * 60)
    print("🎯 DETAILED MATCHING RESULTS")
    print("=" * 60)
 
    if show_details and stats['exact_match_details']:
        n = min(max_details, len(stats['exact_match_details']))
        print(f"\n✅ EXACT MATCHES (first {n}):")
        for i, m in enumerate(stats['exact_match_details'][:n], 1):
            print(f"   {i}. '{m['nombre_productor']}' → DNI: {m['dni']}")
 
    if show_details and stats['fuzzy_match_details']:
        n = min(max_details, len(stats['fuzzy_match_details']))
        print(f"\n🔍 FUZZY MATCHES (first {n}):")
        for i, m in enumerate(stats['fuzzy_match_details'][:n], 1):
            print(f"   {i}. '{m['acopio_name']}' → '{m['matched_name']}' "
                  f"(DNI: {m['matched_dni']}, Score: {m['similarity_score']:.2f})")
 
    if show_details and stats['unmatched_names']:
        n = min(max_details, len(stats['unmatched_names']))
        print(f"\n❌ UNMATCHED (first {n}):")
        for i, u in enumerate(stats['unmatched_names'][:n], 1):
            print(f"   {i}. '{u['nombre_productor']}'")
 
 
def remove_bad_matches(
    bagua_acopio_with_dni: pd.DataFrame,
    bad_names: list[str] | None = None
) -> pd.DataFrame:
    """
    Clear DNI for known false-positive fuzzy matches.
 
    Args:
        bagua_acopio_with_dni:  Bagua transactions after match_dni_by_name()
        bad_names:              List of nombre_productor substrings to clear.
                                Defaults to ['AREVALO IZQUIERDO MARLO'] — the
                                confirmed bad match found during initial analysis.
 
    Returns:
        DataFrame with DNI cleared for bad matches.
    """
    if bad_names is None:
        bad_names = ['AREVALO IZQUIERDO MARLO']
 
    df = bagua_acopio_with_dni.copy()
 
    for name in bad_names:
        mask = df['nombre_productor'].str.contains(name, na=False)
        if mask.any():
            print(f"  🚫 Clearing bad match for '{name}' — {mask.sum()} records")
            df.loc[mask, 'dni'] = ''
        else:
            print(f"  ℹ️  No records found for '{name}'")
 
    return df
 
 
# =============================================================================
# EXCEL ERROR CLEANING
# =============================================================================
 
EXCEL_ERROR_PATTERNS = [
    '#ERROR!', '#¡ERROR!', '#VALUE!', '#¡VALOR!', '#N/A',  '#¡N/A!',
    '#DIV/0!', '#¡DIV/0!', '#REF!',  '#¡REF!',   '#NAME?', '#¿NOMBRE?',
    '#NUM!',   '#¡NÚM!',   '#NULL!', '#¡NULO!',
]
 
def clean_excel_errors(
    df: pd.DataFrame,
    columns_to_clean: list[str] | None = None
) -> pd.DataFrame:
    """
    Replace Excel error strings with empty string in specified columns.
 
    Args:
        df:               Input DataFrame
        columns_to_clean: Columns to check. If None, all object columns are checked.
 
    Returns:
        Cleaned DataFrame.
    """
    df_clean = df.copy()
 
    if columns_to_clean is None:
        columns_to_clean = df_clean.select_dtypes(include=['object']).columns.tolist()
 
    print(f"  🧹 Cleaning Excel errors in {len(columns_to_clean)} columns...")
    errors_found = 0
 
    for col in columns_to_clean:
        if col not in df_clean.columns:
            continue
        df_clean[col] = df_clean[col].astype(str)
        for pattern in EXCEL_ERROR_PATTERNS:
            mask = df_clean[col].str.contains(pattern, case=False, na=False)
            if mask.any():
                errors_found += int(mask.sum())
                df_clean[col] = df_clean[col].str.replace(pattern, '', case=False, regex=False)
 
    if errors_found:
        print(f"     ✅ Cleaned {errors_found} error strings")
    else:
        print(f"     ✅ No error strings found")
 
    return df_clean
 
 
# =============================================================================
# DATA TYPE STANDARDISATION
# =============================================================================
 
def standardize_all_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enforce consistent dtypes on the combined acopio transactions DataFrame.
 
    - transaction_date → YYYY-MM-DD string (MySQL-ready)
    - numeric columns  → float64 (strips currency symbols, commas, % signs)
    - processing_yield → float64 (same stripping)
    """
    df_clean = df.copy()
 
    # Dates
    df_clean['transaction_date'] = pd.to_datetime(df_clean['transaction_date'], errors='coerce')
    df_clean['transaction_date'] = df_clean['transaction_date'].dt.strftime('%Y-%m-%d')
    df_clean['transaction_date'] = df_clean['transaction_date'].replace('NaT', None)
 
    # Numeric columns
    numeric_cols = [
        'campaign_year', 'kg_quantity', 'kg_price', 'local_unit_quantity',
        'local_unit_price', 'local_currency_total_amount', 'humidity_percentage',
        'kg_ha', 'processing_yield', 'local_unit_qty_after_hum_percentage',
    ]
    for col in numeric_cols:
        if col in df_clean.columns:
            df_clean[col] = (
                df_clean[col].astype(str)
                .str.replace(',',  '', regex=False)
                .str.replace('S/', '', regex=False)
                .str.replace('$',  '', regex=False)
                .str.replace('%',  '', regex=False)
            )
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
 
    # processing_yield extra pass (already covered above but kept explicit)
    if 'processing_yield' in df_clean.columns:
        df_clean['processing_yield'] = (
            df_clean['processing_yield'].astype(str)
            .str.replace('%', '', regex=False)
            .str.replace(',', '', regex=False)
        )
        df_clean['processing_yield'] = pd.to_numeric(df_clean['processing_yield'], errors='coerce')
 
    print("  ✅ All data types standardized")
    return df_clean
 
 
# =============================================================================
# MAIN TRANSACTIONS TABLE BUILDER
# =============================================================================
 
def _clean_dni(x) -> str:
    """Pad DNI to 8 digits. Returns empty string for null/empty values."""
    if pd.isna(x) or x == '':
        return ''
    try:
        x_str = str(int(float(x)))
    except (ValueError, TypeError):
        x_str = re.sub(r'\D', '', str(x).lstrip("'").strip())
    return x_str.zfill(8) if x_str else ''
 
 
def create_acopio_transactions_table(
    bagua_acopio_df: pd.DataFrame,
    hu_acopio_df: pd.DataFrame,
    chirinos_acopio_df: pd.DataFrame,
    norandino_acopio_df: pd.DataFrame,
    aprocassi_acopio_df: pd.DataFrame,
    bagua_inspections_df: pd.DataFrame,
    similarity_threshold: float = 0.85,
    bagua_bad_matches: list[str] | None = None,
) -> pd.DataFrame:
    """
    Create the unified acopio_transactions table from all 5 PO transaction files.
 
    Steps:
        1. Resolve Bagua DNI via name matching against inspections
        2. Clean Excel errors from Bagua numeric columns
        3. Standardise DNI format across all POs
        4. Assign org_code + concat all POs
        5. Rename columns to English schema
        6. Standardise data types
        7. Select final column set + add currency/unit codes
 
    Args:
        bagua_acopio_df:        Bagua transactions (no DNI column in source)
        hu_acopio_df:           Huadquiña transactions
        chirinos_acopio_df:     Chirinos transactions
        norandino_acopio_df:    Norandino transactions
        aprocassi_acopio_df:    Aprocassi transactions
        bagua_inspections_df:   Bagua inspections (used for DNI matching)
        similarity_threshold:   Fuzzy match threshold for Bagua DNI matching (default 0.85)
        bagua_bad_matches:      Known false-positive names to clear after fuzzy match.
                                Defaults to ['AREVALO IZQUIERDO MARLO'].
 
    Returns:
        acopio_transactions DataFrame ready for MySQL loading.
    """
    print("=" * 60)
    print("CREATING ACOPIO TRANSACTIONS TABLE")
    print("=" * 60)
 
    # ------------------------------------------------------------------
    # Step 1: Resolve Bagua DNI via name matching
    # ------------------------------------------------------------------
    print("\nStep 1: Resolving Bagua DNI via name matching...")
    bagua_with_dni, matching_stats = match_dni_by_name(
        bagua_acopio_df,
        bagua_inspections_df,
        similarity_threshold=similarity_threshold,
    )
 
    # Remove known bad fuzzy matches
    bagua_with_dni = remove_bad_matches(bagua_with_dni, bad_names=bagua_bad_matches)
 
    # Step 2: Clean Excel errors from Bagua numeric columns
    print("\nStep 2: Cleaning Excel errors in Bagua numeric columns...")
    bagua_clean = clean_excel_errors(bagua_with_dni, columns_to_clean=['kg', 'qq', 'total_soles'])
 
    # ------------------------------------------------------------------
    # Step 3: Standardise DNI format across all POs
    # ------------------------------------------------------------------
    print("\nStep 3: Standardising DNI across all POs...")
    po_frames = [
        (bagua_clean,        'BG'),
        (hu_acopio_df,       'HU'),
        (chirinos_acopio_df, 'CH'),
        (norandino_acopio_df,'NO'),
        (aprocassi_acopio_df,'AP'),
    ]
 
    cleaned_frames = []
    for df, org in po_frames:
        df = df.copy()
        if 'dni' in df.columns:
            df['dni'] = df['dni'].apply(_clean_dni)
            matched = (df['dni'] != '').sum()
            print(f"  ✅ {org}: {matched} records with DNI")
        df['org_code'] = org
        cleaned_frames.append(df)
 
    # ------------------------------------------------------------------
    # Step 4: Concatenate all POs
    # ------------------------------------------------------------------
    print("\nStep 4: Combining all PO transactions...")
    all_acopio = pd.concat(cleaned_frames, ignore_index=True)
    print(f"  Combined: {len(all_acopio)} total records")
 
    # ------------------------------------------------------------------
    # Step 5: Rename columns to English schema
    # ------------------------------------------------------------------
    print("\nStep 5: Renaming columns to English schema...")
    all_acopio.rename(columns={
        'fecha':                    'transaction_date',
        'campania':                 'campaign_year',
        'dni':                      'national_id',
        'nombre_productor':         'farmer_name',
        'sector':                   'sector',
        'categoria':                'category',
        'unidad':                   'transaction_unit',
        'kg':                       'kg_quantity',
        'qq':                       'local_unit_quantity',
        'porcentaje_humedad':       'humidity_percentage',
        'qq_porcentaje_humedad':    'local_unit_qty_after_hum_percentage',
        'precio_kg':                'kg_price',
        'precio_qq':                'local_unit_price',
        'total_soles':              'local_currency_total_amount',
        'taza':                     'cup_quality',
        'taza_rango':               'cup_quality_range',
        'rendimiento':              'processing_yield',
    }, inplace=True)
 
    # ------------------------------------------------------------------
    # Step 6: Standardise data types
    # ------------------------------------------------------------------
    print("\nStep 6: Standardising data types...")
    all_acopio = standardize_all_data_types(all_acopio)
 
    # ------------------------------------------------------------------
    # Step 7: Select final columns + add currency/unit codes
    # ------------------------------------------------------------------
    print("\nStep 7: Selecting final columns...")
    STANDARD_COLUMNS = [
        'transaction_date', 'campaign_year', 'national_id', 'org_code',
        'sector', 'category', 'kg_quantity', 'local_unit_quantity',
        'humidity_percentage', 'transaction_unit', 'farmer_name',
        'local_unit_qty_after_hum_percentage', 'kg_price', 'local_unit_price',
        'local_currency_total_amount', 'kg_ha', 'cup_quality',
        'cup_quality_range', 'processing_yield',
    ]
 
    # Only select columns that exist (safe against PO-specific columns)
    existing_std = [c for c in STANDARD_COLUMNS if c in all_acopio.columns]
    acopio_final = all_acopio[existing_std].copy()
 
    acopio_final['currency_code']        = 'PEN'
    acopio_final['transaction_unit_code'] = map_unit_to_id(
        acopio_final['transaction_unit'].fillna('')
    )
    acopio_final.drop(columns=['transaction_unit'], inplace=True)
 
    print(f"\n   ✅ Acopio transactions table: {len(acopio_final)} records, "
          f"{len(acopio_final.columns)} columns")
    return acopio_final