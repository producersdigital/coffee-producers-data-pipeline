"""
Norandino Inspections Data Cleaner
 
Cleans and standardizes inspection data from Norandino Producer Organization.
Handles massive Excel file (2400+ columns) with plot-level data that needs aggregation.
 
Key features:
- Processes multiple inspection years (2024, 2025) from separate files
- Filters by inspection acceptance, coffee inspection, and cycle year
- Selects ~100 relevant columns from 2400+
- Aggregates data from up to 10 plots per farmer
- Converts area units (m² to ha when needed)
- Generates unique farmer IDs
- Produces two outputs: with plots and farmer-level only
 
Usage:
    from src.stage1_cleaning.inspections.norandino_inspections_cleaner import clean_norandino_inspections
 
    df = clean_norandino_inspections()
"""
 
import pandas as pd
import numpy as np
from pathlib import Path
import sys
 
# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
 
from src.utils.dni_cleaner import DNICleaner
 
# Define DATA_DIR
DATA_DIR = project_root / 'data'
 
# ---------------------------------------------------------------------------
# Multi-year configuration
#
# The Norandino Kobo form accumulates all historical records in one file.
# The 2025 download contains both 2024 and 2025 records (and will contain
# future years too). We filter by 'info_general/ciclo' value to split years.
#
# SOURCE_FILE:  The latest cumulative Kobo export — update filename each year.
# YEARS:        Which cycle values to extract → assigned as inspection_year.
#               Add new years here as data becomes available.
# ---------------------------------------------------------------------------
RAW_DIR = DATA_DIR / 'raw' / 'inspections' / 'norandino'
 
SOURCE_FILE  = RAW_DIR / 'Inspeccion_Interna_Norandino_2025.xlsx'
SOURCE_SHEET = 'Inspeccion Interna Norandino...'  # update if sheet name differs in future exports
 
