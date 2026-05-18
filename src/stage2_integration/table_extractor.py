"""
Table Extractor - Stage 2 Integration
======================================
Extracts MySQL-ready tables from the combined farmer-level and plot-level DataFrames
produced by the orchestrator in data_integrator.py.
 
Each function receives either:
    - all_farmers_identity  (1 row/farmer — for farmers_data, farmers_addresses)
    - all_farmers_temporal  (1 row/farmer/year — for farmer_level_inspections, farmer_level_harvests)
    - all_plots_combined    (1 row/plot — for plot_level_inspections, plot_level_harvests)
 
Functions:
    extract_farmers_data_table()
    extract_farmer_addresses_table()
    extract_farmer_level_inspections_table()
    extract_plot_level_inspections_table()
    extract_farmer_level_harvests_table()
    extract_plot_level_harvests_table()
 
Notes:
    - All functions use 'existing columns only' pattern — safe against PO-specific columns.
    - iterrows() replaced with vectorised pandas for address and harvest tables.
    - Column renames mirror notebook_4 exactly (eu_certification_* → eu_*_certification, plot_ prefixes).
"""
 
import pandas as pd
 
 
# =============================================================================
# FARMERS DATA
# =============================================================================
 
def extract_farmers_data_table(all_farmers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract columns for the farmers table (1 row per farmer).
 
    Receives all_farmers_identity — already deduplicated to 1 row/farmer
    by the orchestrator before this function is called.
    """
    farmers_data_columns = [
        'pd_farmer_id',       # Primary key
        'org_code',           # FK → producer_organizations
        'national_id',
        'farmer_name',
        'telephone',
        'gender_code',        # FK → lookup_genders
        'birth_date',
        'membership_number',
        'member_status',
        'entry_date',
        'base',
    ]
 
    existing_columns = [c for c in farmers_data_columns if c in all_farmers_df.columns]
    farmers_data_table = all_farmers_df[existing_columns].copy()
 
    print(f"   ✅ farmers_data: {len(farmers_data_table)} records, "
          f"{len(farmers_data_table.columns)} columns")
    return farmers_data_table
 
 
# =============================================================================
# FARMER ADDRESSES
# =============================================================================
 
def extract_farmer_addresses_table(all_farmers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract address information into the farmer_addresses table (1 row per farmer).
 
    Receives all_farmers_identity — already deduplicated to 1 row/farmer.
 
    Vectorised implementation (replaces iterrows() from notebook_4 for performance).
    """
    df = all_farmers_df.copy()
 
    # Helper: replace NaN/None with empty string for address fields
    def _str_col(series: pd.Series) -> pd.Series:
        return series.fillna('').astype(str).replace('nan', '').replace('None', '')
 
    addresses_table = pd.DataFrame({
        'pd_farmer_id':          df['pd_farmer_id'],
        'national_id':           df['national_id'] if 'national_id' in df.columns else None,
        'country_code':          df['country_code'] if 'country_code' in df.columns else 'PER',
        'administrative_area_1': _str_col(df.get('department',  pd.Series('', index=df.index))),
        'administrative_area_2': _str_col(df.get('province',    pd.Series('', index=df.index))),
        'administrative_area_3': _str_col(df.get('district',    pd.Series('', index=df.index))),
        'administrative_area_4': _str_col(df.get('village',     pd.Series('', index=df.index))),
        'postal_code':           '',
        'address_line':          _str_col(df.get('location',    pd.Series('', index=df.index))),
    })
 
    # Build formatted_address by concatenating non-empty parts
    parts = pd.concat([
        _str_col(df.get('location',   pd.Series('', index=df.index))),
        _str_col(df.get('village',    pd.Series('', index=df.index))),
        _str_col(df.get('district',   pd.Series('', index=df.index))),
        _str_col(df.get('province',   pd.Series('', index=df.index))),
        _str_col(df.get('department', pd.Series('', index=df.index))),
        pd.Series('Peru', index=df.index),
    ], axis=1)
 
    addresses_table['formatted_address'] = parts.apply(
        lambda row: ', '.join(part for part in row if part.strip()),
        axis=1
    )
 
    addresses_table = addresses_table.reset_index(drop=True)
 
    print(f"   ✅ farmer_addresses: {len(addresses_table)} records")
    return addresses_table
 
 
# =============================================================================
# FARMER-LEVEL INSPECTIONS
# =============================================================================
 
def extract_farmer_level_inspections_table(all_farmers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract inspection-related columns for farmer_level_inspections table.
 
    Receives all_farmers_temporal — 1 row per farmer per year.
    For Chirinos this means multiple rows per farmer (one per inspection year).
    For all other POs this is 1 row per farmer.
    """
    farmer_inspections_columns = [
        'pd_farmer_id',
        'national_id',          # primary lookup key in Stage 3 migration
        'inspection_year',
        'product_code',             # FK → lookup_product_types
        'base',
        'category',
        'number_of_plots',
 
        # Area measurements (farmer-level totals)
        'total_area_ha',
        'coffee_area_ha',
        'growing_area_ha',
        'conversion_area_ha',
        'other_crops_area_ha',
        'forest_area_ha',
        'secondary_forest_area_ha',
        'purma_area_ha',
        'rehabilitation_area_ha',
        'cultivable_area_ha',       # Huadquiña-specific
 
        # Coordinates
        'latitude',
        'longitude',
        'altitude',
        'utm_zone',
        'x_east',
        'y_north',
 
        # Certification and control
        'last_internal_control_date',
        'internal_inspector_name',
        'internal_control_result',
        'conversion_start_date',
        'last_external_control_date',
        'eu_certification_previous',
        'eu_certification_current',
        'nop_certification_current',
        'certification_seals',
        'certification_type',
 
        # Additional
        'temporary_workers_count',
        'female_workers_count',
        'sampling_point',           # Huadquiña-specific
    ]
 
    existing_columns = [c for c in farmer_inspections_columns if c in all_farmers_df.columns]
    farmer_inspections_table = all_farmers_df[existing_columns].copy()
 
    # Final rename to match SDL schema
    farmer_inspections_table.rename(columns={
        'eu_certification_previous': 'eu_previous_certification',
        'eu_certification_current':  'eu_current_certification',
        'nop_certification_current': 'nop_current_certification',
    }, inplace=True)
 
    print(f"   ✅ farmer_level_inspections: {len(farmer_inspections_table)} records, "
          f"{len(farmer_inspections_table.columns)} columns")
    return farmer_inspections_table
 
 
# =============================================================================
# PLOT-LEVEL INSPECTIONS
# =============================================================================
 
def extract_plot_level_inspections_table(all_plots_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract inspection-related columns for plot_level_inspections table.
    Receives all_plots_combined — 1 row per plot.
    Empty DataFrame is handled gracefully (Chirinos contributes no plots).
    """
    if all_plots_df.empty:
        print("   ⚠️  plot_level_inspections: input is empty — returning empty table")
        return pd.DataFrame()
 
    plot_inspections_columns = [
        'pd_farmer_id',
        'inspection_year',
        'product_code',
        'plot_name',
        'category',
 
        # Area measurements (plot-specific)
        'total_area_ha',
        'coffee_area_ha',
        'growing_area_ha',
        'conversion_area_ha',
        'other_crops_area_ha',
        'forest_area_ha',
        'secondary_forest_area_ha',
        'purma_area_ha',
        'rehabilitation_area_ha',
        'cultivable_area_ha',
 
        # Coordinates (plot-specific)
        'latitude',
        'longitude',
        'altitude',
        'utm_zone',
        'x_east',
        'y_north',
 
        # Certification and control (plot-level)
        'last_internal_control_date',
        'internal_inspector_name',
        'internal_control_result',
        'conversion_start_date',
        'eu_certification_previous',
        'eu_certification_current',
        'nop_certification_current',
        'sampling_point',
    ]
 
    existing_columns = [c for c in plot_inspections_columns if c in all_plots_df.columns]
    plot_inspections_table = all_plots_df[existing_columns].copy()
 
    # Add plot_ prefix to plot-specific columns
    plot_inspections_table.rename(columns={
        'category':                   'plot_category',
        'total_area_ha':              'plot_area_ha',
        'coffee_area_ha':             'plot_coffee_area_ha',
        'growing_area_ha':            'plot_growing_area_ha',
        'conversion_area_ha':         'plot_conversion_area_ha',
        'other_crops_area_ha':        'plot_other_crops_area_ha',
        'forest_area_ha':             'plot_forest_area_ha',
        'secondary_forest_area_ha':   'plot_secondary_forest_area_ha',
        'purma_area_ha':              'plot_purma_area_ha',
        'rehabilitation_area_ha':     'plot_rehabilitation_area_ha',
        'cultivable_area_ha':         'plot_cultivable_area_ha',
        'last_internal_control_date': 'plot_last_internal_control_date',
        'internal_inspector_name':    'plot_internal_inspector_name',
        'internal_control_result':    'plot_internal_control_result',
        'conversion_start_date':      'plot_conversion_start_date',
        'eu_certification_previous':  'plot_eu_previous_certification',
        'eu_certification_current':   'plot_eu_current_certification',
        'nop_certification_current':  'plot_nop_current_certification',
        'sampling_point':             'plot_sampling_point',
    }, inplace=True)
 
    print(f"   ✅ plot_level_inspections: {len(plot_inspections_table)} records, "
          f"{len(plot_inspections_table.columns)} columns")
    return plot_inspections_table
 
 
# =============================================================================
# FARMER-LEVEL HARVESTS
# =============================================================================
 
# Harvest columns to pull from each farmer row
_FARMER_HARVEST_FIELDS = [
    'current_year_estimate_local_unit',
    'current_year_estimate_kg',
    'previous_year_estimate_local_unit',
    'previous_year_real_local_unit',
    'real_yield_kgha',
]
 
def extract_farmer_level_harvests_table(all_farmers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract harvest information into farmer_level_harvests table.
    Only rows that have at least one non-null harvest field are included.
 
    Receives all_farmers_temporal — 1 row per farmer per year.
    Vectorised implementation (replaces iterrows() from notebook_4).
    """
    df = all_farmers_df.copy()
 
    # Keep only rows that have at least one harvest value
    harvest_check_cols = [c for c in _FARMER_HARVEST_FIELDS if c in df.columns]
    has_harvest = df[harvest_check_cols].notna().any(axis=1)
    df = df[has_harvest].copy()
 
    harvest_columns = [
        'pd_farmer_id',
        'inspection_year',           # → renamed to harvest_year below
        'product_code',
        'unit_code',
        'previous_year_estimate_local_unit',
        'previous_year_estimate_kg',
        'previous_year_real_local_unit',
        'previous_year_real_kg',
        'current_year_estimate_local_unit',
        'current_year_estimate_kg',
        'current_year_commitment_local_unit',
        'estimated_yield_local_unit_ha',
        'real_yield_kgha',
        'real_yield_local_unit_ha',
    ]
 
    existing_columns = [c for c in harvest_columns if c in df.columns]
    harvests_table = df[existing_columns].copy()
 
    harvests_table.rename(columns={'inspection_year': 'harvest_year'}, inplace=True)
 
    harvests_table = harvests_table.reset_index(drop=True)
 
    print(f"   ✅ farmer_level_harvests: {len(harvests_table)} records")
    return harvests_table
 
 
# =============================================================================
# PLOT-LEVEL HARVESTS
# =============================================================================
 
_PLOT_HARVEST_FIELDS = [
    'current_year_estimate_local_unit',
    'current_year_estimate_kg',
    'previous_year_estimate_local_unit',
    'previous_year_real_local_unit',
    'real_yield_kgha',
]
 
def extract_plot_level_harvests_table(all_plots_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract harvest information for plot_level_harvests table.
    Only plots with at least one non-null harvest field are included.
 
    Receives all_plots_combined — 1 row per plot.
    Vectorised implementation (replaces iterrows() from notebook_4).
    Empty DataFrame is handled gracefully.
    """
    if all_plots_df.empty:
        print("   ⚠️  plot_level_harvests: input is empty — returning empty table")
        return pd.DataFrame()
 
    df = all_plots_df.copy()
 
    # Keep only rows that have at least one harvest value
    harvest_check_cols = [c for c in _PLOT_HARVEST_FIELDS if c in df.columns]
    has_harvest = df[harvest_check_cols].notna().any(axis=1)
    df = df[has_harvest].copy()
 
    harvest_columns = [
        'pd_farmer_id',
        'plot_name',
        'inspection_year',           # → renamed to harvest_year below
        'product_code',
        'unit_code',
        'previous_year_estimate_local_unit',
        'previous_year_estimate_kg',
        'previous_year_real_local_unit',
        'previous_year_real_kg',
        'current_year_estimate_local_unit',
        'current_year_estimate_kg',
        'current_year_commitment_local_unit',
        'estimated_yield_kgha',
        'real_yield_kgha',
        'real_yield_local_unit_ha',
    ]
 
    existing_columns = [c for c in harvest_columns if c in df.columns]
    harvests_table = df[existing_columns].copy()
 
    harvests_table.rename(columns={
        'inspection_year':                    'harvest_year',
        'previous_year_estimate_local_unit':  'plot_previous_year_estimate_local_unit',
        'previous_year_estimate_kg':          'plot_previous_year_estimate_kg',
        'previous_year_real_local_unit':      'plot_previous_year_real_local_unit',
        'previous_year_real_kg':              'plot_previous_year_real_kg',
        'current_year_estimate_local_unit':   'plot_current_year_estimate_local_unit',
        'current_year_estimate_kg':           'plot_current_year_estimate_kg',
        'current_year_commitment_local_unit': 'plot_current_year_commitment_local_unit',
        'estimated_yield_kgha':               'plot_estimated_yield_kgha',
        'real_yield_kgha':                    'plot_real_yield_kgha',
        'real_yield_local_unit_ha':           'plot_real_yield_local_unit_ha',
    }, inplace=True)
 
    harvests_table = harvests_table.reset_index(drop=True)
 
    print(f"   ✅ plot_level_harvests: {len(harvests_table)} records")
    return harvests_table