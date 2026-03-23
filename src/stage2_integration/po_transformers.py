"""
PO Transformers - Stage 2 Integration
======================================
Creates farmer-level and plot-level datasets for each Producer Organization (PO),
ready for downstream table extraction and MySQL loading.
 
One function pair per PO:
    create_<po>_farmer_level_dataset()  →  1 row per farmer (or 1 row per farmer per year for Chirinos)
    create_<po>_plot_level_dataset()    →  1 row per plot (or empty DataFrame if PO has no plot data)
 
Key architectural notes:
    - Bagua, Huadquiña, Aprocassi: auto-detect granularity (plot vs farmer level)
    - Chirinos: multi-year data — NO aggregation, NO granularity detection.
      Returns 1 row per farmer per year. inspeccion_year → inspection_year in English rename.
    - Norandino: already farmer-level. Plot function unpivots wide format (up to 10 plots/farmer).
    - Column translations (Spanish → English) are embedded per PO to match notebook_4 exactly.
    - add_schema_compliance_columns() sets org_code, country_code, gender_code.
 
Usage:
    from src.stage2_integration.po_transformers import (
        create_bagua_farmer_level_dataset,
        create_bagua_plot_level_dataset,
        # ... etc
    )
"""
 
import pandas as pd
import numpy as np
from pathlib import Path
 
 
from src.utils.mapping_helpers import map_gender_to_id, map_unit_to_id  # noqa: F401 (re-exported)
 