NORANDINO_YEARS_TO_EXTRACT = [2023, 2024, 2025]   # add future years here
 
 
class NorandinoInspectionsCleaner:
    """
    Clean and standardize Norandino inspection data (multi-year).
 
    This is the most complex cleaner due to:
    - Massive source files with 2400+ columns each
    - Plot-level data (up to 10 plots per farmer)
    - Need to aggregate plot data to farmer level
    - Area unit conversion
    - Multiple inspection years stacked into one output
 
    Attributes:
        data: Cleaned DataFrame (farmer-level, all years)
        data_with_plots: DataFrame with all plot details (all years)
        dni_cleaner: DNI cleaning utility
    """
 
    def __init__(self):
        """Initialize the cleaner with file paths and utilities."""
        self.dni_cleaner = DNICleaner()
 
        # Output directory
        self.output_dir = DATA_DIR / 'processed' / 'inspections' / 'norandino'
        self.output_dir.mkdir(parents=True, exist_ok=True)
 
        self.data = None
        self.data_with_plots = None
 
    def clean(self) -> pd.DataFrame:
        """
        Clean Norandino inspections data for all configured years.
 
        Loads the single cumulative Kobo export, then splits by cycle year.
        Each year's records go through the same cleaning pipeline and get
        an inspection_year label before being stacked into one output.
 
        Returns:
            Cleaned DataFrame with farmer-level inspection data (all years)
        """
        print("\n" + "=" * 60)
        print("CLEANING NORANDINO INSPECTIONS (MULTI-YEAR)")
        print("=" * 60)
 
        if not SOURCE_FILE.exists():
            raise FileNotFoundError(f"Source file not found: {SOURCE_FILE}")
 
        print(f"\n  Reading {SOURCE_FILE.name}...")
        print("  ⚠️  This file has 2400+ columns, may take a moment...")
        try:
            raw_df = pd.read_excel(SOURCE_FILE, sheet_name=SOURCE_SHEET)
        except Exception as e:
            print(f"  ⚠️  Sheet '{SOURCE_SHEET}' not found: {e}")
            print("  Trying first sheet as fallback...")
            raw_df = pd.read_excel(SOURCE_FILE)
 
        print(f"  Loaded {len(raw_df):,} rows, {len(raw_df.columns):,} columns")
 
        # Report available cycle values
        if 'info_general/ciclo' in raw_df.columns:
            available = sorted(raw_df['info_general/ciclo'].dropna().unique())
            print(f"  Cycles found in file: {available}")
            print(f"  Extracting years: {NORANDINO_YEARS_TO_EXTRACT}")
 
        year_dfs = []
        for year in NORANDINO_YEARS_TO_EXTRACT:
            print(f"\n{'─' * 50}")
            print(f"  Processing {year} inspections...")
            print(f"{'─' * 50}")
 
            config = {
                'path':        SOURCE_FILE,
                'sheet':       SOURCE_SHEET,
                'cycle_value': year,
            }
            df = self._clean_single_year(year, config, raw_df=raw_df)
            if df is not None and len(df) > 0:
                year_dfs.append(df)
                print(f"  ✅ {year}: {len(df):,} records cleaned")
            else:
                print(f"  ⚠️  No records found for cycle {year}")
 
        if not year_dfs:
            raise ValueError("No inspection data could be extracted for any year.")
 
        combined = pd.concat(year_dfs, ignore_index=True)
 
        print(f"\n{'=' * 60}")
        years_loaded = [str(y) for y in NORANDINO_YEARS_TO_EXTRACT if
                        any(d['inspection_year'].iloc[0] == y for d in year_dfs if len(d) > 0)]
        print(f"COMBINED: {len(combined):,} records — years: {', '.join(years_loaded)}")
        print(f"{'=' * 60}")
 
        self.data_with_plots = combined.copy()
        return combined
 
    def _clean_single_year(
        self, year: int, config: dict, raw_df: pd.DataFrame = None
    ) -> 'pd.DataFrame | None':
        """
        Apply the full cleaning pipeline to a single year's data.
 
        Args:
            year:    Inspection year (e.g. 2024, 2025)
            config:  Dict with 'path', 'sheet', 'cycle_value'
            raw_df:  Pre-loaded DataFrame (avoids re-reading the file per year)
 
        Returns:
            Cleaned DataFrame for this year, or None on failure.
        """
        # Use pre-loaded df if provided — avoids reading the large file multiple times
        if raw_df is not None:
            df = raw_df.copy()
        else:
            print(f"\n  Reading {config['path'].name}...")
            try:
                df = pd.read_excel(config['path'], sheet_name=config['sheet'])
            except Exception as e:
                print(f"  ⚠️  Sheet '{config['sheet']}' not found: {e}")
                try:
                    df = pd.read_excel(config['path'])
                except Exception as e2:
                    print(f"  ❌ Could not load file: {e2}")
                    return None
 
        # Apply cleaning steps
        df = self._filter_rows(df, config['cycle_value'])
        if len(df) == 0:
            print(f"  ⚠️  No rows passed filters for {year}")
            return None
 
        df = self._select_columns(df)
        df = self._rename_to_standard(df)
        df = self._fix_area_units(df)
        df = self._aggregate_plot_data(df)
        df = self._convert_data_types(df)
 
        # Add inspection_year — canonical column matching Chirinos pattern
        df['inspection_year'] = year
 
        # Add metadata
        df['org_code']    = 'NO'
        df['country_code'] = 'PER'
        df['data_source'] = f"NORANDINO/raw_data/{config['path'].name}"
 
        self._check_data_quality(df, year)
 
        return df
 
    def _filter_rows(self, df: pd.DataFrame, cycle_value: int) -> pd.DataFrame:
        """
        Filter rows by acceptance, coffee inspection, and cycle year.
 
        Args:
            df:           Raw DataFrame
            cycle_value:  Year value to filter on in 'info_general/ciclo'
 
        Returns:
            Filtered DataFrame
        """
        print(f"\n  Filtering rows (cycle={cycle_value})...")
        initial_count = len(df)
 
        # Filter 1: Inspection accepted
        if 'acepta_inspeccion' in df.columns:
            df = df[df['acepta_inspeccion'] == 1]
            print(f"    After acepta_inspeccion==1: {len(df):,} rows")
 
        # Filter 2: Coffee inspection
        # NOTE: We do NOT filter by inspeccion_cafe here so that panela and
        # cacao farmers are also included in the SDL. Dashboards can filter
        # by product type/categoria at query time.
        if 'datos_general/inspeccion_cafe' in df.columns:
            coffee_count  = (df['datos_general/inspeccion_cafe'] == 1).sum()
            other_count   = len(df) - coffee_count
            print(f"    Coffee inspections: {coffee_count:,}, other crops: {other_count:,} "
                  f"(keeping ALL for SDL)")
 
        # Filter 3: Cycle year
        if 'info_general/ciclo' in df.columns:
            df = df[df['info_general/ciclo'] == cycle_value]
            print(f"    After cycle=={cycle_value}: {len(df):,} rows")
        else:
            print(f"  ⚠️  'info_general/ciclo' column not found — not filtering by cycle")
 
        removed = initial_count - len(df)
        print(f"  ✅ Removed {removed:,} rows, kept {len(df):,}")
 
        return df
 
    def _select_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Select ~100 relevant columns from 2400+.
 
        Includes basic info + data for up to 10 plots (p1-p10).
 
        Args:
            df: DataFrame with all columns
 
        Returns:
            DataFrame with selected columns
        """
        print("\n  Selecting relevant columns...")
 
        # Basic information columns
        basic_cols = [
            'info_general/fecha_inspeccion', 'info_general/_gps_latitude',
            'info_general/_gps_longitude', 'info_general/_gps_altitude',
            'info_general/dni', 'datos_general/nombre_completo',
            'datos_general/caserio', 'datos_general/distrito',
            'datos_general/provincia', 'datos_general/departamento',
            'datos_general/estatus_socio', 'datos_general/estatus_cert_actual',
            'datos_general/genero', 'num_parcelas/n_parcelas',
            'datos_general/telefono_productor', 'datos_general/fecha_nacimiento',
            'manejo_agro/area_rehab',
            # Crop type flags (1/0) — tells us which crops were inspected
            'datos_general/inspeccion_cafe',
            'datos_general/inspeccion_panela',
            'datos_general/inspeccion_cacao',
        ]
 
        # Plot-specific columns (p1-p10)
        plot_cols = []
        for i in range(1, 11):  # p1 through p10
            plot_cols.extend([
                f'parcelas_p{i}/nom_parcela_p{i}',
                f'parcelas_p{i}/ha_cafe_prod_p{i}',
                f'parcelas_p{i}/ha_cafe_crec_p{i}',
                f'parcelas_p{i}/ha_cacao_prod_p{i}',
                f'parcelas_p{i}/ha_cacao_crec_p{i}',
                f'parcelas_p{i}/ha_panela_prod_p{i}',
                f'parcelas_p{i}/ha_panela_crec_p{i}',
                f'parcelas_p{i}/ha_otro_p_p{i}',
                f'parcelas_p{i}/ha_otro_c_p{i}',
                f'parcelas_p{i}/manejo_cultivo_p{i}/cultivo_cafe_cultivo_anterior_p{i}',
                f'parcelas_p{i}/est_prod_cafe_qq_p{i}'
            ])
 
        # Combine all columns
        selected_cols = basic_cols + plot_cols
 
        # Select only columns that exist
        existing_cols = [col for col in selected_cols if col in df.columns]
        df = df[existing_cols].copy()
 
        print(f"    Selected {len(existing_cols)} columns from {len(selected_cols)} requested")
 
        return df
 
    def _rename_to_standard(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns to standard names."""
        rename_map = {
            'info_general/fecha_inspeccion':    'fecha_ultimo_control_interno',
            'info_general/_gps_latitude':       'latitud',
            'info_general/_gps_longitude':      'longitud',
            'info_general/_gps_altitude':       'altitud',
            'info_general/dni':                 'dni',
            'datos_general/nombre_completo':    'nombre_productor',
            'datos_general/caserio':            'caserio',
            'datos_general/distrito':           'distrito',
            'datos_general/provincia':          'provincia',
            'datos_general/departamento':       'departamento',
            'datos_general/estatus_socio':      'estado_socio',
            'datos_general/estatus_cert_actual':'categoria',
            'datos_general/genero':             'genero',
            'num_parcelas/n_parcelas':          'numero_parcelas',
            'datos_general/telefono_productor': 'telefono',
            'datos_general/fecha_nacimiento':   'fecha_nacimiento',
            'manejo_agro/area_rehab':           'area_rehabilitacion',
            'datos_general/inspeccion_cafe':    'inspeccion_cafe',
            'datos_general/inspeccion_panela':  'inspeccion_panela',
            'datos_general/inspeccion_cacao':   'inspeccion_cacao',
        }
 
        df = df.rename(columns=rename_map)
        print(f"  Renamed {len(rename_map)} columns to standard names")
 
        return df
 
    def _fix_area_units(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert square meters to hectares for values > 100."""
        print("\n  Fixing area units (m² → ha where needed)...")
 
        area_cols = [col for col in df.columns if 'ha_' in col.lower()]
 
        total_fixed = 0
        for col in area_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            mask = df[col] > 100
            if mask.sum() > 0:
                df.loc[mask, col] = df.loc[mask, col] / 10000
                total_fixed += mask.sum()
 
        if total_fixed > 0:
            print(f"    ✅ Fixed {total_fixed} values across {len(area_cols)} area columns")
 
        return df
 
    def _aggregate_plot_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate plot-specific data (p1-p10) into farmer-level totals."""
        print("\n  Aggregating plot data (p1-p10)...")
 
        aggregations = {
            'area_cafe':              [col for col in df.columns if '/ha_cafe_prod_p' in col],
            'area_crecimiento':       [col for col in df.columns if '/ha_cafe_crec_p' in col],
            'area_cacao_produccion':  [col for col in df.columns if '/ha_cacao_prod_p' in col],
            'area_cacao_crecimiento': [col for col in df.columns if '/ha_cacao_crec_p' in col],
            'area_panela_produccion': [col for col in df.columns if '/ha_panela_prod_p' in col],
            'area_panela_crecimiento':[col for col in df.columns if '/ha_panela_crec_p' in col],
            'area_otros_produccion':  [col for col in df.columns if '/ha_otro_p_p' in col],
            'area_otros_crecimiento': [col for col in df.columns if '/ha_otro_c_p' in col],
            'cosecha_estimado_actual_qq': [col for col in df.columns if '/est_prod_cafe_qq_p' in col],
            'cosecha_real_anterior':  [col for col in df.columns if '/cultivo_cafe_cultivo_anterior_p' in col],
        }
 
        for new_col, source_cols in aggregations.items():
            for col in source_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            if source_cols:
                df[new_col] = df[source_cols].sum(axis=1, min_count=1).round(2)
                print(f"    Created {new_col} from {len(source_cols)} plot columns")
 
        df['area_otros_cultivos'] = (
            df.get('area_cacao_produccion', 0) +
            df.get('area_cacao_crecimiento', 0) +
            df.get('area_panela_produccion', 0) +
            df.get('area_panela_crecimiento', 0) +
            df.get('area_otros_produccion', 0) +
            df.get('area_otros_crecimiento', 0)
        ).round(2)
 
        df['area_total_ha'] = (
            df.get('area_cafe', 0) +
            df.get('area_crecimiento', 0) +
            df.get('area_otros_cultivos', 0)
        ).round(2)
 
        plot_name_cols = [col for col in df.columns if 'nom_parcela_p' in col]
        if plot_name_cols:
            df['numero_parcelas_calculado'] = df[plot_name_cols].notna().sum(axis=1)
            print(f"    Calculated actual plot count from {len(plot_name_cols)} name columns")
 
        return df
 
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert columns to appropriate data types."""
        print("\n  Converting data types...")
 
        # DNI
        df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='dni')
 
        # Phone
        if 'telefono' in df.columns:
            df['telefono'] = df['telefono'].astype(str).replace('nan', '')
            df['telefono'] = df['telefono'].str.replace(r'[^0-9+]', '', regex=True)
 
        # Area columns
        area_cols = [col for col in df.columns if 'area_' in col]
        for col in area_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        if area_cols:
            print(f"    Converted {len(area_cols)} area columns")
 
        # Geographic coordinates
        for col in ['longitud', 'latitud']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
 
        # Altitude
        if 'altitud' in df.columns:
            df['altitud'] = pd.to_numeric(df['altitud'], errors='coerce').fillna(0).astype(int)
 
        # Date columns
        for col in ['fecha_nacimiento', 'fecha_ultimo_control_interno']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
 
        # Normalise categoria — fix encoding variants of accented characters
        # The '?' in 'Ecol?gico' is a mojibake replacement for 'ó'.
        # We use regex to replace any non-ASCII character between 'Ecol' and 'gico'.
        if 'categoria' in df.columns:
            import re, unicodedata
            def _fix_cat(v):
                if pd.isna(v):
                    return v
                s = unicodedata.normalize('NFC', str(v).strip())
                # Replace any character that isn't ASCII letter/space between Ecol and gico
                s = re.sub(r'Ecol[^a-zA-Z]gico', 'Ecológico', s)
                s = re.sub(r'R-Ecol[^a-zA-Z]gico', 'R-Ecológico', s)
                return s
            df['categoria'] = df['categoria'].apply(_fix_cat)
 
        # Crop inspection flags as integer 0/1
        for flag_col in ['inspeccion_cafe', 'inspeccion_panela', 'inspeccion_cacao']:
            if flag_col in df.columns:
                df[flag_col] = pd.to_numeric(df[flag_col], errors='coerce').fillna(0).astype(int)
 
        # Yield columns
        yield_cols = [col for col in df.columns if 'cosecha' in col or 'rendimiento' in col]
        for col in yield_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
 
        # Number of plots
        if 'numero_parcelas' in df.columns:
            df['numero_parcelas'] = pd.to_numeric(
                df['numero_parcelas'], errors='coerce'
            ).fillna(0).astype(int)
 
        return df
 
    def _check_data_quality(self, df: pd.DataFrame, year: int) -> None:
        """Check for data quality issues."""
        print(f"\n  Data quality checks ({year})...")
 
        missing_dni = df[(df['dni'] == '') | (df['dni'] == 'nan')]
        if not missing_dni.empty:
            print(f"    ⚠️  {len(missing_dni)} rows with missing DNI")
 
        if 'area_total_ha' in df.columns:
            large_areas = df[df['area_total_ha'] > 50]
            if not large_areas.empty:
                print(f"    ⚠️  {len(large_areas)} rows with area_total_ha > 50 ha")
 
        # Check assumption: each farmer should have at most 1 inspection per year
        # (Norandino confirmed farmers are not inspected for multiple crops same year)
        dups = df.groupby('dni').size()
        multi = dups[dups > 1]
        if len(multi) > 0:
            print(f"    ⚠️  ASSUMPTION BROKEN: {len(multi)} farmers have >1 row in {year}")
            print(f"       This may cause one inspection to be skipped in Stage 3.")
            print(f"       Confirm with Norandino if multi-crop inspections are occurring.")
        else:
            print(f"    ✅ All farmers have exactly 1 inspection row in {year}")
 
    def generate_farmer_ids(self, po_prefix: str = 'NO') -> pd.DataFrame:
        """
        Generate unique farmer IDs with deduplication across all years.
 
        A farmer who appears in both 2024 and 2025 gets the same ID.
 
        Args:
            po_prefix: Prefix for farmer IDs (default: 'NO')
 
        Returns:
            DataFrame with added farmer ID columns
        """
        if self.data_with_plots is None:
            raise ValueError("No data to process! Run clean() first.")
 
        print("\n" + "=" * 60)
        print("GENERATING FARMER IDs")
        print("=" * 60)
 
        df = self.data_with_plots.copy()
        print(f"\nInput: {len(df):,} records across "
              f"{df['inspection_year'].nunique()} year(s): "
              f"{sorted(df['inspection_year'].unique())}")
 
        # Remove invalid rows
        valid_rows = (
            df['nombre_productor'].notna() &
            (df['nombre_productor'] != '') &
            df['dni'].notna() &
            (df['dni'].astype(str) != 'nan')
        )
        if valid_rows.sum() < len(df):
            removed = len(df) - valid_rows.sum()
            print(f"⚠️  Removing {removed} invalid records (empty name or DNI)")
            df = df[valid_rows].copy()
 
        print(f"After cleaning: {len(df):,} valid records")
 
        # Standardise
        df['nombre_estandarizado'] = df['nombre_productor'].apply(self._standardize_name)
        df['dni_estandarizado']    = df['dni'].astype(str).replace('nan', '')
 
        # Generate IDs — same farmer across years gets same ID
        current_id      = 1
        farmer_registry = {}
        id_assignments  = []
 
        for idx, row in df.iterrows():
            current_dni  = row['dni_estandarizado']
            current_name = row['nombre_estandarizado']
 
            if current_dni != '' and current_dni in farmer_registry:
                assigned_id = farmer_registry[current_dni]
            elif current_dni == '' and current_name in farmer_registry:
                assigned_id = farmer_registry[current_name]
            else:
                assigned_id = current_id
                if current_dni != '':
                    farmer_registry[current_dni] = current_id
                if current_name != '':
                    farmer_registry[current_name] = current_id
                current_id += 1
 
            id_assignments.append(assigned_id)
 
        df['id_global'] = id_assignments
        df['producers_direct_id_productor'] = (
            po_prefix + df['id_global'].astype(str).str.zfill(5)
        )
 
        unique_farmers = current_id - 1
        print(f"✅ Assigned {unique_farmers} unique farmer IDs "
              f"(farmers in multiple years share the same ID)")
 
        # Report per year
        for yr in sorted(df['inspection_year'].unique()):
            yr_df = df[df['inspection_year'] == yr]
            print(f"   {yr}: {len(yr_df):,} records, "
                  f"{yr_df['id_global'].nunique()} unique farmers")
 
        self.data_with_plots = df
        return df
 
    def _standardize_name(self, name: str) -> str:
        """Standardize farmer name for matching."""
        if pd.isna(name) or name == '':
            return ''
        return str(name).upper().strip()
 
    def drop_plot_columns(self) -> pd.DataFrame:
        """Drop plot-level columns to create farmer-level DataFrame."""
        if self.data_with_plots is None:
            raise ValueError("No data! Run clean() and generate_farmer_ids() first.")
 
        print("\n  Dropping plot-level columns...")
 
        df = self.data_with_plots.copy()
 
        plot_cols = [col for col in df.columns if
                     '/ha_cafe_prod_p' in col or '/ha_cafe_crec_p' in col or
                     '/ha_cacao_prod_p' in col or '/ha_cacao_crec_p' in col or
                     '/ha_panela_prod_p' in col or '/ha_panela_crec_p' in col or
                     '/ha_otro_p_p' in col or '/ha_otro_c_p' in col or
                     '/est_prod_cafe_qq_p' in col or
                     '/cultivo_cafe_cultivo_anterior_p' in col or
                     'nom_parcela_p' in col]
 
        intermediate_cols = [
            'area_cacao_produccion', 'area_cacao_crecimiento',
            'area_panela_produccion', 'area_panela_crecimiento',
            'area_otros_produccion', 'area_otros_crecimiento',
            'numero_parcelas_calculado'
        ]
 
        df = df.drop(columns=plot_cols + intermediate_cols, errors='ignore')
 
        print(f"    Dropped {len(plot_cols) + len(intermediate_cols)} plot/intermediate columns")
        print(f"    Farmer-level DataFrame: {len(df):,} rows, {len(df.columns)} columns")
 
        self.data = df
        return df
 
    def get_summary(self) -> dict:
        """Get summary statistics."""
        if self.data is None:
            return {"error": "No farmer-level data. Run drop_plot_columns() first."}
 
        df = self.data
 
        summary = {
            "total_inspections": len(df),
            "columns":           len(df.columns),
            "column_names":      df.columns.tolist(),
        }
 
        if 'inspection_year' in df.columns:
            summary["by_year"] = df['inspection_year'].value_counts().sort_index().to_dict()
 
        if 'producers_direct_id_productor' in df.columns:
            summary["unique_farmers"] = df['producers_direct_id_productor'].nunique()
 
        if 'categoria' in df.columns:
            summary["by_category"] = df['categoria'].value_counts().to_dict()
 
        if 'area_total_ha' in df.columns:
            summary["total_area_ha"] = round(df['area_total_ha'].sum(), 2)
 
        return summary
 
    def save(self,
             with_plots_filename:   str = 'norandino_with_all_plots_data.pkl',
             farmer_level_filename: str = 'norandino_inspections_clean.pkl') -> tuple:
        """Save both versions: with plots and farmer-level."""
        if self.data_with_plots is None or self.data is None:
            raise ValueError("No data to save. Run full cleaning process first.")
 
        with_plots_path = self.output_dir / with_plots_filename
        self.data_with_plots.to_pickle(with_plots_path)
        print(f"✅ Saved with plots: {with_plots_path.name} ({len(self.data_with_plots):,} rows)")
 
        farmer_level_path = self.output_dir / farmer_level_filename
        self.data.to_pickle(farmer_level_path)
        print(f"✅ Saved farmer-level: {farmer_level_path.name} ({len(self.data):,} rows)")
 
        return (with_plots_path, farmer_level_path)
 
 
def clean_norandino_inspections() -> pd.DataFrame:
    """
    Convenience function to clean Norandino inspections data (all years).
 
    Returns:
        Cleaned farmer-level DataFrame with inspection_year column
    """
    cleaner = NorandinoInspectionsCleaner()
 
    cleaner.clean()
    cleaner.generate_farmer_ids()
    df = cleaner.drop_plot_columns()
    cleaner.save()
 
    return df
 
 
if __name__ == "__main__":
    df = clean_norandino_inspections()
 
    cleaner = NorandinoInspectionsCleaner()
    cleaner.data = df
    summary = cleaner.get_summary()
 
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total inspections: {summary['total_inspections']:,}")
 
    if 'by_year' in summary:
        print(f"\nBy year:")
        for yr, count in summary['by_year'].items():
            print(f"  {yr}: {count:,} records")
 
    if 'unique_farmers' in summary:
        print(f"\nUnique farmers: {summary['unique_farmers']}")
 
    if 'by_category' in summary:
        print(f"\nBy category:")
        for cat, count in summary['by_category'].items():
            print(f"  {cat}: {count}")
 
    if 'total_area_ha' in summary:
        print(f"\nTotal area: {summary['total_area_ha']:,.2f} hectares")
 
    display_cols = [c for c in [
                        'producers_direct_id_productor', 'nombre_productor', 'dni',
                        'inspection_year', 'categoria', 'area_cafe', 'area_total_ha',
                        'numero_parcelas'
                    ] if c in df.columns]
    if display_cols:
        print(f"\nFirst farmer across all years (same DNI should share same ID):")
        first_farmer_dni = df['dni'].iloc[0]
        farmer_rows = df[df['dni'] == first_farmer_dni][display_cols]
        print(farmer_rows.to_string(index=False))
        print(f"\n→ {len(farmer_rows)} inspection records for DNI {first_farmer_dni} "
              f"across {farmer_rows['inspection_year'].nunique()} year(s): "
              f"{sorted(farmer_rows['inspection_year'].unique().tolist())}")
 
    print(f"\nColumn names ({len(df.columns)} total):")
    print(df.columns.tolist())
    print("\n" + "=" * 60)