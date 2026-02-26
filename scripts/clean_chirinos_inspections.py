"""
Runner Script: Clean Chirinos Inspections (Comprehensive, Multi-Year)

Uses ChirinosInspectionsCleaner to load, harmonize and concatenate
inspection files from 2020 to 2024 into a single comprehensive dataset.

Features:
- Multi-year loading with consistent column naming
- TOTAL row removal
- Data type standardization (after concat)
- Summary statistics per year
- Output as pickle + Excel

Usage:
    python scripts/clean_chirinos_inspections.py
"""

import sys
import os
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.stage1_cleaning.inspections.chirinos_inspections_cleaner import ChirinosInspectionsCleaner


def _build_data_dictionary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds an English-language data dictionary from the combined cleaned dataset.
    Includes Spanish column name, English translation, category, data type,
    years with data, fill rate per year, and a sample value.
    """

    # ── English translations ────────────────────────────────────────────────
    translations = {
        # Identity
        'dni':                              'National ID (DNI)',
        'año_inspeccion':                   'Inspection Year',
        'nro_socio':                        'Member Number',
        'nombre_productor':                 'Farmer Name',
        'dni_verificacion':                 'National ID (verification copy)',
        # Location
        'base':                             'Base / Local Group',
        'caserio':                          'Village / Hamlet',
        'distrito':                         'District',
        'provincia':                        'Province',
        'direccion':                        'Address',
        # Personal
        'genero':                           'Gender',
        'fecha_nacimiento':                 'Date of Birth',
        'edad_socio':                       'Age',
        'rango_edad':                       'Age Range',
        'telefono':                         'Phone Number',
        'apellido':                         'Last Name',
        'nombre_socio':                     'First Name',
        # Membership
        'fecha_ingreso':                    'Join Date',
        'fecha_inicio_conversion':          'Organic Conversion Start Date',
        'categoria':                        'Member Category (current year)',
        'categoria_propuesta':              'Proposed Category (next year)',
        'categoria_anterior':               'Member Category (previous year)',
        'estado_socio':                     'Member Status',
        'condicion':                        'Special Condition',
        # Inspection
        'nombre_inspector_interno':         'Internal Inspector Name',
        'dni_inspector_interno':            'Internal Inspector ID',
        'fecha_ultimo_control_interno':     'Internal Inspection Date',
        'resultado_control_interno':        'Internal Inspection Result',
        'control_externo':                  'External Control (years)',
        'insumos_prohibidos':               'Prohibited Inputs Used',
        'dia_inspeccion':                   'Inspection Day',
        'mes_inspeccion':                   'Inspection Month',
        'año_inspeccion_raw':               'Inspection Year (raw from file)',
        # Geolocation
        'latitud':                          'Latitude',
        'longitud':                         'Longitude',
        'altitud':                          'Altitude (masl)',
        'rango_altitud':                    'Altitude Range',
        # Land use — area
        'area_total_ha':                    'Total Farm Area (ha)',
        'area_cafe':                        'Coffee Production Area (ha)',
        'area_crecimiento':                 'Coffee Growth Area (ha)',
        'area_invernadero_pasto':           'Pasture / Greenhouse Area (ha)',
        'area_purma':                       'Fallow / Scrubland Area (ha)',
        'area_reserva':                     'Nature Reserve Area (ha)',
        'area_bosque':                      'Primary Forest Area (ha)',
        'area_bosque_secundario':           'Secondary Forest Area (ha)',
        'area_reforestacion':               'Reforestation Area (ha)',
        'area_reserva_reforestacion':       'Reserve + Reforestation Area (ha)',
        'area_otros_cultivos':              'Other Crops Area (ha)',
        'area_otros_cultivos_detalle':      'Other Crops Area — Detail (ha)',
        'area_maiz':                        'Maize Area (ha)',
        'area_cacao':                       'Cacao Area (ha)',
        'area_cana':                        'Sugar Cane Area (ha)',
        'area_pan_llevar':                  'Subsistence Crops Area (ha)',
        'area_pina':                        'Pineapple Area (ha)',
        'area_platano':                     'Banana Area (ha)',
        'cultivo_total':                    'Total Cultivated Area (ha)',
        'numero_parcelas':                  'Number of Plots',
        # Ranges
        'rango_hectareas':                  'Farm Size Range (ha)',
        'rango_ha_productor':               'Farmer Ha Range',
        # Harvest
        'cosecha_estimado_anterior_qq':     'Previous Year Estimated Harvest (qq)',
        'cosecha_estimado_anterior_kg':     'Previous Year Estimated Harvest (kg)',
        'cosecha_acopio_anterior_kg':       'Previous Year Actual Collection (kg)',
        'cosecha_estimado_actual_qq':       'Current Year Estimated Harvest (qq)',
        'cosecha_estimado_actual_kg':       'Current Year Estimated Harvest (kg)',
        'cosecha_estimado_actual_tm':       'Current Year Estimated Harvest (metric tons)',
        'cosecha_acopio_actual_kg':         'Current Year Actual Collection (kg)',
        'compromiso_acopio_actual_qq':      'Current Year Delivery Commitment (qq)',
        'compromiso_acopio_anterior_qq':    'Previous Year Delivery Commitment (qq)',
        'rendimiento_estimado_qqha':        'Estimated Yield (qq/ha)',
        'rendimiento_kgha':                 'Estimated Yield (kg/ha)',
        'rendimiento_compromiso_kgha':      'Commitment Yield (kg/ha)',
        'saldo_acopio_actual':              'Current Year Collection Balance',
        'pct_cumplimiento_acopio':          'Collection Commitment Fulfilment (%)',
        'qq_autorizados':                   'Authorized Quintals',
        # Certification
        'sellos':                           'Certification Seals (combined)',
        'certificacion':                    'Certification Entity',
        'certificacion_ue_anterior':        'EU Certification — Previous Year',
        'certificacion_ue_actual':          'EU Certification — Current Year',
        'certificacion_nop_anterior':       'NOP Certification — Previous Year',
        'certificacion_nop_actual':         'NOP Certification — Current Year',
        'sello_ra':                         'Rainforest Alliance Seal',
        'sello_utz':                        'UTZ Seal',
        'sello_bf':                         'Bird Friendly Seal',
        'riesgo':                           'Risk Level',
        # Labor
        'numero_trabajadores_temporales':   'Temporary Workers (total)',
        'numero_trabajadores_mujeres':      'Female Workers',
        # Metadata
        'org_code':                         'Organization Code',
        'country_code':                     'Country Code',
    }

    # ── Category mapping ────────────────────────────────────────────────────
    category_map = {
        'dni':                              'Identity',
        'año_inspeccion':                   'Identity',
        'nro_socio':                        'Identity',
        'nombre_productor':                 'Identity',
        'dni_verificacion':                 'Identity',
        'base':                             'Location',
        'caserio':                          'Location',
        'distrito':                         'Location',
        'provincia':                        'Location',
        'direccion':                        'Location',
        'genero':                           'Personal Info',
        'fecha_nacimiento':                 'Personal Info',
        'edad_socio':                       'Personal Info',
        'rango_edad':                       'Personal Info',
        'telefono':                         'Personal Info',
        'apellido':                         'Personal Info',
        'nombre_socio':                     'Personal Info',
        'fecha_ingreso':                    'Membership',
        'fecha_inicio_conversion':          'Membership',
        'categoria':                        'Membership',
        'categoria_propuesta':              'Membership',
        'categoria_anterior':               'Membership',
        'estado_socio':                     'Membership',
        'condicion':                        'Membership',
        'org_code':                         'Metadata',
        'country_code':                     'Metadata',
        'nombre_inspector_interno':         'Inspection',
        'dni_inspector_interno':            'Inspection',
        'fecha_ultimo_control_interno':     'Inspection',
        'resultado_control_interno':        'Inspection',
        'control_externo':                  'Inspection',
        'insumos_prohibidos':               'Inspection',
        'dia_inspeccion':                   'Inspection',
        'mes_inspeccion':                   'Inspection',
        'año_inspeccion_raw':               'Inspection',
        'latitud':                          'Geolocation',
        'longitud':                         'Geolocation',
        'altitud':                          'Geolocation',
        'rango_altitud':                    'Geolocation',
        'sellos':                           'Certification',
        'certificacion':                    'Certification',
        'certificacion_ue_anterior':        'Certification',
        'certificacion_ue_actual':          'Certification',
        'certificacion_nop_anterior':       'Certification',
        'certificacion_nop_actual':         'Certification',
        'sello_ra':                         'Certification',
        'sello_utz':                        'Certification',
        'sello_bf':                         'Certification',
        'riesgo':                           'Certification',
        'numero_trabajadores_temporales':   'Labor',
        'numero_trabajadores_mujeres':      'Labor',
    }

    years = sorted(df['año_inspeccion'].unique())
    records = []

    for col in df.columns:
        # Determine category
        if col.startswith('area_') or col in ('cultivo_total', 'numero_parcelas'):
            cat = 'Land Use (ha)'
        elif col.startswith('rango_') or col in ('rango_hectareas', 'rango_ha_productor'):
            cat = 'Ranges'
        elif any(k in col for k in ['cosecha_', 'rendimiento_', 'compromiso_acopio',
                                     'acopio', 'saldo_', 'pct_', 'qq_']):
            cat = 'Harvest & Yield'
        else:
            cat = category_map.get(col, 'Other')

        # Fill rate per year
        years_with_data = []
        fill_by_year = {}
        for yr in years:
            yr_data = df.loc[df['año_inspeccion'] == yr, col]
            total = len(yr_data)
            if total == 0:
                continue
            if df[col].dtype == object:
                non_empty = yr_data.replace('', pd.NA).notna().sum()
            else:
                non_empty = yr_data.notna().sum()
            pct = round(non_empty / total * 100, 1)
            fill_by_year[str(yr)] = f"{pct}%"
            if non_empty > 0:
                years_with_data.append(str(yr))

        # Sample value
        sample = df[col].replace('', pd.NA).dropna() if df[col].dtype == object else df[col].dropna()
        sample_val = str(sample.iloc[0]) if len(sample) > 0 else ''

        row = {
            'column_name':          col,
            'english_name':         translations.get(col, '— needs translation'),
            'category':             cat,
            'data_type':            str(df[col].dtype),
            'years_with_data':      ', '.join(years_with_data) if years_with_data else 'none',
        }
        for yr in years:
            row[f'coverage_{yr}'] = fill_by_year.get(str(yr), 'N/A')

        row['sample_value'] = sample_val[:80]
        records.append(row)

    return pd.DataFrame(records).sort_values(['category', 'column_name']).reset_index(drop=True)


def main():
    print("\n" + "=" * 70)
    print("CHIRINOS INSPECTIONS CLEANING — MULTI-YEAR COMPREHENSIVE DATASET")
    print("=" * 70)

    # ========================================================================
    # CONFIGURATION — update filenames to match your actual raw files
    # ========================================================================

    YEAR_FILES = {
        2024: 'data/raw/inspections/chirinos/Data General 2024.xlsx',
        2023: 'data/raw/inspections/chirinos/Data General 2023.xlsx',
        2022: 'data/raw/inspections/chirinos/Data General 2022.xlsx',
        2021: 'data/raw/inspections/chirinos/Data general 2021.xlsx',
        2020: 'data/raw/inspections/chirinos/Data General 2020.xlsx',
    }

    OUTPUT_FILE = 'data/processed/inspections/chirinos/chirinos_comprehensive_all_years.pkl'

    # Files where a specific sheet must be selected (others default to first sheet)
    SHEET_NAMES = {
        2024: 'LPA-General 2024',
    }

    BASE_PATH = None  # Set to your project root if needed

    # ========================================================================
    # VALIDATION — check which files exist before starting
    # ========================================================================

    print("\nChecking input files...")
    missing_files = [
        (year, path) for year, path in YEAR_FILES.items()
        if not Path(path).exists()
    ]
    if missing_files:
        print("\n  ⚠️  The following year files were not found and will be skipped:")
        for year, path in missing_files:
            print(f"    {year}: {path}")
    else:
        print("  ✅ All year files found")

    available_years = [y for y in YEAR_FILES if Path(YEAR_FILES[y]).exists()]
    if not available_years:
        print("\n❌ ERROR: No input files found. Please update YEAR_FILES paths.")
        return

    # ========================================================================
    # PROCESSING
    # ========================================================================

    try:
        cleaner = ChirinosInspectionsCleaner(
            year_files=YEAR_FILES,
            base_path=BASE_PATH,
            sheet_names=SHEET_NAMES
        )

        # Step 1: Clean and concatenate all years
        print("\n" + "─" * 70)
        print("STEP 1: LOADING AND CLEANING ALL YEARS")
        print("─" * 70)
        clean_data = cleaner.clean_all_years()

        # Step 2: Summary
        print("\n" + "─" * 70)
        print("CLEANING SUMMARY")
        print("─" * 70)
        summary = cleaner.get_summary()
        print(f"Total rows:              {summary['total_rows']:,}")
        print(f"Total columns:           {summary['total_columns']}")
        print(f"Years present:           {summary['years_present']}")
        print(f"\nRows per year:")
        for year, count in sorted(summary['rows_per_year'].items()):
            print(f"  {year}: {count:,} farmers")
        print(f"\nUnique farmers (by DNI): {summary['unique_farmers_dni']:,}")
        print(f"Missing DNI:             {summary['missing_dni']:,}")

        # Step 3: Save
        print("\n" + "─" * 70)
        print("STEP 2: SAVING")
        print("─" * 70)

        # Save as pickle
        print(f"  Saving pickle: {OUTPUT_FILE}")
        cleaner.save(OUTPUT_FILE)

        # Save as Excel with data dictionary sheet
        excel_output = OUTPUT_FILE.replace('.pkl', '.xlsx')
        Path(excel_output).parent.mkdir(parents=True, exist_ok=True)
        print(f"  Saving Excel: {excel_output}")

        with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
            # Sheet 1: the data
            clean_data.to_excel(writer, sheet_name='Datos', index=False)

            # Sheet 2: data dictionary
            _build_data_dictionary(clean_data).to_excel(
                writer, sheet_name='Diccionario', index=False
            )

        print("  ✅ Excel file created with data dictionary sheet!")

        # Final summary
        print("\n" + "=" * 70)
        print("✅ CHIRINOS INSPECTIONS CLEANING COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print(f"\nOutput file:   {OUTPUT_FILE}")
        print(f"Total records: {len(clean_data):,}")
        print(f"Total columns: {len(clean_data.columns)}")

        # Column overview grouped by type
        print("\n" + "─" * 70)
        print("OUTPUT COLUMNS OVERVIEW")
        print("─" * 70)

        key_cols = ['dni', 'año_inspeccion', 'nro_socio', 'nombre_productor',
                    'base', 'caserio', 'distrito', 'provincia']
        area_cols = [c for c in clean_data.columns if c.startswith('area_')]
        harvest_cols = [c for c in clean_data.columns
                        if any(k in c for k in ['cosecha_', 'rendimiento_', 'compromiso_'])]
        cert_cols = [c for c in clean_data.columns if 'certificacion' in c or 'sello' in c]
        date_cols = [c for c in clean_data.columns if 'fecha' in c]

        print(f"\nKey identity columns:")
        for col in key_cols:
            if col in clean_data.columns:
                print(f"  - {col}")

        print(f"\nArea columns ({len(area_cols)}):")
        for col in area_cols:
            print(f"  - {col}")

        print(f"\nHarvest columns ({len(harvest_cols)}):")
        for col in harvest_cols:
            print(f"  - {col}")

        print(f"\nCertification / seals columns ({len(cert_cols)}):")
        for col in cert_cols:
            print(f"  - {col}")

        print(f"\nDate columns ({len(date_cols)}):")
        for col in date_cols:
            print(f"  - {col}")

        # Sample rows
        print("\n" + "─" * 70)
        print("SAMPLE DATA (first 3 rows — key columns)")
        print("─" * 70)
        display_cols = ['dni', 'año_inspeccion', 'nombre_productor',
                        'base', 'area_total_ha', 'area_cafe', 'categoria']
        available = [c for c in display_cols if c in clean_data.columns]
        print(clean_data[available].head(3).to_string(index=False))

        print("\n" + "=" * 70 + "\n")

    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
        print("\nMake sure all file paths in YEAR_FILES are correct.")

    except Exception as e:
        print(f"\n❌ ERROR during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()