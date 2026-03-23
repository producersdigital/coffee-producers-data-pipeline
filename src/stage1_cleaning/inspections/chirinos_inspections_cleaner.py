"""
Chirinos Inspections Data Cleaner
 
Cleans and standardizes inspection data from Chirinos Producer Organization.
Handles multi-year files (2020-2024) with different column structures.
 
Key features:
- Column harmonization across years (aggregation + renaming)
- Forest area aggregation (primary + secondary)
- Crop area aggregation (sum of individual crops)
- Farmer ID generation (CH##### format)
 
Usage:
    from src.stage1_cleaning.inspections.chirinos_inspections_cleaner import clean_chirinos_inspections
    
    df = clean_chirinos_inspections()
"""
 
import pandas as pd
import numpy as np
from pathlib import Path
import sys
 
# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
 
from src.utils.dni_cleaner import DNICleaner
 
# Define DATA_DIR here (no dependency on config.paths)
DATA_DIR = project_root / 'data'
 
 
class ChirinosInspectionsCleaner:
    """
    Clean and standardize Chirinos inspection data from multiple years.
    
    Attributes:
        file_paths: List of file paths to process
        data: Cleaned DataFrame
        dni_cleaner: DNI cleaning utility
    """
    
    def __init__(self):
        """Initialize the cleaner with file paths and utilities."""
        self.dni_cleaner = DNICleaner()
        
        # Define file paths for all years
        raw_dir = DATA_DIR / 'raw' / 'inspections' / 'chirinos'
        self.file_paths = {
            2020: raw_dir / 'Data General 2020.xlsx',
            2021: raw_dir / 'Data general 2021.xlsx',
            2022: raw_dir / 'Data General 2022.xlsx',
            2023: raw_dir / 'Data General 2023.xlsx',
            2024: raw_dir / 'Data General 2024.xlsx'
        }
        
        # Sheet names per year (exact names from Excel files)
        self.sheet_names = {
            2020: 'Data 2020',
            2021: 'LISTA DE SOCIOS',
            2022: 'LPA-General',
            2023: 'General-2023',
            2024: 'LPA-General 2024'
        }
        
        # Output directory
        self.output_dir = DATA_DIR / 'processed' / 'inspections' / 'chirinos'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data = None
    
    def clean_all_years(self) -> pd.DataFrame:
        """
        Clean all inspection years and combine them.
        
        Returns:
            Combined and cleaned DataFrame
        """
        print("\n" + "="*60)
        print("CLEANING CHIRINOS INSPECTIONS")
        print("="*60)
        
        all_years = []
        
        for year, file_path in sorted(self.file_paths.items()):
            if not file_path.exists():
                print(f"\n⚠️  Skipping {year}: File not found")
                continue
            
            print(f"\nCleaning {year} inspections...")
            df = self._clean_single_year(file_path, year)
            all_years.append(df)
            print(f"  ✅ {year}: {len(df)} inspections")
        
        # Combine all years
        print("\nCombining all years...")
        combined = pd.concat(all_years, ignore_index=True)
        print(f"  Total inspections: {len(combined)}")
        
        # Apply final cleaning
        combined = self._final_cleaning(combined)
        
        # Store result
        self.data = combined
        
        print(f"\n✅ Chirinos inspections cleaning complete!")
        print(f"   Total inspections: {len(combined)}")
        print(f"   Years: {sorted(combined['año_inspeccion'].unique())}")
        
        return combined
    
    def _clean_single_year(self, file_path: Path, year: int) -> pd.DataFrame:
        """
        Clean a single year's inspection file.
        
        Args:
            file_path: Path to the Excel file
            year: Year being processed
            
        Returns:
            Cleaned DataFrame for this year
        """
        # Get the correct sheet name for this year
        sheet_name = self.sheet_names.get(year, 0)  # Fallback to first sheet if not mapped
        
        # Read the file with the correct sheet name
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns from sheet '{sheet_name}'")
        
        # Lowercase all columns first (for consistent matching)
        # Also normalize whitespace (remove leading/trailing, collapse multiple spaces)
        df.columns = df.columns.str.lower().str.strip().str.replace(r'\s+', ' ', regex=True)
        
        # Apply year-specific harmonization
        df = self._harmonize_columns(df, year)
        
        # Add year identifier
        df['año_inspeccion'] = year
        
        return df
    
    def _harmonize_columns(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Harmonize columns from different years to match 2024 structure.
        
        Different years have different column structures:
        - 2024: Already in target format
        - 2020-2023: Need aggregation and renaming
        
        Args:
            df: DataFrame with year-specific columns
            year: Year being processed
            
        Returns:
            DataFrame with harmonized columns
        """
        print(f"  Harmonizing columns for {year}...")
        
        if year == 2024:
            # 2024 already has most columns correct
            print(f"    2024 structure - minimal harmonization needed")
        else:
            # Create new columns through aggregation
            df = self._aggregate_forest_columns(df)
            df = self._aggregate_crop_columns(df)
        
        # Rename columns to match 2024 (all years)
        df = self._rename_year_columns(df, year)
        
        # Drop columns that don't exist in 2024
        df = self._drop_old_year_columns(df)
        
        # CRITICAL: Handle duplicate columns intelligently
        df = self._coalesce_duplicate_columns(df, year)
        
        return df
    
    def _coalesce_duplicate_columns(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Intelligently merge duplicate columns instead of just dropping them.
        
        When we have two columns with the same name, combine them:
        - Prefer non-NaN values
        - If both have values, prefer the first (usually from aggregation)
        - Log what's happening for transparency
        
        Args:
            df: DataFrame potentially with duplicate column names
            year: Year being processed (for logging)
            
        Returns:
            DataFrame with duplicates resolved
        """
        if not df.columns.duplicated().any():
            return df
        
        # Find which columns are duplicated
        duplicate_names = df.columns[df.columns.duplicated()].unique().tolist()
        
        print(f"      ⚠️  Found duplicates for {len(duplicate_names)} column(s): {duplicate_names}")
        print(f"      → This suggests multiple source columns renamed to same target")
        
        # Process each duplicate
        for col_name in duplicate_names:
            # Get all columns with this name
            duplicate_cols = df.loc[:, df.columns == col_name]
            
            if len(duplicate_cols.columns) == 2:
                # Most common case: exactly 2 duplicates
                col1 = duplicate_cols.iloc[:, 0]
                col2 = duplicate_cols.iloc[:, 1]
                
                # Count non-null values in each
                count1 = col1.notna().sum()
                count2 = col2.notna().sum()
                
                print(f"        '{col_name}':")
                print(f"          - First occurrence:  {count1:4d} non-null values")
                print(f"          - Second occurrence: {count2:4d} non-null values")
                
                # Check if values are identical where both exist
                both_exist = col1.notna() & col2.notna()
                if both_exist.any():
                    num_both = both_exist.sum()
                    same_values = (col1[both_exist] == col2[both_exist]).sum()
                    diff_values = num_both - same_values
                    
                    print(f"          - Both have values: {num_both} rows")
                    print(f"            → Same values: {same_values}, Different: {diff_values}")
                    
                    if diff_values > 0:
                        print(f"          ⚠️  WARNING: {diff_values} rows differ! Keeping first column.")
                        # Show a sample of differences
                        diff_mask = both_exist & (col1 != col2)
                        if diff_mask.sum() > 0:
                            print(f"          Sample difference (first 3):")
                            for idx in df[diff_mask].head(3).index:
                                print(f"            Row {idx}: col1={col1[idx]}, col2={col2[idx]}")
                
                # Coalesce: prefer col1, but fill with col2 where col1 is NaN
                merged = col1.combine_first(col2)
                
                # Remove both duplicates and add merged version
                df = df.loc[:, df.columns != col_name]
                df[col_name] = merged
                
            else:
                # More than 2 duplicates (rare but handle it)
                print(f"        '{col_name}': {len(duplicate_cols.columns)} duplicates - keeping first")
                df = df.loc[:, ~df.columns.duplicated(keep='first')]
        
        print(f"      ✅ Resolved all duplicate columns")
        return df
    

    def _standardize_name(self, name: str) -> str:
        """
        Standardize farmer name for matching.
        
        Args:
            name: Raw name string
            
        Returns:
            Standardized name (uppercase, stripped)
        """
        if pd.isna(name) or name == '':
            return ''
        return str(name).upper().strip()
    
    def _aggregate_forest_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate forest-related columns.
        
        area_bosque_secundario = RESERVA/REFORESTACION (if exists)
                               OR RESERVA + REFORESTACION
        
        Important: Watch for duplicate summation if all three columns exist!
        """
        # Check if already has the combined column
        if 'reserva/reforestacion' in df.columns:
            # Use the pre-summed column
            df['area_bosque_secundario'] = df['reserva/reforestacion']
            print(f"      Used reserva/reforestacion for area_bosque_secundario")
        else:
            # Sum individual columns (filling missing with 0)
            reserva = df.get('reserva', pd.Series(0, index=df.index)).fillna(0)
            reforestacion = df.get('reforestacion', pd.Series(0, index=df.index)).fillna(0)
            df['area_bosque_secundario'] = reserva + reforestacion
            print(f"      Created area_bosque_secundario from reserva + reforestacion")
        
        return df
    
    def _aggregate_crop_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate crop columns.
        
        area_otros_cultivos = OTROS CULTIVOS + MAIZ + CACAO + CAÑA + 
                             PAN LLEVAR + PIÑA + PLATANO
        
        Note: 2020 has 'OTROS CULTIVOS 1' which is already the total - we'll drop it
        """
        # Get individual crop columns (handle missing gracefully)
        otros = df.get('otros cultivos', pd.Series(0, index=df.index)).fillna(0)
        ortos = df.get('ortos cultuvos', pd.Series(0, index=df.index)).fillna(0)  # Typo in 2021
        maiz = df.get('maiz', pd.Series(0, index=df.index)).fillna(0)
        cacao = df.get('cacao', pd.Series(0, index=df.index)).fillna(0)
        cana = df.get('caña', pd.Series(0, index=df.index)).fillna(0)
        pan_llevar = df.get('pan llevar', pd.Series(0, index=df.index)).fillna(0)
        pina = df.get('piña', pd.Series(0, index=df.index)).fillna(0)
        platano = df.get('platano', pd.Series(0, index=df.index)).fillna(0)
        
        # Sum all crops (use max of otros/ortos to handle the typo)
        otros_base = np.maximum(otros, ortos)
        df['area_otros_cultivos'] = (otros_base + maiz + cacao + cana + 
                                      pan_llevar + pina + platano)
        
        print(f"      Created area_otros_cultivos from sum of crop columns")
        
        return df
    
    def _rename_year_columns(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Rename columns to match 2024 standard names.
        
        Args:
            df: DataFrame with original column names (already lowercased)
            year: Year being processed
            
        Returns:
            DataFrame with standardized column names
        """
        # Comprehensive rename map (columns are already lowercase)
        rename_map = {
            # Basic info - NOTE: nº and id are dropped, not renamed
            'nombre del productor': 'nombre_productor',
            'nombre productor': 'nombre_productor',
            'nombre productor.1': 'nombre_productor_dup',  # Will drop later
            'socio dni': 'dni',
            'dni.1': 'dni_dup',  # Will drop later
            
            # Location
            'base': 'base',
            'caserio': 'caserio',
            'distrito': 'distrito',
            'provincia': 'provincia',
            
            # Areas
            'ha total': 'area_total_ha',
            'area total': 'area_total_ha',
            'total finca': 'area_total_ha',
            'suma de total hectareas': 'area_total_ha',
            
            'café produccion': 'area_cafe',
            'cultivo producción': 'area_cafe',
            'cultivo produccion': 'area_cafe',
            'suma de total h cafe produccion': 'area_cafe',
            
            'café crecimiento': 'area_crecimiento',
            'cafe crecimiento': 'area_crecimiento',
            'cultivo crecimiento': 'area_crecimiento',
            'suma de total h cafe crecimiento': 'area_crecimiento',
            
            'inverna/pasto': 'area_invernadero_pasto',
            'inverna pasto': 'area_invernadero_pasto',
            'inverna': 'area_invernadero_pasto',
            'suma de total h inverna pasto': 'area_invernadero_pasto',
            
            'rastrojo/purma': 'area_purma',
            'rastrojo purma': 'area_purma',
            'rastrojo, purma': 'area_purma',
            'suma de total h rastrojo purma': 'area_purma',
            
            'bosque': 'area_bosque',
            'bosque primario': 'area_bosque',
            'suma de total h bosque primario': 'area_bosque',
            
            # area_bosque_secundario already created in aggregation
            'suma de total h bosque secundario': 'area_bosque_secundario',
            
            # area_otros_cultivos already created in aggregation
            'suma de total h otros cultivos': 'area_otros_cultivos',
            
            # Personal info
            'genero': 'genero',
            'socio genero': 'genero',
            
            'fecha de nacimiento': 'fecha_nacimiento',
            'fecha nacimiento': 'fecha_nacimiento',
            'ds.fecha nacim texto': 'fecha_nacimiento',
            'fecha nc': 'fecha_nacimiento',
            
            'fecha ingreso': 'fecha_ingreso',
            'fecha ingreso texto': 'fecha_ingreso',
            
            # Inspector info
            'nombre inspector': 'nombre_inspector_interno',
            'inspector': 'nombre_inspector_interno',
            'inspector interno': 'nombre_inspector_interno',
            
            'dni inspector': 'dni_inspector_interno',
            'inspector dni': 'dni_inspector_interno',
            
            # Dates
            'fecha de inspeccion interna': 'fecha_ultimo_control_interno',
            'fecha inspeccion interna': 'fecha_ultimo_control_interno',
            'fecha inspeccion': 'fecha_ultimo_control_interno',
            'fecha ultimo control interno': 'fecha_ultimo_control_interno',
            
            'inicio de conversión': 'fecha_inicio_conversion',
            'inicio conversión': 'fecha_inicio_conversion',
            'fecha conversion texto': 'fecha_inicio_conversion',
            
            # Harvest estimates
            'estimado 2023': 'cosecha_estimado_anterior_kg',
            'estimado qq 2023': 'cosecha_estimado_anterior_qq',
            'acopio 2023': 'cosecha_acopio_anterior_kg',
            'estimado de cosecha 2024': 'cosecha_estimado_actual_qq',
            'estimado kg 2024': 'cosecha_estimado_actual_kg',
            'estimado promedio /ha': 'rendimiento_estimado_qqha',
            'compromiso acopio 2024': 'compromiso_acopio_actual_qq',
            
            # Coordinates
            'latitud': 'latitud',
            'latutud': 'latitud',  # Typo in 2021
            'suma de coordenadas gps latitud': 'latitud',
            
            'longitud': 'longitud',
            'suma de coordenadas gps longitud': 'longitud',
            
            'altitud': 'altitud',
            'suma de altitud': 'altitud',
            
            # Other
            'nº parcelas': 'numero_parcelas',
            'n° parcelas': 'numero_parcelas',
            'suma de numero parcelas': 'numero_parcelas',
            
            'nº celular': 'telefono',
            'celular': 'telefono',
            'suma de ds.celular socio 1': 'telefono',
            
            'sellos': 'sellos',
            
            'estado': 'estado_socio',
            'estado del socio': 'estado_socio',
            
            'estatus org': 'categoria',
            'estatus propuesto': 'categoria_propuesta',
            
            'certificacion': 'certificacion',
            'entidad de certificacion': 'certificacion',
            
            'numero de trabajadodes temporales': 'numero_trabajadores_temporales',
            'n° trabajadoras mujeres': 'numero_trabajadores_mujeres',
            'n° trabajadioras mujeres': 'numero_trabajadores_mujeres',  # Typo variant
            
            'ue-2023': 'certificacion_ue_rtpo_anterior',
        }
        
        # Apply renames (only for columns that exist)
        existing_renames = {k: v for k, v in rename_map.items() if k in df.columns}
        
        if existing_renames:
            df = df.rename(columns=existing_renames)
            print(f"      Renamed {len(existing_renames)} columns to standard names")
        
        return df
    
    def _drop_old_year_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Drop columns that exist in old years but not in 2024 final structure.
        """
        # Columns to drop (already lowercase)
        drop_cols = [
            # Duplicates from renaming
            'nombre_productor_dup', 'dni_dup',
            
            # Farmer/member numbers (inconsistent across years - we use pd_farmer_id instead)
            'nº', 'n°', 'id',
            
            # Old status columns
            'estatus 2019', 'estatus 2020', 'estatus 2021', 'estatus 2022', 'estatus 2023',
            
            # Old certification columns (covered in SELLOS)
            'utz', 'ra', 'bf', 'rainforest alliance', 'bird friendly',
            
            # Control externo
            'control externo', 'control externo (años)',
            
            # Risk
            'riesgo',
            
            # Individual crop columns (already aggregated)
            'maiz', 'cacao', 'caña', 'pan llevar', 'piña', 'platano',
            'otros cultivos', 'ortos cultuvos',  # Typo in 2021
            'otros cultivos 1',  # 2020 total (redundant)
            
            # Forest columns (already aggregated)
            'reserva', 'reforestacion', 'reserva/reforestacion',
            
            # Other duplicates/unnecessary
            'apellido', 'nombre',  # Have full name in nombre_productor
            'dia', 'mes', 'año',  # Have full dates
            'rango de hectareas', 'rango de edad', 'rango altitud', 'rango',  # Ranges
            'rango de ha/productor', 'rango ha productor',  # More range variants
            'edad', 'edad socio', 'rango edad',  # Age fields (calculated from fecha_nacimiento)
            'direccion',  # Address
            
            # Old harvest/acopio columns from previous years
            'comp acopio 2020', 'acopio 2020', 'estimado 2021',
            'comp- acopio 2021', 'estiamdo 2021', 'acopio 2021',
            'estimado 2019', 'acopio 2019', 'estimado 2020', 
            'comp. acopio 2020', 'acopio 2020',
            'productividad qq/ha', 'productividad kg/ha',
            'estiamdo 2022', 'estimado kg 2022', 'acopio 2022',
            'estimado producción 2022', 'compromiso acopio 2022',
            'estimado producción 2023', 'estimado producción 2023 kg.',
            'compromiso acopio 2023', 'estiamdo 2022',
            'estimado en tm 2024',  # TM conversion (we have kg)
            'rdto. (sacos/ha)', 'rdto. (kg/ha)',  # Normalized (space instead of \n)
            'rdto. (kg/ha)de compromiso de acopio',
            'tm', 'saldo 2022', '% cumplimiento 2022', 'qq autorizados',
            'redto (sacos/ha)', 'diferencia de estimado y compromiso',
            
            # Other
            'condicion', 'proyectos', 'ee', 
            'uso de insumos no permitidos',
            'insumos prohibidos', 
            'uso de insumos no permitidos (fecha y producto)',
            'resultado control interno', 
            'resultados del control interno',
            'resultados de control interno',
            'ruta de inspección', 'dia de inspeccion', 'programacion',
            'cultivo total',  # Redundant: just area_cafe + area_crecimiento
            'producto biologico', 'unnamed: 56',
            'suma de ds.socio edad',
            'ue /per 2021', 'ue /per 2022', 'ue /per 2023',  # Normalized versions
            'nop 2022', 'nop 2023',  # Normalized versions
        ]
        
        # Find which ones actually exist
        cols_to_drop = [col for col in df.columns if col in drop_cols]
        
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            print(f"      Dropped {len(cols_to_drop)} old/redundant columns")
        
        return df
    
    def _final_cleaning(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply final cleaning steps to the combined data.
        
        Args:
            df: Combined DataFrame from all years
            
        Returns:
            Fully cleaned DataFrame
        """
        print("\nApplying final cleaning...")
        
        # Add metadata
        df['org_code'] = 'CH'
        df['country_code'] = 'PER'
        
        # Build data source string
        years = sorted(df['año_inspeccion'].unique())
        data_source = f"Chirinos inspection files: {', '.join(map(str, years))}"
        df['data_source'] = data_source
        
        print(f"  Added metadata columns")
        
        # Clean DNI if it exists
        if 'dni' in df.columns:
            df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='dni')
        
        # Convert data types
        df = self._convert_data_types(df)
        
        # Drop any remaining unnamed columns
        unnamed_cols = [col for col in df.columns if 'unnamed' in col.lower()]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols)
            print(f"  Dropped {len(unnamed_cols)} unnamed (empty) columns")
        
        return df
    
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert columns to appropriate data types."""
        print("\n  Converting data types...")
        
        # Date columns
        date_cols = [
            'fecha_nacimiento', 'fecha_ingreso', 
            'fecha_inicio_conversion', 'fecha_ultimo_control_interno'
        ]
        
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Numeric columns
        numeric_cols = [
            'area_total_ha', 'area_cafe', 'area_crecimiento',
            'area_invernadero_pasto', 'area_purma', 'area_bosque',
            'area_bosque_secundario', 'area_otros_cultivos',
            'cosecha_estimado_anterior_kg', 'cosecha_estimado_anterior_qq',
            'cosecha_acopio_anterior_kg', 'cosecha_estimado_actual_qq',
            'cosecha_estimado_actual_kg', 'rendimiento_estimado_qqha',
            'latitud', 'longitud'
        ]
        
        converted = 0
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                converted += 1
        
        # Integer columns
        int_cols = [
            'nro_socio', 'altitud', 'numero_parcelas',
            'compromiso_acopio_actual_qq', 'año_inspeccion',
            'numero_trabajadores_temporales', 'numero_trabajadores_mujeres'
        ]
        
        for col in int_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                converted += 1
        
        # String columns (ensure they're strings, not objects)
        str_cols = [
            'nombre_productor', 'base', 'caserio', 'distrito', 'provincia',
            'dni', 'genero', 'nombre_inspector_interno', 'dni_inspector_interno',
            'telefono', 'sellos', 'estado_socio', 'categoria', 'categoria_propuesta',
            'certificacion', 'org_code', 'country_code', 'data_source'
        ]
        
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '')
                converted += 1
        
        print(f"    Converted {converted} columns to appropriate types")
        
        return df
    
    def generate_farmer_ids(self, po_prefix: str = 'CH') -> pd.DataFrame:
        """
        Generate unique farmer IDs with deduplication.
        
        This method:
        1. Removes invalid rows (empty name or DNI)
        2. Standardizes names and DNIs
        3. Matches farmers by DNI first, then name
        4. Generates unique IDs
        
        Args:
            po_prefix: Prefix for farmer IDs (default: 'CH' for Chirinos)
            
        Returns:
            DataFrame with added columns:
            - nombre_estandarizado
            - dni_estandarizado
            - id_global
            - producers_direct_id_productor (formatted ID)
        """
        if self.data is None:
            raise ValueError("No data to process! Run clean_all_years() first.")
        
        print("\n" + "=" * 60)
        print("GENERATING FARMER IDs")
        print("=" * 60)
        
        df = self.data.copy()
        
        print(f"\nInput: {len(df)} records")
        
        # Step 1: Remove invalid rows (empty name AND DNI)
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
        
        print(f"After cleaning: {len(df)} valid records")
        
        # Step 2: Add standardized columns
        df['nombre_estandarizado'] = df['nombre_productor'].apply(self._standardize_name)
        df['dni_estandarizado'] = df['dni'].astype(str).replace('nan', '')
        
        # Step 3: Generate unique farmer IDs
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
        self.data = df
        
        return df
    
    def get_summary(self) -> dict:
        """Get summary statistics of the cleaned data."""
        if self.data is None:
            return {"error": "No data available. Run clean_all_years() first."}
        
        df = self.data
        
        summary = {
            "total_inspections": len(df),
            "years": sorted(df['año_inspeccion'].unique().tolist()),
            "inspections_by_year": df['año_inspeccion'].value_counts().sort_index().to_dict(),
            "columns": len(df.columns),
            "column_names": df.columns.tolist()
        }
        
        if 'pd_farmer_id' in df.columns:
            summary["unique_farmers"] = df['pd_farmer_id'].nunique()
        
        return summary
    
    def save(self, filename: str = 'chirinos_inspections_clean.pkl') -> Path:
        """
        Save cleaned data to pickle file.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        if self.data is None:
            raise ValueError("No data to save. Run clean_all_years() first.")
        
        output_path = self.output_dir / filename
        self.data.to_pickle(output_path)
        print(f"✅ Saved pickle: {output_path.name} ({len(self.data)} rows)")
        
        return output_path
 
 
def clean_chirinos_inspections() -> pd.DataFrame:
    """
    Convenience function to clean Chirinos inspections data.
    
    Returns:
        Cleaned DataFrame with farmer IDs
    """
    cleaner = ChirinosInspectionsCleaner()
    df = cleaner.clean_all_years()
    df = cleaner.generate_farmer_ids()
    cleaner.save()
    
    return df
 
 
if __name__ == "__main__":
    # Run the cleaner
    df = clean_chirinos_inspections()
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    summary = ChirinosInspectionsCleaner().get_summary() if hasattr(df, 'index') else {}
    for key, value in summary.items():
        if key == 'column_names':
            print(f"\n{key}:")
            for i, col in enumerate(value, 1):
                print(f"  {i}. {col}")
        elif key == 'inspections_by_year':
            print(f"\n{key}:")
            for year, count in sorted(value.items()):
                print(f"  {year}: {count:,}")
        else:
            print(f"{key}: {value}")
 