def add_schema_compliance_columns(
    df: pd.DataFrame,
    org_code: str,
    lookup_genders_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Add org_code, country_code, and gender_code columns for schema compliance.
    gender_code is mapped from 'gender' column if present; otherwise left NULL.
    """
    df = df.copy()
    df['org_code'] = org_code
    df['country_code'] = 'PER'
 
    if 'gender' in df.columns and df['gender'].notna().any():
        df['gender_code'] = map_gender_to_id(df['gender'], lookup_genders_df)
        print(f"  ✅ Gender data found and mapped for {org_code}")
    else:
        df['gender_code'] = None
        print(f"  ⚠️  No gender data available for {org_code} - leaving NULL")
 
    return df
 
 
# =============================================================================
# BAGUA GRANDE
# =============================================================================
 
def create_bagua_farmer_level_dataset(
    bagua_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> tuple[pd.DataFrame, bool]:
    """
    Bagua Grande farmer-level dataset.
    Auto-detects granularity: if plot-level data, aggregates to farmer level.
 
    Returns:
        (farmers_df, create_plot_table)
    """
    print("Processing Bagua Grande...")
    print(f"  Input: {len(bagua_inspections_df)} records")
 
    farmer_counts = bagua_inspections_df['producers_direct_id_productor'].value_counts()
    max_plots_per_farmer = farmer_counts.max()
 
    if max_plots_per_farmer > 1:
        print(f"  📊 Plot-level data detected (max {max_plots_per_farmer} plots per farmer)")
        create_plot_table = True
 
        farmers_df = bagua_inspections_df.groupby('producers_direct_id_productor').agg({
            'nombre_productor':               'first',
            'dni':                            'first',
            'nro_socio':                      'first',
            'base':                           'first',
            'categoria':                      lambda x: ','.join(x.unique()),
            'org_code':                       'first',
            'ubicacion':                      'first',
            'area_total_ha':                  'sum',
            'area_cafe':                      'sum',
            'area_crecimiento':               'sum',
            'area_conversion':                'sum',
            'area_otros_cultivos':            'sum',
            'area_bosque':                    'sum',
            'cosecha_estimado_anterior_qq':   'sum',
            'cosecha_acopio_anterior_qq':     'sum',
            'cosecha_estimado_actual_qq':     'sum',
            'cosecha_estimado_actual_kg':     'sum',
            'rendimiento_actual_kgha':        'mean',
            'fecha_ultimo_control_interno':   'first',
            'nombre_inspector_interno':       'first',
            'resultado_control_interno':      'first',
            'fecha_inicio_conversion':        'first',
            'certificacion_ue_rtpo_anterior': 'first',
            'certificacion_ue_rtpo_actual':   'first',
            'certificacion_nop_actual':       'first',
            'latitud':                        'first',
            'longitud':                       'first',
            'altitud':                        'first',
            'zona_utm':                       'first',
            'x_este':                         'first',
            'y_norte':                        'first',
            'nombre_parcela':                 'size',   # count of plots
        }).reset_index()
 
    else:
        print(f"  📊 Farmer-level data detected (1 row per farmer)")
        create_plot_table = False
 
        farmer_level_columns = [
            'producers_direct_id_productor', 'nombre_productor', 'dni', 'nro_socio',
            'base', 'categoria', 'ubicacion', 'area_total_ha', 'area_cafe',
            'area_crecimiento', 'area_conversion', 'area_otros_cultivos', 'area_bosque',
            'cosecha_estimado_anterior_qq', 'cosecha_acopio_anterior_qq',
            'cosecha_estimado_actual_qq', 'cosecha_estimado_actual_kg',
            'rendimiento_actual_kgha', 'fecha_ultimo_control_interno',
            'nombre_inspector_interno', 'resultado_control_interno',
            'fecha_inicio_conversion', 'certificacion_ue_rtpo_anterior',
            'certificacion_ue_rtpo_actual', 'certificacion_nop_actual',
            'latitud', 'longitud', 'altitud', 'zona_utm', 'x_este', 'y_norte',
            'numero_parcelas', 'org_code'
        ]
        existing_columns = [c for c in farmer_level_columns if c in bagua_inspections_df.columns]
        farmers_df = bagua_inspections_df[existing_columns].copy()
 
    # numero_parcelas → number_of_plots (farmer-level path only)
    if 'numero_parcelas' in farmers_df.columns:
        farmers_df.rename(columns={'numero_parcelas': 'number_of_plots'}, inplace=True)
 
    farmers_df.rename(columns={
        'producers_direct_id_productor':  'pd_farmer_id',
        'nombre_productor':               'farmer_name',
        'dni':                            'national_id',
        'nro_socio':                      'membership_number',
        'ubicacion':                      'location',
        'nombre_parcela':                 'number_of_plots',   # plot-level path
        'categoria':                      'category',
        'area_total_ha':                  'total_area_ha',
        'area_cafe':                      'coffee_area_ha',
        'area_crecimiento':               'growing_area_ha',
        'area_conversion':                'conversion_area_ha',
        'area_otros_cultivos':            'other_crops_area_ha',
        'area_bosque':                    'forest_area_ha',
        'cosecha_estimado_anterior_qq':   'previous_year_estimate_local_unit',
        'cosecha_acopio_anterior_qq':     'previous_year_real_local_unit',
        'cosecha_estimado_actual_qq':     'current_year_estimate_local_unit',
        'cosecha_estimado_actual_kg':     'current_year_estimate_kg',
        'rendimiento_actual_kgha':        'real_yield_kgha',
        'fecha_ultimo_control_interno':   'last_internal_control_date',
        'nombre_inspector_interno':       'internal_inspector_name',
        'resultado_control_interno':      'internal_control_result',
        'fecha_inicio_conversion':        'conversion_start_date',
        'certificacion_ue_rtpo_anterior': 'eu_certification_previous',
        'certificacion_ue_rtpo_actual':   'eu_certification_current',
        'certificacion_nop_actual':       'nop_certification_current',
        'latitud':                        'latitude',
        'longitud':                       'longitude',
        'altitud':                        'altitude',
        'base':                           'base',
    }, inplace=True)
 
    farmers_df = add_schema_compliance_columns(farmers_df, org_code='BG', lookup_genders_df=lookup_genders)
    farmers_df['inspection_year'] = 2024
    farmers_df['product_code']    = 'COFFEE'
    farmers_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(farmers_df)} unique farmers")
    print(f"  Create plot table: {create_plot_table}")
    return farmers_df, create_plot_table
 
 
def create_bagua_plot_level_dataset(
    bagua_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> pd.DataFrame:
    """
    Bagua Grande plot-level dataset. No aggregation — one row per plot.
    """
    print(f"  Input: {len(bagua_inspections_df)} plot records")
 
    plot_level_columns = [
        'producers_direct_id_productor', 'nombre_productor', 'dni', 'nro_socio',
        'base', 'categoria', 'ubicacion', 'area_total_ha', 'area_cafe',
        'area_crecimiento', 'area_conversion', 'area_otros_cultivos', 'area_bosque',
        'cosecha_estimado_anterior_qq', 'cosecha_acopio_anterior_qq',
        'cosecha_estimado_actual_qq', 'cosecha_estimado_actual_kg',
        'rendimiento_actual_kgha', 'fecha_ultimo_control_interno',
        'nombre_inspector_interno', 'resultado_control_interno',
        'fecha_inicio_conversion', 'certificacion_ue_rtpo_anterior',
        'certificacion_ue_rtpo_actual', 'certificacion_nop_actual',
        'latitud', 'longitud', 'altitud', 'zona_utm', 'x_este', 'y_norte',
        'numero_parcelas', 'org_code'
    ]
    existing_columns = [c for c in plot_level_columns if c in bagua_inspections_df.columns]
    plots_df = bagua_inspections_df[existing_columns].copy()
 
    if 'numero_parcelas' in plots_df.columns:
        plots_df.rename(columns={'numero_parcelas': 'number_of_plots'}, inplace=True)
 
    plots_df.rename(columns={
        'producers_direct_id_productor':  'pd_farmer_id',
        'nombre_productor':               'farmer_name',
        'dni':                            'national_id',
        'nro_socio':                      'membership_number',
        'ubicacion':                      'location',
        'nombre_parcela':                 'plot_name',
        'categoria':                      'category',
        'area_total_ha':                  'total_area_ha',
        'area_cafe':                      'coffee_area_ha',
        'area_crecimiento':               'growing_area_ha',
        'area_conversion':                'conversion_area_ha',
        'area_otros_cultivos':            'other_crops_area_ha',
        'area_bosque':                    'forest_area_ha',
        'cosecha_estimado_anterior_qq':   'previous_year_estimate_local_unit',
        'cosecha_acopio_anterior_qq':     'previous_year_real_local_unit',
        'cosecha_estimado_actual_qq':     'current_year_estimate_local_unit',
        'cosecha_estimado_actual_kg':     'current_year_estimate_kg',
        'rendimiento_actual_kgha':        'real_yield_kgha',
        'fecha_ultimo_control_interno':   'last_internal_control_date',
        'nombre_inspector_interno':       'internal_inspector_name',
        'resultado_control_interno':      'internal_control_result',
        'fecha_inicio_conversion':        'conversion_start_date',
        'certificacion_ue_rtpo_anterior': 'eu_certification_previous',
        'certificacion_ue_rtpo_actual':   'eu_certification_current',
        'certificacion_nop_actual':       'nop_certification_current',
        'latitud':                        'latitude',
        'longitud':                       'longitude',
        'altitud':                        'altitude',
        'base':                           'base',
    }, inplace=True)
 
    if len(plots_df) > 0:
        plots_df = add_schema_compliance_columns(plots_df, org_code='BG', lookup_genders_df=lookup_genders)
        plots_df['inspection_year'] = 2024
        plots_df['product_code']    = 'COFFEE'
        plots_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(plots_df)} plot records")
    return plots_df
 
 
# =============================================================================
# HUADQUIÑA
# =============================================================================
 
def create_huadquina_farmer_level_dataset(
    hu_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> tuple[pd.DataFrame, bool]:
    """
    Huadquiña farmer-level dataset.
    Auto-detects granularity: if plot-level data, aggregates to farmer level.
 
    Returns:
        (farmers_df, create_plot_table)
    """
    print("Processing Huadquiña...")
    print(f"  Input: {len(hu_inspections_df)} records")
 
    farmer_counts = hu_inspections_df['producers_direct_id_productor'].value_counts()
    max_plots_per_farmer = farmer_counts.max()
 
    if max_plots_per_farmer > 1:
        print(f"  📊 Plot-level data detected (max {max_plots_per_farmer} plots per farmer)")
        create_plot_table = True
 
        farmers_df = hu_inspections_df.groupby('producers_direct_id_productor').agg({
            'nombre_productor':               'first',
            'dni':                            'first',
            'nro_socio':                      'first',
            'telefono':                       'first',
            'categoria':                      lambda x: ','.join(x.unique()),
            'org_code':                       'first',
            'ubicacion':                      'first',
            'area_total_ha':                  'sum',
            'area_cafe':                      'sum',
            'area_crecimiento':               'sum',
            'area_otros_cultivos':            'sum',
            'area_bosque':                    'sum',
            'area_purma':                     'sum',
            'area_cultivable':                'sum',
            'cosecha_estimado_anterior_qq':   'sum',
            'cosecha_acopio_anterior_qq':     'sum',
            'cosecha_estimado_actual_qq':     'sum',
            'rendimiento_actual_qqha':        'mean',
            'fecha_ultimo_control_interno':   'first',
            'nombre_inspector_interno':       'first',
            'resultado_control_interno':      'first',
            'fecha_inicio_conversion':        'first',
            'fecha_ultimo_control_externo':   'first',
            'certificacion_ue_rtpo_anterior': 'first',
            'certificacion_ue_rtpo_actual':   'first',
            'certificacion_nop_actual':       'first',
            'latitud':                        'first',
            'longitud':                       'first',
            'altitud':                        'first',
            'zona_utm':                       'first',
            'x_este':                         'first',
            'y_norte':                        'first',
            'punto_muestreo':                 'first',
        }).reset_index()
 
    else:
        print(f"  📊 Farmer-level data detected (1 row per farmer)")
        create_plot_table = False
 
        farmer_level_columns = [
            'producers_direct_id_productor', 'nombre_productor', 'dni', 'nro_socio',
            'telefono', 'categoria', 'ubicacion', 'area_total_ha', 'area_cafe',
            'area_crecimiento', 'area_otros_cultivos', 'area_bosque', 'area_purma',
            'area_cultivable', 'cosecha_estimado_anterior_qq', 'cosecha_acopio_anterior_qq',
            'cosecha_estimado_actual_qq', 'rendimiento_actual_qqha',
            'fecha_ultimo_control_interno', 'nombre_inspector_interno',
            'resultado_control_interno', 'fecha_inicio_conversion',
            'fecha_ultimo_control_externo', 'certificacion_ue_rtpo_anterior',
            'certificacion_ue_rtpo_actual', 'certificacion_nop_actual',
            'latitud', 'longitud', 'altitud', 'zona_utm', 'x_este', 'y_norte',
            'punto_muestreo', 'numero_parcelas', 'org_code', 'sector', 'cupo_qq'
        ]
        existing_columns = [c for c in farmer_level_columns if c in hu_inspections_df.columns]
        farmers_df = hu_inspections_df[existing_columns].copy()
 
    if 'numero_parcelas' in farmers_df.columns:
        farmers_df.rename(columns={'numero_parcelas': 'number_of_plots'}, inplace=True)
 
    farmers_df.rename(columns={
        'producers_direct_id_productor':  'pd_farmer_id',
        'nombre_productor':               'farmer_name',
        'dni':                            'national_id',
        'nro_socio':                      'membership_number',
        'telefono':                       'telephone',
        'ubicacion':                      'location',
        'categoria':                      'category',
        'area_total_ha':                  'total_area_ha',
        'area_cafe':                      'coffee_area_ha',
        'area_crecimiento':               'growing_area_ha',
        'area_otros_cultivos':            'other_crops_area_ha',
        'area_bosque':                    'forest_area_ha',
        'area_purma':                     'purma_area_ha',
        'area_cultivable':                'cultivable_area_ha',
        'cosecha_estimado_anterior_qq':   'previous_year_estimate_local_unit',
        'cosecha_acopio_anterior_qq':     'previous_year_real_local_unit',
        'cosecha_estimado_actual_qq':     'current_year_estimate_local_unit',
        'rendimiento_actual_qqha':        'real_yield_local_unit_ha',
        'fecha_ultimo_control_interno':   'last_internal_control_date',
        'nombre_inspector_interno':       'internal_inspector_name',
        'resultado_control_interno':      'internal_control_result',
        'fecha_inicio_conversion':        'conversion_start_date',
        'fecha_ultimo_control_externo':   'last_external_control_date',
        'certificacion_ue_rtpo_anterior': 'eu_certification_previous',
        'certificacion_ue_rtpo_actual':   'eu_certification_current',
        'certificacion_nop_actual':       'nop_certification_current',
        'latitud':                        'latitude',
        'longitud':                       'longitude',
        'altitud':                        'altitude',
        'zona_utm':                       'utm_zone',
        'x_este':                         'x_east',
        'y_norte':                        'y_north',
        'punto_muestreo':                 'sampling_point',
    }, inplace=True)
 
    farmers_df = add_schema_compliance_columns(farmers_df, org_code='HU', lookup_genders_df=lookup_genders)
    farmers_df['inspection_year'] = 2025
    farmers_df['product_code']    = 'COFFEE'
    farmers_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(farmers_df)} unique farmers")
    print(f"  Create plot table: {create_plot_table}")
    return farmers_df, create_plot_table
 
 
def create_huadquina_plot_level_dataset(
    hu_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> pd.DataFrame:
    """Huadquiña plot-level dataset. No aggregation — one row per plot."""
    print(f"  Input: {len(hu_inspections_df)} plot records")
 
    plot_level_columns = [
        'producers_direct_id_productor', 'nombre_productor', 'dni', 'nro_socio',
        'telefono', 'categoria', 'ubicacion', 'area_total_ha', 'area_cafe',
        'area_crecimiento', 'area_otros_cultivos', 'area_bosque', 'area_purma',
        'area_cultivable', 'cosecha_estimado_anterior_qq', 'cosecha_acopio_anterior_qq',
        'cosecha_estimado_actual_qq', 'rendimiento_actual_qqha',
        'fecha_ultimo_control_interno', 'nombre_inspector_interno',
        'resultado_control_interno', 'fecha_inicio_conversion',
        'fecha_ultimo_control_externo', 'certificacion_ue_rtpo_anterior',
        'certificacion_ue_rtpo_actual', 'certificacion_nop_actual',
        'latitud', 'longitud', 'altitud', 'zona_utm', 'x_este', 'y_norte',
        'punto_muestreo', 'numero_parcelas', 'org_code'
    ]
    existing_columns = [c for c in plot_level_columns if c in hu_inspections_df.columns]
    plots_df = hu_inspections_df[existing_columns].copy()
 
    if 'numero_parcelas' in plots_df.columns:
        plots_df.rename(columns={'numero_parcelas': 'number_of_plots'}, inplace=True)
 
    plots_df.rename(columns={
        'producers_direct_id_productor':  'pd_farmer_id',
        'nombre_productor':               'farmer_name',
        'dni':                            'national_id',
        'nro_socio':                      'membership_number',
        'telefono':                       'telephone',
        'ubicacion':                      'location',
        'categoria':                      'category',
        'area_total_ha':                  'total_area_ha',
        'area_cafe':                      'coffee_area_ha',
        'area_crecimiento':               'growing_area_ha',
        'area_otros_cultivos':            'other_crops_area_ha',
        'area_bosque':                    'forest_area_ha',
        'area_purma':                     'purma_area_ha',
        'area_cultivable':                'cultivable_area_ha',
        'cosecha_estimado_anterior_qq':   'previous_year_estimate_local_unit',
        'cosecha_acopio_anterior_qq':     'previous_year_real_local_unit',
        'cosecha_estimado_actual_qq':     'current_year_estimate_local_unit',
        'rendimiento_actual_qqha':        'real_yield_local_unit_ha',
        'fecha_ultimo_control_interno':   'last_internal_control_date',
        'nombre_inspector_interno':       'internal_inspector_name',
        'resultado_control_interno':      'internal_control_result',
        'fecha_inicio_conversion':        'conversion_start_date',
        'fecha_ultimo_control_externo':   'last_external_control_date',
        'certificacion_ue_rtpo_anterior': 'eu_certification_previous',
        'certificacion_ue_rtpo_actual':   'eu_certification_current',
        'certificacion_nop_actual':       'nop_certification_current',
        'latitud':                        'latitude',
        'longitud':                       'longitude',
        'altitud':                        'altitude',
        'zona_utm':                       'utm_zone',
        'x_este':                         'x_east',
        'y_norte':                        'y_north',
        'punto_muestreo':                 'sampling_point',
    }, inplace=True)
 
    if len(plots_df) > 0:
        plots_df = add_schema_compliance_columns(plots_df, org_code='HU', lookup_genders_df=lookup_genders)
        plots_df['inspection_year'] = 2025
        plots_df['product_code']    = 'COFFEE'
        plots_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(plots_df)} plot records")
    return plots_df
 
 
# =============================================================================
# CHIRINOS  ← MULTI-YEAR: no aggregation, no granularity detection
# =============================================================================
 
def create_chirinos_farmer_level_dataset(
    chirinos_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> tuple[pd.DataFrame, bool]:
    """
    Chirinos farmer-level dataset.
 
    IMPORTANT — MULTI-YEAR BEHAVIOUR:
        Stage 1 outputs one row per farmer per year (via año_inspeccion column).
        We do NOT aggregate here. The result is N rows per farmer where N = years present.
 
        In the orchestrator (data_integrator.py):
            - all_farmers_temporal  → feeds farmer_level_inspections + farmer_level_harvests
            - all_farmers_identity  → deduplicated to 1 row/farmer (latest year) for
                                      farmers_data + farmers_addresses
 
        Chirinos has NO plot-level data → always returns create_plot_table = False.
 
    Returns:
        (farmers_df, False)
    """
    print("Processing Chirinos (multi-year)...")
    print(f"  Input: {len(chirinos_inspections_df)} records "
          f"({chirinos_inspections_df['año_inspeccion'].nunique()} years)")
 
    # --- NO granularity detection, NO groupby aggregation ---
    # Stage 1 already gives us exactly 1 row per farmer per year.
    # Select the columns we need (use existing only — not all years have all columns).
    farmer_level_columns = [
        'producers_direct_id_productor', 'nombre_productor', 'dni', 'nro_socio', 'telefono',
        'categoria', 'categoria_propuesta', 'genero', 'fecha_nacimiento', 'fecha_ingreso',
        'base', 'caserio', 'distrito', 'provincia',
        'area_total_ha', 'area_cafe', 'area_crecimiento', 'area_otros_cultivos',
        'area_bosque', 'area_bosque_secundario', 'area_purma', 'area_invernadero_pasto',
        'cosecha_estimado_anterior_kg', 'cosecha_estimado_anterior_qq',
        'cosecha_acopio_anterior_kg', 'cosecha_estimado_actual_qq',
        'cosecha_estimado_actual_kg', 'rendimiento_estimado_qqha',
        'compromiso_acopio_actual_qq', 'numero_parcelas',
        'fecha_ultimo_control_interno', 'nombre_inspector_interno',
        'dni_inspector_interno', 'fecha_inicio_conversion',
        'estado_socio', 'numero_trabajadores_temporales', 'numero_trabajadores_mujeres',
        'certificacion_ue_rtpo_anterior', 'sellos', 'certificacion',
        'latitud', 'longitud', 'altitud',
        'org_code',
        'año_inspeccion',   # ← carry through for orchestrator deduplication
    ]
    existing_columns = [c for c in farmer_level_columns if c in chirinos_inspections_df.columns]
    farmers_df = chirinos_inspections_df[existing_columns].copy()
 
    farmers_df.rename(columns={
        'producers_direct_id_productor':  'pd_farmer_id',
        'nombre_productor':               'farmer_name',
        'dni':                            'national_id',
        'telefono':                       'telephone',
        'nro_socio':                      'membership_number',
        'base':                           'base',
        'caserio':                        'village',
        'distrito':                       'district',
        'provincia':                      'province',
        'categoria':                      'category',
        'categoria_propuesta':            'proposed_category',
        'genero':                         'gender',
        'fecha_nacimiento':               'birth_date',
        'fecha_ingreso':                  'entry_date',
        'nombre_inspector_interno':       'internal_inspector_name',
        'dni_inspector_interno':          'internal_inspector_dni',
        'fecha_inicio_conversion':        'conversion_start_date',
        'fecha_ultimo_control_interno':   'last_internal_control_date',
        'area_total_ha':                  'total_area_ha',
        'area_cafe':                      'coffee_area_ha',
        'area_crecimiento':               'growing_area_ha',
        'area_invernadero_pasto':         'greenhouse_pasture_area_ha',
        'area_purma':                     'purma_area_ha',
        'area_bosque':                    'forest_area_ha',
        'area_bosque_secundario':         'secondary_forest_area_ha',
        'area_otros_cultivos':            'other_crops_area_ha',
        'cosecha_estimado_anterior_kg':   'previous_year_estimate_kg',
        'cosecha_estimado_anterior_qq':   'previous_year_estimate_local_unit',
        'cosecha_acopio_anterior_kg':     'previous_year_real_kg',
        'cosecha_estimado_actual_qq':     'current_year_estimate_local_unit',
        'cosecha_estimado_actual_kg':     'current_year_estimate_kg',
        'rendimiento_estimado_qqha':      'estimated_yield_local_unit_ha',
        'compromiso_acopio_actual_qq':    'current_year_commitment_local_unit',
        'numero_parcelas':                'number_of_plots',
        'latitud':                        'latitude',
        'longitud':                       'longitude',
        'altitud':                        'altitude',
        'estado_socio':                   'member_status',
        'numero_trabajadores_temporales': 'temporary_workers_count',
        'numero_trabajadores_mujeres':    'female_workers_count',
        'certificacion_ue_rtpo_anterior': 'eu_certification_previous',
        'sellos':                         'certification_seals',
        'certificacion':                  'certification_type',
        'año_inspeccion':                 'inspection_year',  # Spanish→English here
    }, inplace=True)
 
    farmers_df = add_schema_compliance_columns(farmers_df, org_code='CH', lookup_genders_df=lookup_genders)
    # NOTE: inspection_year is NOT hardcoded — it comes from the data (one value per row)
    farmers_df['product_code'] = 'COFFEE'
    farmers_df['unit_code']    = 'QQ'
 
    years_in_output = sorted(farmers_df['inspection_year'].unique())
    print(f"  Output: {len(farmers_df)} records across years {years_in_output}")
    print(f"  Create plot table: False (Chirinos has no plot-level data)")
    return farmers_df, False
 
 
def create_chirinos_plot_level_dataset(
    chirinos_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> pd.DataFrame:
    """
    Chirinos plot-level dataset.
    Chirinos source data has no individual plot rows — returns empty DataFrame.
    The orchestrator will skip adding this to plot_tables.
    """
    print("  Chirinos: no plot-level data — returning empty DataFrame")
    return pd.DataFrame()
 
 
# =============================================================================
# NORANDINO
# =============================================================================
 
def create_norandino_farmer_level_dataset(
    norandino_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> pd.DataFrame:
    """
    Norandino farmer-level dataset.
    Already 1 row per farmer from Stage 1 — no aggregation needed.
    Note: returns only farmers_df (no create_plot_table flag) — special case in orchestrator.
    """
    print("Processing Norandino...")
    print(f"  Input: {len(norandino_inspections_df)} farmer records")
 
    farmer_level_columns = [
        'producers_direct_id_productor', 'nombre_productor', 'dni', 'telefono',
        'caserio', 'distrito', 'provincia', 'departamento', 'estado_socio',
        'categoria', 'genero', 'fecha_nacimiento', 'area_rehabilitacion',
        'area_total_ha', 'area_cafe', 'area_crecimiento', 'area_otros_cultivos',
        'cosecha_estimado_actual_qq', 'cosecha_real_anterior',
        'latitud', 'longitud', 'altitud', 'fecha_ultimo_control_interno',
        'numero_parcelas', 'org_code'
    ]
    existing_columns = [c for c in farmer_level_columns if c in norandino_inspections_df.columns]
    farmers_df = norandino_inspections_df[existing_columns].copy()
 
    farmers_df.rename(columns={
        'producers_direct_id_productor': 'pd_farmer_id',
        'nombre_productor':              'farmer_name',
        'dni':                           'national_id',
        'telefono':                      'telephone',
        'caserio':                       'village',
        'distrito':                      'district',
        'provincia':                     'province',
        'departamento':                  'department',
        'estado_socio':                  'member_status',
        'categoria':                     'category',
        'genero':                        'gender',
        'fecha_nacimiento':              'birth_date',
        'area_rehabilitacion':           'rehabilitation_area_ha',
        'area_total_ha':                 'total_area_ha',
        'area_cafe':                     'coffee_area_ha',
        'area_crecimiento':              'growing_area_ha',
        'area_otros_cultivos':           'other_crops_area_ha',
        'cosecha_estimado_actual_qq':    'current_year_estimate_local_unit',
        'cosecha_real_anterior':         'previous_year_real_local_unit',
        'latitud':                       'latitude',
        'longitud':                      'longitude',
        'altitud':                       'altitude',
        'fecha_ultimo_control_interno':  'last_internal_control_date',
        'numero_parcelas':               'number_of_plots',
    }, inplace=True)
 
    farmers_df = add_schema_compliance_columns(farmers_df, org_code='NO', lookup_genders_df=lookup_genders)
    farmers_df['inspection_year'] = 2024
    farmers_df['product_code']    = 'COFFEE'
    farmers_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(farmers_df)} unique farmers")
    return farmers_df
 
 
def create_norandino_plot_level_dataset(
    norandino_wide_path: str | Path,
    lookup_genders: pd.DataFrame
) -> pd.DataFrame:
    """
    Norandino plot-level dataset.
    Loads the wide-format intermediate file (norandino_with_all_plots_data.pkl)
    and unpivots up to 10 plot columns per farmer into individual plot rows.
 
    Args:
        norandino_wide_path: Path to norandino_with_all_plots_data.pkl
        lookup_genders:      Lookup DataFrame for gender mapping
 
    Returns:
        plots_df with one row per named plot
    """
    print("  Loading Norandino wide-format plots data...")
    norandino_wide_df = pd.read_pickle(norandino_wide_path)
    print(f"  Loaded: {len(norandino_wide_df)} farmer records with plot columns")
 
    plot_records = []
 
    for _, farmer_row in norandino_wide_df.iterrows():
 
        for plot_num in range(1, 11):
            plot_name_col      = f'parcelas_p{plot_num}/nom_parcela_p{plot_num}'
            coffee_area_col    = f'parcelas_p{plot_num}/ha_cafe_prod_p{plot_num}'
            growth_area_col    = f'parcelas_p{plot_num}/ha_cafe_crec_p{plot_num}'
            cacao_prod_col     = f'parcelas_p{plot_num}/ha_cacao_prod_p{plot_num}'
            cacao_crec_col     = f'parcelas_p{plot_num}/ha_cacao_crec_p{plot_num}'
            panela_prod_col    = f'parcelas_p{plot_num}/ha_panela_prod_p{plot_num}'
            panela_crec_col    = f'parcelas_p{plot_num}/ha_panela_crec_p{plot_num}'
            otros_prod_col     = f'parcelas_p{plot_num}/ha_otro_p_p{plot_num}'
            otros_crec_col     = f'parcelas_p{plot_num}/ha_otro_c_p{plot_num}'
            estimate_col       = f'parcelas_p{plot_num}/est_prod_cafe_qq_p{plot_num}'
            prev_year_real_col = f'parcelas_p{plot_num}/cultivo_cafe_cultivo_anterior_p{plot_num}'
 
            # Skip plots with no name
            if (plot_name_col not in farmer_row or
                    pd.isna(farmer_row[plot_name_col]) or
                    str(farmer_row[plot_name_col]).strip() == ''):
                continue
 
            def _to_num(val):
                result = pd.to_numeric(val, errors='coerce')
                return 0 if pd.isna(result) else result
 
            coffee_area     = _to_num(farmer_row.get(coffee_area_col, 0))
            growth_area     = _to_num(farmer_row.get(growth_area_col, 0))
            cacao_prod_area = _to_num(farmer_row.get(cacao_prod_col, 0))
            cacao_crec_area = _to_num(farmer_row.get(cacao_crec_col, 0))
            panela_prod     = _to_num(farmer_row.get(panela_prod_col, 0))
            panela_crec     = _to_num(farmer_row.get(panela_crec_col, 0))
            otros_prod      = _to_num(farmer_row.get(otros_prod_col, 0))
            otros_crec      = _to_num(farmer_row.get(otros_crec_col, 0))
 
            other_crops_area = (cacao_prod_area + cacao_crec_area + panela_prod +
                                panela_crec + otros_prod + otros_crec)
            total_area = coffee_area + growth_area + other_crops_area
 
            plot_records.append({
                'pd_farmer_id':                    farmer_row.get('producers_direct_id_productor', ''),
                'farmer_name':                     farmer_row.get('nombre_productor', ''),
                'national_id':                     farmer_row.get('dni', ''),
                'telephone':                       farmer_row.get('telefono', ''),
                'plot_name':                       farmer_row[plot_name_col],
                'village':                         farmer_row.get('caserio', ''),
                'district':                        farmer_row.get('distrito', ''),
                'province':                        farmer_row.get('provincia', ''),
                'department':                      farmer_row.get('departamento', ''),
                'member_status':                   farmer_row.get('estado_socio', ''),
                'category':                        farmer_row.get('categoria', ''),
                'gender':                          farmer_row.get('genero', ''),
                'birth_date':                      farmer_row.get('fecha_nacimiento'),
                'total_area_ha':                   total_area,
                'coffee_area_ha':                  coffee_area,
                'growing_area_ha':                 growth_area,
                'other_crops_area_ha':             other_crops_area,
                'current_year_estimate_local_unit': _to_num(farmer_row.get(estimate_col, 0)),
                'previous_year_real_local_unit':    _to_num(farmer_row.get(prev_year_real_col, 0)),
                'latitude':                        farmer_row.get('latitud'),
                'longitude':                       farmer_row.get('longitud'),
                'altitude':                        farmer_row.get('altitud'),
                'org_code':                        farmer_row.get('org_code'),
                'last_internal_control_date':      farmer_row.get('fecha_ultimo_control_interno'),
                'number_of_plots':                 1,
                'rehabilitation_area_ha':          0,
            })
 
    plots_df = pd.DataFrame(plot_records)
 
    if len(plots_df) > 0:
        plots_df = add_schema_compliance_columns(plots_df, org_code='NO', lookup_genders_df=lookup_genders)
        plots_df['inspection_year'] = 2024
        plots_df['product_code']    = 'COFFEE'
        plots_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(plots_df)} plot records")
    return plots_df
 
 
# =============================================================================
# APROCASSI
# =============================================================================
 
def create_aprocassi_farmer_level_dataset(
    aprocassi_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> tuple[pd.DataFrame, bool]:
    """
    Aprocassi farmer-level dataset.
    Auto-detects granularity: if plot-level data, aggregates to farmer level.
 
    Returns:
        (farmers_df, create_plot_table)
    """
    print("Processing Aprocassi...")
    print(f"  Input: {len(aprocassi_inspections_df)} records")
 
    farmer_counts = aprocassi_inspections_df['producers_direct_id_productor'].value_counts()
    max_plots_per_farmer = farmer_counts.max()
 
    if max_plots_per_farmer > 1:
        print(f"  📊 Plot-level data detected (max {max_plots_per_farmer} plots per farmer)")
        create_plot_table = True
 
        farmers_df = aprocassi_inspections_df.groupby('producers_direct_id_productor').agg({
            'nombre_productor':             'first',
            'dni':                          'first',
            'distrito':                     'first',
            'base':                         'first',
            'categoria':                    lambda x: ','.join(x.unique()),
            'org_code':                     'first',
            'area_total_ha':                'sum',
            'area_cafe':                    'sum',
            'area_crecimiento':             'sum',
            'area_rehabilitacion':          'sum',
            'area_otros_cultivos':          'sum',
            'area_bosque':                  'sum',
            'cosecha_estimado_anterior_qq': 'sum',
            'cosecha_acopio_anterior_qq':   'sum',
            'cosecha_estimado_actual_qq':   'sum',
            'latitud':                      'first',
            'longitud':                     'first',
            'altitud':                      'first',
            'zona_utm':                     'first',
            'x_este':                       'first',
            'y_norte':                      'first',
            'nombre_parcela':               'size',   # count of plots
        }).reset_index()
 
        farmers_df.rename(columns={'nombre_parcela': 'number_of_plots'}, inplace=True)
 
    else:
        print(f"  📊 Farmer-level data detected (1 row per farmer)")
        create_plot_table = False
 
        farmer_level_columns = [
            'producers_direct_id_productor', 'nombre_productor', 'dni', 'distrito',
            'base', 'categoria', 'area_total_ha', 'area_cafe', 'area_crecimiento',
            'area_rehabilitacion', 'area_otros_cultivos', 'area_bosque',
            'cosecha_estimado_anterior_qq', 'cosecha_acopio_anterior_qq',
            'cosecha_estimado_actual_qq', 'latitud', 'longitud', 'altitud',
            'zona_utm', 'x_este', 'y_norte', 'numero_parcelas', 'org_code'
        ]
        existing_columns = [c for c in farmer_level_columns if c in aprocassi_inspections_df.columns]
        farmers_df = aprocassi_inspections_df[existing_columns].copy()
 
    if 'numero_parcelas' in farmers_df.columns:
        farmers_df.rename(columns={'numero_parcelas': 'number_of_plots'}, inplace=True)
 
    farmers_df.rename(columns={
        'producers_direct_id_productor':  'pd_farmer_id',
        'nombre_productor':               'farmer_name',
        'dni':                            'national_id',
        'distrito':                       'district',
        'base':                           'base',
        'categoria':                      'category',
        'area_total_ha':                  'total_area_ha',
        'area_cafe':                      'coffee_area_ha',
        'area_crecimiento':               'growing_area_ha',
        'area_rehabilitacion':            'rehabilitation_area_ha',
        'area_otros_cultivos':            'other_crops_area_ha',
        'area_bosque':                    'forest_area_ha',
        'cosecha_estimado_anterior_qq':   'previous_year_estimate_local_unit',
        'cosecha_acopio_anterior_qq':     'previous_year_real_local_unit',
        'cosecha_estimado_actual_qq':     'current_year_estimate_local_unit',
        'latitud':                        'latitude',
        'longitud':                       'longitude',
        'altitud':                        'altitude',
        'zona_utm':                       'utm_zone',
        'x_este':                         'x_east',
        'y_norte':                        'y_north',
    }, inplace=True)
 
    farmers_df = add_schema_compliance_columns(farmers_df, org_code='AP', lookup_genders_df=lookup_genders)
    farmers_df['inspection_year'] = 2024
    farmers_df['product_code']    = 'COFFEE'
    farmers_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(farmers_df)} unique farmers")
    print(f"  Create plot table: {create_plot_table}")
    return farmers_df, create_plot_table
 
 
def create_aprocassi_plot_level_dataset(
    aprocassi_inspections_df: pd.DataFrame,
    lookup_genders: pd.DataFrame
) -> pd.DataFrame:
    """Aprocassi plot-level dataset. No aggregation — one row per plot."""
    print(f"  Input: {len(aprocassi_inspections_df)} plot records")
 
    plot_level_columns = [
        'producers_direct_id_productor', 'nombre_productor', 'dni', 'distrito',
        'base', 'categoria', 'area_total_ha', 'area_cafe', 'area_crecimiento',
        'area_rehabilitacion', 'area_otros_cultivos', 'area_bosque',
        'cosecha_estimado_anterior_qq', 'cosecha_acopio_anterior_qq',
        'cosecha_estimado_actual_qq', 'latitud', 'longitud', 'altitud',
        'zona_utm', 'x_este', 'y_norte', 'numero_parcelas', 'org_code'
    ]
    existing_columns = [c for c in plot_level_columns if c in aprocassi_inspections_df.columns]
    plots_df = aprocassi_inspections_df[existing_columns].copy()
 
    if 'numero_parcelas' in plots_df.columns:
        plots_df.rename(columns={'numero_parcelas': 'number_of_plots'}, inplace=True)
 
    plots_df.rename(columns={
        'producers_direct_id_productor':  'pd_farmer_id',
        'nombre_productor':               'farmer_name',
        'dni':                            'national_id',
        'distrito':                       'district',
        'base':                           'base',
        'categoria':                      'category',
        'area_total_ha':                  'total_area_ha',
        'area_cafe':                      'coffee_area_ha',
        'area_crecimiento':               'growing_area_ha',
        'area_rehabilitacion':            'rehabilitation_area_ha',
        'area_otros_cultivos':            'other_crops_area_ha',
        'area_bosque':                    'forest_area_ha',
        'cosecha_estimado_anterior_qq':   'previous_year_estimate_local_unit',
        'cosecha_acopio_anterior_qq':     'previous_year_real_local_unit',
        'cosecha_estimado_actual_qq':     'current_year_estimate_local_unit',
        'latitud':                        'latitude',
        'longitud':                       'longitude',
        'altitud':                        'altitude',
        'zona_utm':                       'utm_zone',
        'x_este':                         'x_east',
        'y_norte':                        'y_north',
    }, inplace=True)
 
    if len(plots_df) > 0:
        plots_df = add_schema_compliance_columns(plots_df, org_code='AP', lookup_genders_df=lookup_genders)
        plots_df['inspection_year'] = 2024
        plots_df['product_code']    = 'COFFEE'
        plots_df['unit_code']       = 'QQ'
 
    print(f"  Output: {len(plots_df)} plot records")
    return plots_df