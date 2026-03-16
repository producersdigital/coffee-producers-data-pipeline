"""
Norandino Inspections Data Cleaner
 
Cleans and standardizes inspection data from Norandino Producer Organization.
Handles massive Excel file (2400+ columns) with plot-level data that needs aggregation.
 
Key features:
- Filters by inspection acceptance, coffee inspection, and 2024 cycle
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
 
 
class NorandinoInspectionsCleaner:
    """
    Clean and standardize Norandino inspection data.
    
    This is the most complex cleaner due to:
    - Massive source file with 2400+ columns
    - Plot-level data (up to 10 plots per farmer)
    - Need to aggregate plot data to farmer level
    - Area unit conversion
    
    Attributes:
        file_path: Path to the inspections Excel file
        data: Cleaned DataFrame (farmer-level)
        data_with_plots: DataFrame with all plot details
        dni_cleaner: DNI cleaning utility
    """
    
    def __init__(self):
        """Initialize the cleaner with file path and utilities."""
        self.dni_cleaner = DNICleaner()
        
        # Define file path
        raw_dir = DATA_DIR / 'raw' / 'inspections' / 'norandino'
        self.file_path = raw_dir / 'Inspecciones_internas_24.xlsx'
        
        # Output directory
        self.output_dir = DATA_DIR / 'processed' / 'inspections' / 'norandino'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data = None
        self.data_with_plots = None
    
    def clean(self) -> pd.DataFrame:
        """
        Clean the Norandino inspections data.
        
        Returns:
            Cleaned DataFrame with farmer-level inspection data
        """
        print("\n" + "="*60)
        print("CLEANING NORANDINO INSPECTIONS")
        print("="*60)
        
        # 1. Read the massive file
        print(f"\nReading from {self.file_path.name}")
        print("  ⚠️  This file has 2400+ columns, may take a moment...")
        df = pd.read_excel(self.file_path, sheet_name='Inspeccion Interna Norandino...')
        print(f"  Loaded {len(df):,} rows, {len(df.columns):,} columns")
        
        # 2. Filter rows
        df = self._filter_rows(df)
        
        # 3. Select relevant columns
        df = self._select_columns(df)
        
        # 4. Rename columns to standard names
        df = self._rename_to_standard(df)
        
        # 5. Fix area units (m² → ha if > 100)
        df = self._fix_area_units(df)
        
        # 6. Aggregate plot data
        df = self._aggregate_plot_data(df)
        
        # 7. Convert data types
        df = self._convert_data_types(df)
        
        # 8. Add metadata
        df['org_code'] = 'NO'
        df['country_code'] = 'PER'
        df['data_source'] = 'NORANDINO/raw_data/Inspecciones_internas_24.xlsx'
        print(f"  Added metadata columns")
        
        # 9. Check data quality
        self._check_data_quality(df)
        
        # Store data with plots before dropping them
        self.data_with_plots = df.copy()
        
        print(f"\n✅ Norandino inspections cleaning complete!")
        print(f"   Total inspections: {len(df):,}")
        
        return df
    
    def _filter_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter rows by acceptance, coffee inspection, and 2024 cycle.
        
        Args:
            df: DataFrame with all rows
            
        Returns:
            Filtered DataFrame
        """
        print("\n  Filtering rows...")
        initial_count = len(df)
        
        # Filter 1: Inspection accepted
        df = df[df['acepta_inspeccion'] == 1]
        print(f"    After acepta_inspeccion==1: {len(df):,} rows")
        
        # Filter 2: Coffee inspection
        df = df[df['datos_general/inspeccion_cafe'] == 1]
        print(f"    After coffee inspection==1: {len(df):,} rows")
        
        # Filter 3: 2024 cycle
        df = df[df['info_general/ciclo'] == 2024]
        print(f"    After 2024 cycle: {len(df):,} rows")
        
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
            'manejo_agro/area_rehab'
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
        """
        Rename columns to standard names.
        
        Args:
            df: DataFrame with original column names
            
        Returns:
            DataFrame with standardized names
        """
        rename_map = {
            'info_general/fecha_inspeccion': 'fecha_ultimo_control_interno',
            'info_general/_gps_latitude': 'latitud',
            'info_general/_gps_longitude': 'longitud',
            'info_general/_gps_altitude': 'altitud',
            'info_general/dni': 'dni',
            'datos_general/nombre_completo': 'nombre_productor',
            'datos_general/caserio': 'caserio',
            'datos_general/distrito': 'distrito',
            'datos_general/provincia': 'provincia',
            'datos_general/departamento': 'departamento',
            'datos_general/estatus_socio': 'estado_socio',
            'datos_general/estatus_cert_actual': 'categoria',
            'datos_general/genero': 'genero',
            'num_parcelas/n_parcelas': 'numero_parcelas',
            'datos_general/telefono_productor': 'telefono',
            'datos_general/fecha_nacimiento': 'fecha_nacimiento',
            'manejo_agro/area_rehab': 'area_rehabilitacion'
        }
        
        df = df.rename(columns=rename_map)
        print(f"  Renamed {len(rename_map)} columns to standard names")
        
        return df
    
    def _fix_area_units(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert square meters to hectares for values > 100.
        
        Some area values are mistakenly in m² instead of ha.
        
        Args:
            df: DataFrame with area columns
            
        Returns:
            DataFrame with corrected area units
        """
        print("\n  Fixing area units (m² → ha where needed)...")
        
        # Find all area columns (ha_ prefix)
        area_cols = [col for col in df.columns if 'ha_' in col.lower()]
        
        total_fixed = 0
        for col in area_cols:
            # Convert to numeric
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Find values > 100 (likely in m²)
            mask = df[col] > 100
            if mask.sum() > 0:
                df.loc[mask, col] = df.loc[mask, col] / 10000
                total_fixed += mask.sum()
        
        if total_fixed > 0:
            print(f"    ✅ Fixed {total_fixed} values across {len(area_cols)} area columns")
        
        return df
    
    def _aggregate_plot_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate plot-specific data into farmer-level totals.
        
        Sums data from up to 10 plots (p1-p10) into single farmer-level columns.
        
        Args:
            df: DataFrame with plot-level data
            
        Returns:
            DataFrame with aggregated columns added
        """
        print("\n  Aggregating plot data (p1-p10)...")
        
        # Define aggregation groups
        aggregations = {
            'area_cafe': [col for col in df.columns if '/ha_cafe_prod_p' in col],
            'area_crecimiento': [col for col in df.columns if '/ha_cafe_crec_p' in col],
            'area_cacao_produccion': [col for col in df.columns if '/ha_cacao_prod_p' in col],
            'area_cacao_crecimiento': [col for col in df.columns if '/ha_cacao_crec_p' in col],
            'area_panela_produccion': [col for col in df.columns if '/ha_panela_prod_p' in col],
            'area_panela_crecimiento': [col for col in df.columns if '/ha_panela_crec_p' in col],
            'area_otros_produccion': [col for col in df.columns if '/ha_otro_p_p' in col],
            'area_otros_crecimiento': [col for col in df.columns if '/ha_otro_c_p' in col],
            'cosecha_estimado_actual_qq': [col for col in df.columns if '/est_prod_cafe_qq_p' in col],
            'cosecha_real_anterior': [col for col in df.columns if '/cultivo_cafe_cultivo_anterior_p' in col]
        }
        
        # Aggregate each group
        for new_col, source_cols in aggregations.items():
            # Convert source columns to numeric and fill NaN with 0
            for col in source_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Sum across plots
            if source_cols:
                df[new_col] = df[source_cols].sum(axis=1, min_count=1).round(2)
                print(f"    Created {new_col} from {len(source_cols)} plot columns")
        
        # Calculate total areas
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
        
        # Count non-empty plots
        plot_name_cols = [col for col in df.columns if 'nom_parcela_p' in col]
        if plot_name_cols:
            df['numero_parcelas_calculado'] = df[plot_name_cols].notna().sum(axis=1)
            print(f"    Calculated actual plot count from {len(plot_name_cols)} name columns")
        
        return df
    
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert columns to appropriate data types."""
        print("\n  Converting data types...")
        
        # 1. Clean DNI
        df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='dni')
        
        # 2. Phone numbers as strings
        if 'telefono' in df.columns:
            df['telefono'] = df['telefono'].astype(str).replace('nan', '')
            df['telefono'] = df['telefono'].str.replace(r'[^0-9+]', '', regex=True)
        
        # 3. Area columns (already handled in aggregation, just ensure 2 decimals)
        area_cols = [col for col in df.columns if 'area_' in col]
        for col in area_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        
        if area_cols:
            print(f"    Converted {len(area_cols)} area columns")
        
        # 4. Geographic coordinates
        geo_cols = ['longitud', 'latitud']
        for col in geo_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 5. Altitude
        if 'altitud' in df.columns:
            df['altitud'] = pd.to_numeric(df['altitud'], errors='coerce').fillna(0).astype(int)
        
        # 6. Date columns
        date_cols = ['fecha_nacimiento', 'fecha_ultimo_control_interno']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # 7. Yield columns
        yield_cols = [col for col in df.columns if 'cosecha' in col or 'rendimiento' in col]
        for col in yield_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        
        # 8. Number of plots as integer
        if 'numero_parcelas' in df.columns:
            df['numero_parcelas'] = pd.to_numeric(df['numero_parcelas'], errors='coerce').fillna(0).astype(int)
        
        return df
    
    def _check_data_quality(self, df: pd.DataFrame) -> None:
        """Check for data quality issues."""
        print("\n  Data quality checks...")
        
        # Missing DNIs
        missing_dni = df[(df['dni'] == '') | (df['dni'] == 'nan')]
        if not missing_dni.empty:
            print(f"    ⚠️  {len(missing_dni)} rows with missing DNI")
        
        # Large areas (> 50 ha)
        if 'area_total_ha' in df.columns:
            large_areas = df[df['area_total_ha'] > 50]
            if not large_areas.empty:
                print(f"    ⚠️  {len(large_areas)} rows with area_total_ha > 50 hectares")
    
    def generate_farmer_ids(self, po_prefix: str = 'NO') -> pd.DataFrame:
        """
        Generate unique farmer IDs with deduplication.
        Uses improved version from Chirinos/Huadquiña/Aprocassi.
        
        Args:
            po_prefix: Prefix for farmer IDs (default: 'NO' for Norandino)
            
        Returns:
            DataFrame with added farmer ID columns
        """
        if self.data_with_plots is None:
            raise ValueError("No data to process! Run clean() first.")
        
        print("\n" + "="*60)
        print("GENERATING FARMER IDs")
        print("="*60)
        
        df = self.data_with_plots.copy()
        
        print(f"\nInput: {len(df):,} records")
        
        # Remove invalid rows (empty name AND DNI)
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
        
        # Add standardized columns
        df['nombre_estandarizado'] = df['nombre_productor'].apply(self._standardize_name)
        df['dni_estandarizado'] = df['dni'].astype(str).replace('nan', '')
        
        # Generate unique IDs
        current_id = 1
        farmer_registry = {}
        id_assignments = []
        
        for idx, row in df.iterrows():
            current_dni = row['dni_estandarizado']
            current_name = row['nombre_estandarizado']
            
            # Match by DNI first
            if current_dni != '' and current_dni in farmer_registry:
                assigned_id = farmer_registry[current_dni]
            # Match by name if DNI missing
            elif current_dni == '' and current_name in farmer_registry:
                assigned_id = farmer_registry[current_name]
            # New farmer
            else:
                assigned_id = current_id
                if current_dni != '':
                    farmer_registry[current_dni] = current_id
                if current_name != '':
                    farmer_registry[current_name] = current_id
                current_id += 1
            
            id_assignments.append(assigned_id)
        
        df['id_global'] = id_assignments
        df['producers_direct_id_productor'] = po_prefix + df['id_global'].astype(str).str.zfill(5)
        
        print(f"✅ Assigned {current_id-1} unique farmer IDs")
        
        # Update stored data
        self.data_with_plots = df
        
        return df
    
    def _standardize_name(self, name: str) -> str:
        """Standardize farmer name for matching."""
        if pd.isna(name) or name == '':
            return ''
        return str(name).upper().strip()
    
    def drop_plot_columns(self) -> pd.DataFrame:
        """
        Drop plot-level columns to create farmer-level DataFrame.
        
        Returns:
            Farmer-level DataFrame without plot details
        """
        if self.data_with_plots is None:
            raise ValueError("No data! Run clean() and generate_farmer_ids() first.")
        
        print("\n  Dropping plot-level columns...")
        
        df = self.data_with_plots.copy()
        
        # Find plot columns
        plot_cols = [col for col in df.columns if
                    '/ha_cafe_prod_p' in col or '/ha_cafe_crec_p' in col or
                    '/ha_cacao_prod_p' in col or '/ha_cacao_crec_p' in col or
                    '/ha_panela_prod_p' in col or '/ha_panela_crec_p' in col or
                    '/ha_otro_p_p' in col or '/ha_otro_c_p' in col or
                    '/est_prod_cafe_qq_p' in col or
                    '/cultivo_cafe_cultivo_anterior_p' in col or
                    'nom_parcela_p' in col]
        
        # Add intermediate columns
        intermediate_cols = [
            'area_cacao_produccion', 'area_cacao_crecimiento',
            'area_panela_produccion', 'area_panela_crecimiento',
            'area_otros_produccion', 'area_otros_crecimiento',
            'numero_parcelas_calculado'
        ]
        
        cols_to_drop = plot_cols + intermediate_cols
        
        # Drop columns
        df = df.drop(columns=cols_to_drop, errors='ignore')
        
        print(f"    Dropped {len(cols_to_drop)} plot/intermediate columns")
        print(f"    Farmer-level DataFrame: {len(df):,} rows, {len(df.columns)} columns")
        
        # Store farmer-level data
        self.data = df
        
        return df
    
    def get_summary(self) -> dict:
        """Get summary statistics."""
        if self.data is None:
            return {"error": "No farmer-level data. Run drop_plot_columns() first."}
        
        df = self.data
        
        summary = {
            "total_inspections": len(df),
            "columns": len(df.columns),
            "column_names": df.columns.tolist()
        }
        
        if 'producers_direct_id_productor' in df.columns:
            summary["unique_farmers"] = df['producers_direct_id_productor'].nunique()
        
        if 'categoria' in df.columns:
            summary["by_category"] = df['categoria'].value_counts().to_dict()
        
        if 'area_total_ha' in df.columns:
            summary["total_area_ha"] = round(df['area_total_ha'].sum(), 2)
        
        return summary
    
    def save(self, 
             with_plots_filename: str = 'norandino_with_all_plots_data.pkl',
             farmer_level_filename: str = 'norandino_inspections_clean.pkl') -> tuple:
        """
        Save both versions: with plots and farmer-level.
        
        Args:
            with_plots_filename: Filename for data with all plot details
            farmer_level_filename: Filename for farmer-level data
            
        Returns:
            Tuple of (with_plots_path, farmer_level_path)
        """
        if self.data_with_plots is None or self.data is None:
            raise ValueError("No data to save. Run full cleaning process first.")
        
        # Save with plots
        with_plots_path = self.output_dir / with_plots_filename
        self.data_with_plots.to_pickle(with_plots_path)
        print(f"✅ Saved with plots: {with_plots_path.name} ({len(self.data_with_plots):,} rows)")
        
        # Save farmer-level
        farmer_level_path = self.output_dir / farmer_level_filename
        self.data.to_pickle(farmer_level_path)
        print(f"✅ Saved farmer-level: {farmer_level_path.name} ({len(self.data):,} rows)")
        
        return (with_plots_path, farmer_level_path)
 
 
def clean_norandino_inspections() -> pd.DataFrame:
    """
    Convenience function to clean Norandino inspections data.
    
    Returns:
        Cleaned farmer-level DataFrame
    """
    cleaner = NorandinoInspectionsCleaner()
    
    # Clean data
    cleaner.clean()
    
    # Generate farmer IDs
    cleaner.generate_farmer_ids()
    
    # Create farmer-level data
    df = cleaner.drop_plot_columns()
    
    # Save both versions
    cleaner.save()
    
    return df
 
 
if __name__ == "__main__":
    # Run the cleaner
    df = clean_norandino_inspections()
    
    # Print summary
    cleaner = NorandinoInspectionsCleaner()
    cleaner.data = df
    summary = cleaner.get_summary()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total inspections: {summary['total_inspections']:,}")
    
    if 'unique_farmers' in summary:
        print(f"Unique farmers: {summary['unique_farmers']}")
    
    if 'by_category' in summary:
        print(f"\nBy category:")
        for cat, count in summary['by_category'].items():
            print(f"  {cat}: {count}")
    
    if 'total_area_ha' in summary:
        print(f"\nTotal area: {summary['total_area_ha']:,.2f} hectares")
    
    print("\nFirst 3 inspections preview:")
    display_cols = [c for c in ['producers_direct_id_productor', 'nombre_productor', 
                                 'dni', 'area_cafe', 'area_total_ha'] 
                    if c in df.columns]
    if display_cols:
        print(df[display_cols].head(3).to_string(index=False))
    
    print(f"\nColumn names ({len(df.columns)} total):")
    print(df.columns.tolist())
    
    print("\n" + "="*60)