"""
Bagua Grande Inspections Cleaner - Full Featured

Processes the Bagua Grande LPA (Lista de Productores Activos) file with complete
data cleaning, type conversions, and optional farmer ID generation.

Matches the notebook cleaning logic exactly.

Author: Daniela
"""

import pandas as pd
import numpy as np
import unicodedata
from typing import Optional, Dict, List, Tuple
from pathlib import Path

# Import utilities
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.utils import FileHandler, DNICleaner, ColumnCleaner

# For UTM coordinate conversion
try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False
    print("⚠️  Warning: pyproj not installed. UTM conversion will be skipped.")
    print("   Install with: pip install pyproj")


class BaguaInspectionsCleaner:
    """
    Clean Bagua Grande inspection data from LPA Excel file.
    
    Features:
    - Multi-row header processing
    - UTM Zone 17S coordinate conversion
    - Column renaming to standardized Spanish names
    - Data type conversions (numeric, datetime)
    - CAC010 DNI correction
    - Optional farmer ID generation across sheets
    
    Usage:
        cleaner = BaguaInspectionsCleaner('raw_data/LPA 24.xlsx')
        clean_data = cleaner.clean_all_sheets()
        
        # Optional: Generate farmer IDs
        clean_data_with_ids = cleaner.generate_farmer_ids()
        
        cleaner.save('processed_data/bagua_inspections_clean.pkl')
    """
    
    # Configuration
    HEADER_ROWS = [7, 8, 9, 10]
    DATA_START_ROW = 11
    
    # UTM Zone 17S for Bagua Grande (EPSG:32717)
    UTM_EPSG = 'EPSG:32717'
    WGS84_EPSG = 'EPSG:4326'
    
    # Specific columns to drop (in addition to Column_ and Unnamed:)
    COLUMNS_TO_DROP = [
        'Control interno_Ultimo uso de insumos no permitidos (fecha y producto)',
        'Control externo (años) (6)',
        'Nº',
        'No'  # Some sheets use 'No' instead of 'Nº'
    ]
    
    # Sheet-specific column mappings (Spanish → standardized Spanish)
    ECOL_COLUMN_MAPPING = {
        'Cod': 'nro_socio',
        'Nombre productor(a)': 'nombre_productor',
        'DNI': 'dni',
        'Dirección (Zona, Sector, Compañía)': 'ubicacion',
        'Cobases/ organización': 'base',
        'Nombe de las parcelas': 'nombre_parcela',
        'Datos de georeferenciación UTM_ZONA': 'zona_utm',
        'Altitud m.s.n.m.': 'altitud',
        'X (Este)': 'x_este',
        'Y (Norte)': 'y_norte',
        'Superficie (ha)_Area total finca': 'area_total_ha',
        'Cultivo ecológico_Prod': 'area_cafe',
        'Crec.': 'area_crecimiento',
        'Parcelas en_conversión, sólo_si necesario': 'area_conversion',
        'Otros cultivos': 'area_otros_cultivos',
        'Bosque_Pastura_Reserva': 'area_bosque',
        'Cosecha (qq, kg) (estado)_Estimado año anterior qq 55.20': 'cosecha_estimado_anterior_qq',
        'Cosecha/Acopio año anterior qq': 'cosecha_acopio_anterior_qq',
        'Estimado año actual qq': 'cosecha_estimado_actual_qq',
        'Estimado año actual Kg': 'cosecha_estimado_actual_kg',
        'Rendi-miento actual (Kg/ha)': 'rendimiento_actual_kgha',
        'Fecha control interno': 'fecha_ultimo_control_interno',
        'Nombre Inspector interno': 'nombre_inspector_interno',
        'Resultado control interno': 'resultado_control_interno',
        'Control externo_Inicio de conversión': 'fecha_inicio_conversion',
        'Certificación IMOcert_UE / RTPO_Año anterior': 'certificacion_ue_rtpo_anterior',
        'Año actual': 'certificacion_ue_rtpo_actual',
        'NOP_Año actual': 'certificacion_nop_actual'
    }
    
    C0_COLUMN_MAPPING = {
        'Cod': 'nro_socio',
        'Nombre socio': 'nombre_productor',
        'DNI': 'dni',
        'Zona, Sector, Compañía': 'ubicacion',
        'cobases': 'base',
        'Nombre de la parcelas': 'nombre_parcela',
        'Datos de georeferenciación UTM_Zona': 'zona_utm',
        'Altitud m.s.n.m.': 'altitud',
        'X (Este)': 'x_este',
        'Y (Norte)': 'y_norte',
        'Superficie (ha)_Area_Total_Finca': 'area_total_ha',
        'Cultivo ecológico_Prod': 'area_cafe',
        'Crec.': 'area_crecimiento',
        'Parcelas en_conversión, sólo_si necesario': 'area_conversion',
        'Otros cultivos': 'area_otros_cultivos',
        'Bosque_Pastura_Reserva': 'area_bosque',
        'Cosecha (qq, kg) (estado)_Estimado año anterior qq': 'cosecha_estimado_anterior_qq',
        'Cosecha/Acopio año anterior qq': 'cosecha_acopio_anterior_qq',
        'Estimado año actual qq': 'cosecha_estimado_actual_qq',
        'Estimado año actual Kg': 'cosecha_estimado_actual_kg',
        'Rendi-miento actual (Kg/ha)': 'rendimiento_actual_kgha',
        'Fecha control interno': 'fecha_ultimo_control_interno',
        'Nombre Inspector interno': 'nombre_inspector_interno',
        'Resultado control interno': 'resultado_control_interno',
        'Control externo_Inicio de conversión': 'fecha_inicio_conversion',
        'Certificación IMOcert_UE / RTPO_Año anterior': 'certificacion_ue_rtpo_anterior',
        'Año actual': 'certificacion_ue_rtpo_actual'
    }
    
    C1_COLUMN_MAPPING = {
        'Cod': 'nro_socio',
        'Nombre socio': 'nombre_productor',
        'DNI': 'dni',
        'Zona, Sector, Compañía': 'ubicacion',
        'cobase': 'base',
        'Nombre de las parcelas': 'nombre_parcela',
        'Datos de georeferenciación UTM_Zona': 'zona_utm',
        'Altitud m.s.n.m.': 'altitud',
        'X (Este)': 'x_este',
        'Y (Norte)': 'y_norte',
        'Superficie (ha)_Area_Total_Finca': 'area_total_ha',
        'Cultivo ecológico_Prod': 'area_cafe',
        'Crec.': 'area_crecimiento',
        'Parcelas en_conversión, sólo_si necesario': 'area_conversion',
        'Otros cultivos': 'area_otros_cultivos',
        'Bosque_Pastura_Reserva': 'area_bosque',
        'Cosecha (qq, kg) (estado)_Estimado año anterior qq': 'cosecha_estimado_anterior_qq',
        'Cosecha/Acopio año anterior qq': 'cosecha_acopio_anterior_qq',
        'Estimado año actual qq': 'cosecha_estimado_actual_qq',
        'Estimado año actual Kg': 'cosecha_estimado_actual_kg',
        'Rendi-miento actual (Kg/ha)': 'rendimiento_actual_kgha',
        'Fecha control interno': 'fecha_ultimo_control_interno',
        'Nombre Inspector interno': 'nombre_inspector_interno',
        'Resultado control interno': 'resultado_control_interno',
        'Control externo_Inicio de conversión': 'fecha_inicio_conversion',
        'Certificación IMOcert_UE / RTPO_Año anterior': 'certificacion_ue_rtpo_anterior',
        'Año actual': 'certificacion_ue_rtpo_actual'
    }
    
    C2_COLUMN_MAPPING = {
        'Cod': 'nro_socio',
        'Nombre socio': 'nombre_productor',
        'DNI': 'dni',
        'Zona, Sector, Compañía': 'ubicacion',
        'cobases/asociacion.': 'base',
        'Nombre de las parcelas': 'nombre_parcela',
        'Datos de georeferenciación UTM_Zona': 'zona_utm',
        'Altitud m.s.n.m.': 'altitud',
        'X (Este)': 'x_este',
        'Y (Norte)': 'y_norte',
        'Superficie (ha)_Area_Total_Finca': 'area_total_ha',
        'Cultivo ecológico_Prod': 'area_cafe',
        'Crec.': 'area_crecimiento',
        'Parcelas en_conversión, sólo_si necesario': 'area_conversion',
        'Otros cultivos': 'area_otros_cultivos',
        'Bosque_Pastura_Reserva': 'area_bosque',
        'Cosecha (qq, kg) (estado)_Estimado año anterior qq': 'cosecha_estimado_anterior_qq',
        'Cosecha/Acopio año anterior qq': 'cosecha_acopio_anterior_qq',
        'Estimado año actual qq': 'cosecha_estimado_actual_qq',
        'Estimado año actual Kg': 'cosecha_estimado_actual_kg',
        'Rendi-miento actual (Kg/ha)': 'rendimiento_actual_kgha',
        'Fecha control interno': 'fecha_ultimo_control_interno',
        'Nombre Inspector interno': 'nombre_inspector_interno',
        'Resultado control interno': 'resultado_control_interno',
        'Control externo_Inicio de conversión': 'fecha_inicio_conversion',
        'Certificación IMOcert_UE / RTPO_Año anterior': 'certificacion_ue_rtpo_anterior',
        'Año actual': 'certificacion_ue_rtpo_actual'
    }
    
    def __init__(self, file_path: str, base_path: Optional[str] = None):
        """
        Initialize the Bagua cleaner.
        
        Args:
            file_path: Path to the Bagua LPA Excel file
            base_path: Optional base directory for all data files
        """
        self.file_path = file_path
        
        # Initialize utilities
        self.file_handler = FileHandler(base_path=base_path)
        self.dni_cleaner = DNICleaner(verbose=True)
        self.col_cleaner = ColumnCleaner()
        
        # Storage for cleaned data
        self.data = None
        self.ecol_df = None
        self.c0_df = None
        self.c1_df = None
        self.c2_df = None
    
    def clean_all_sheets(self) -> pd.DataFrame:
        """
        Clean all sheets and combine them.
        
        Returns:
            Combined DataFrame with all cleaned inspection data
        """
        print("\n" + "=" * 60)
        print("CLEANING BAGUA GRANDE INSPECTIONS")
        print("=" * 60)
        
        # Clean each sheet
        print("\n1. Cleaning Ecol (Ecological) sheet...")
        self.ecol_df = self._clean_sheet('Ecol', self.ECOL_COLUMN_MAPPING, 'Orgánico')
        
        print("\n2. Cleaning C0 (Conversion 0) sheet...")
        self.c0_df = self._clean_sheet('C0', self.C0_COLUMN_MAPPING, 'C0')
        
        print("\n3. Cleaning C1 (Conversion 1) sheet...")
        self.c1_df = self._clean_sheet('C1', self.C1_COLUMN_MAPPING, 'C1')
        
        print("\n4. Cleaning C2 (Conversion 2) sheet...")
        self.c2_df = self._clean_sheet('C2', self.C2_COLUMN_MAPPING, 'C2')
        
        # Fix CAC010 DNI before combining (Bagua-specific fix)
        print("\n5. Applying Bagua-specific fixes...")
        self._fix_cac010_dni()
        
        # Combine all sheets
        print("\n6. Combining all sheets...")
        self.data = pd.concat(
            [self.ecol_df, self.c0_df, self.c1_df, self.c2_df], 
            ignore_index=True
        )
        
        print(f"\n✅ Bagua cleaning complete!")
        print(f"   Total rows: {len(self.data)}")
        print(f"   - Ecol: {len(self.ecol_df)} rows")
        print(f"   - C0: {len(self.c0_df)} rows")
        print(f"   - C1: {len(self.c1_df)} rows")
        print(f"   - C2: {len(self.c2_df)} rows")
        
        return self.data
    
    def _clean_sheet(self, sheet_name: str, column_mapping: Dict, categoria: str) -> pd.DataFrame:
        """
        Clean a single sheet with full processing.
        
        Args:
            sheet_name: Name of the sheet
            column_mapping: Dictionary for column renaming
            categoria: Category value ('Orgánico', 'C0', 'C1', 'C2')
            
        Returns:
            Fully cleaned DataFrame
        """
        # 1. Read with multi-row headers
        df = self.file_handler.read_multi_header(
            file_path=self.file_path,
            sheet_name=sheet_name,
            header_rows=self.HEADER_ROWS,
            data_start_row=self.DATA_START_ROW,
            remove_total=True,
            clean_columns=False  # We'll do custom column cleaning
        )
        
        # 2. Drop specific unwanted columns
        cols_to_drop = [col for col in df.columns 
                       if col.startswith('Column_') or 
                       'Unnamed:' in str(col) or 
                       col in self.COLUMNS_TO_DROP]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            print(f"  Dropped {len(cols_to_drop)} administrative columns")
        
        # 3. Convert UTM coordinates to Lat/Long (before renaming!)
        df = self._convert_utm_coordinates(df)
        
        # 4. Rename columns to standardized names
        df = self._rename_columns(df, column_mapping, sheet_name)
        
        # 5. Clean DNI
        if 'dni' in df.columns:
            df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='DNI')
        else:
            print(f"  ⚠️  No DNI column found in {sheet_name} sheet")
            df['dni'] = ''
        
        # 6. Convert data types
        df = self._convert_data_types(df)
        
        # 7. Add metadata
        df['categoria'] = categoria
        df['org_code'] = 'BG'
        df['country_code'] = 'PER'
        df['data_source'] = f'{Path(self.file_path).name} - {sheet_name}'
        
        return df
    
    def _convert_utm_coordinates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert UTM Zone 17S coordinates to Latitude/Longitude.
        
        Args:
            df: DataFrame with UTM columns
            
        Returns:
            DataFrame with added latitude/longitude columns
        """
        if not PYPROJ_AVAILABLE:
            print("  ⚠️  Skipping UTM conversion (pyproj not installed)")
            return df
        
        # Find UTM columns (before renaming!)
        x_cols = [col for col in df.columns if 'Este' in str(col) or 'X (' in str(col)]
        y_cols = [col for col in df.columns if 'Norte' in str(col) or 'Y (' in str(col)]
        
        if not x_cols or not y_cols:
            print("  ℹ️  No UTM coordinate columns found")
            return df
        
        x_col = x_cols[0]
        y_col = y_cols[0]
        
        print(f"  Converting UTM Zone 17S coordinates: {x_col}, {y_col}")
        
        # Create transformer for UTM Zone 17S → WGS84
        transformer = Transformer.from_crs(
            self.UTM_EPSG,  # UTM Zone 17S
            self.WGS84_EPSG,  # WGS84 lat/lon
            always_xy=True
        )
        
        # Convert coordinates
        def convert_point(row):
            try:
                x = float(row[x_col])
                y = float(row[y_col])
                
                if pd.isna(x) or pd.isna(y):
                    return pd.Series({'latitud': np.nan, 'longitud': np.nan})
                
                # Transform
                lon, lat = transformer.transform(x, y)
                return pd.Series({'latitud': lat, 'longitud': lon})
            
            except (ValueError, TypeError):
                return pd.Series({'latitud': np.nan, 'longitud': np.nan})
        
        # Apply conversion
        coords = df.apply(convert_point, axis=1)
        df['latitud'] = coords['latitud']
        df['longitud'] = coords['longitud']
        
        valid_coords = df['latitud'].notna().sum()
        print(f"  ✅ Converted {valid_coords} coordinate pairs")
        
        return df
    
    def _rename_columns(self, df: pd.DataFrame, column_mapping: Dict, sheet_name: str) -> pd.DataFrame:
        """
        Rename columns using sheet-specific mapping.
        
        Args:
            df: DataFrame with original column names
            column_mapping: Dictionary of old_name → new_name
            sheet_name: Name of sheet (for logging)
            
        Returns:
            DataFrame with renamed columns
        """
        
        # Apply only mappings for columns that exist
        existing_mappings = {k: v for k, v in column_mapping.items() if k in df.columns}


        # Apply only mappings for columns that exist
        existing_mappings = {k: v for k, v in column_mapping.items() if k in df.columns}
        
        if existing_mappings:
            df = df.rename(columns=existing_mappings)
            print(f"  Renamed {len(existing_mappings)} columns")
        
        # Warn about expected columns that weren't found
        missing = set(column_mapping.keys()) - set(existing_mappings.keys())
        if missing and len(missing) < 5:  # Don't spam if many missing
            for col in list(missing)[:3]:
                print(f"  ⚠️  Expected column '{col}' not found in {sheet_name}")
        
        return df
    
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert columns to appropriate data types.
        
        Handles:
        - Area columns → numeric, 2 decimals, fillna(0)
        - Geo columns → numeric
        - Date columns → datetime
        - Yield columns → numeric, 2 decimals, fillna(0)
        
        Args:
            df: DataFrame to convert
            
        Returns:
            DataFrame with converted types
        """
        # Area columns: numeric with 2 decimals, fill NaN with 0
        area_columns = [col for col in df.columns if col.startswith('area_')]
        for col in area_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        
        if area_columns:
            print(f"  Converted {len(area_columns)} area columns to numeric")
        
        # Geolocation columns: numeric
        geo_columns = ['x_este', 'y_norte', 'latitud', 'longitud', 'altitud']
        for col in geo_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Date columns: datetime
        date_columns = [
            'fecha_ultimo_control_interno',
            'fecha_inicio_conversion',
            'fecha_ultimo_control_externo'
        ]
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Yield/harvest columns: numeric with 2 decimals, fill NaN with 0
        yield_columns = [col for col in df.columns if 'cosecha_' in col or 'rendimiento_' in col]
        for col in yield_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        
        return df
    
    def _fix_cac010_dni(self) -> None:
        """
        Fix DNI for farmer CAC010 (Bagua-specific correction).
        
        This farmer has an incorrect DNI in the source data that needs correction.
        """
        sheets_to_fix = [
            (self.ecol_df, 'Ecol'),
            (self.c0_df, 'C0'),
            (self.c1_df, 'C1'),
            (self.c2_df, 'C2')
        ]
        
        cac010_found = False
        for df, sheet_name in sheets_to_fix:
            if df is not None and 'nro_socio' in df.columns:
                mask = df['nro_socio'] == 'CAC010'
                if mask.any():
                    old_dni = df.loc[mask, 'dni'].iloc[0]
                    df.loc[mask, 'dni'] = '33827154'
                    print(f"  ✓ Fixed CAC010 in {sheet_name}: {old_dni} → 33827154")
                    cac010_found = True
        
        if not cac010_found:
            print("  ℹ️  CAC010 not found in any sheet")
    
    def generate_farmer_ids(self, po_prefix: str = 'BG') -> pd.DataFrame:
        """
        Generate global farmer IDs across all sheets.
        
        This method:
        1. Standardizes farmer names (removes accents, handles formats)
        2. Matches farmers within each sheet (DNI priority, then name)
        3. Creates global IDs across all sheets
        4. Generates PD_ID_Productor with prefix
        
        Args:
            po_prefix: Prefix for farmer IDs (default: 'BG' for Bagua)
            
        Returns:
            DataFrame with added columns:
            - nombre_estandarizado
            - dni_estandarizado
            - id_hoja (within-sheet ID)
            - id_global (cross-sheet ID)
            - producers_direct_id_productor (formatted ID)
        
        Example:
            clean_data = cleaner.clean_all_sheets()
            final_data = cleaner.generate_farmer_ids()
            cleaner.save('output.pkl')
        """
        if self.data is None:
            raise ValueError("No data to process! Run clean_all_sheets() first.")
        
        print("\n" + "=" * 60)
        print("GENERATING FARMER IDs")
        print("=" * 60)
        
        # Add sheet identifiers for tracking
        self.ecol_df = self.ecol_df.copy()
        self.c2_df = self.c2_df.copy()
        self.c1_df = self.c1_df.copy()
        self.c0_df = self.c0_df.copy()
          
        # Mark plots within each sheet
        print("\n1. Identifying farmers within each sheet...")
        ecol_marked = self._mark_farmer_plots(self.ecol_df, 'Ecol')
        c2_marked = self._mark_farmer_plots(self.c2_df, 'C2')
        c1_marked = self._mark_farmer_plots(self.c1_df, 'C1')
        c0_marked = self._mark_farmer_plots(self.c0_df, 'C0')
        
        # Create global IDs across sheets
        print("\n2. Creating global farmer IDs across sheets...")
        final_df = self._create_global_farmer_ids(
            [ecol_marked, c2_marked, c1_marked, c0_marked],
            po_prefix=po_prefix
        )
        
        # Update stored data
        self.data = final_df
        
        unique_farmers = final_df['producers_direct_id_productor'].nunique()
        print(f"\n✅ Generated {unique_farmers} unique farmer IDs")
        
        return final_df
    
    def _standardize_name(self, name: str) -> str:
        """
        Standardize farmer name for matching.
        
        - Removes accents
        - Handles "Lastname, Firstname" → "Firstname Lastname"
        - Strips whitespace
        
        Args:
            name: Original name
            
        Returns:
            Standardized name
        """
        if pd.isna(name):
            return ''
        
        name = str(name)
        
        # Remove accents
        name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
        
        # Handle "Lastname, Firstname" format
        if ',' in name:
            parts = name.split(',')
            if len(parts) == 2:
                name = f"{parts[1].strip()} {parts[0].strip()}"
        
        return name.strip()
    
    def _mark_farmer_plots(self, df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
        """
        Mark which rows belong to which farmer within a sheet.
        
        Priority: DNI first, then name.
        
        Args:
            df: DataFrame for one sheet
            sheet_name: Name of sheet
            
        Returns:
            DataFrame with id_temporal and id_hoja columns
        """
        df = df.copy()
        
        # Add standardized columns
        if 'nombre_productor' in df.columns:
            df['nombre_estandarizado'] = df['nombre_productor'].apply(self._standardize_name)
        else:
            df['nombre_estandarizado'] = ''
        
        if 'dni' in df.columns:
            df['dni_estandarizado'] = df['dni'].astype(str).replace('nan', '')
        else:
            df['dni_estandarizado'] = ''
        
        df['id_temporal'] = None
        current_id = 1
        
        # Track farmers by DNI and name
        farmer_registry = {}
        
        for idx, row in df.iterrows():
            current_dni = row['dni_estandarizado']
            current_name = row['nombre_estandarizado']
            
            # Skip empty rows
            if current_dni == '' and current_name == '':
                continue
            
            # Match by DNI first
            if current_dni != '' and current_dni in farmer_registry:
                df.loc[idx, 'id_temporal'] = farmer_registry[current_dni]
            # Match by name if DNI missing
            elif current_dni == '' and current_name != '' and current_name in farmer_registry:
                df.loc[idx, 'id_temporal'] = farmer_registry[current_name]
            # New farmer
            else:
                df.loc[idx, 'id_temporal'] = current_id
                if current_dni != '':
                    farmer_registry[current_dni] = current_id
                if current_name != '':
                    farmer_registry[current_name] = current_id
                current_id += 1
        
        # Propagate IDs to additional plot rows
        for idx, row in df.iterrows():
            if pd.isna(df.at[idx, 'id_temporal']):
                previous_ids = df.loc[:idx-1, 'id_temporal'].dropna()
                if len(previous_ids) > 0:
                    df.loc[idx, 'id_temporal'] = previous_ids.iloc[-1]
        
        # Add sheet identifier
        df['id_hoja'] = sheet_name + "_" + df['id_temporal'].astype(str)
        
        print(f"  {sheet_name}: Found {df['id_temporal'].nunique()} farmers")
        
        return df
    
    def _create_global_farmer_ids(self, all_dfs: List[pd.DataFrame], po_prefix: str) -> pd.DataFrame:
        """
        Create global farmer IDs across all sheets.
        
        Args:
            all_dfs: List of DataFrames (one per sheet)
            po_prefix: Prefix for IDs (e.g., 'BG')
            
        Returns:
            Combined DataFrame with global IDs
        """
        # Combine all sheets
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        combined_df['id_global'] = None
        current_id = 1
        
        # Track farmers globally
        farmer_registry = {}
        
        # First pass: rows with farmer details
        farmer_rows = combined_df[
            (combined_df['dni_estandarizado'] != '') | 
            (combined_df['nombre_estandarizado'] != '')
        ]
        
        for idx, row in farmer_rows.iterrows():
            current_dni = row['dni_estandarizado']
            current_name = row['nombre_estandarizado']
            
            # Match by DNI first
            if current_dni != '' and current_dni in farmer_registry:
                combined_df.loc[idx, 'id_global'] = farmer_registry[current_dni]
            # Match by name if DNI missing
            elif current_dni == '' and current_name != '' and current_name in farmer_registry:
                combined_df.loc[idx, 'id_global'] = farmer_registry[current_name]
            # New farmer
            else:
                combined_df.loc[idx, 'id_global'] = current_id
                if current_dni != '':
                    farmer_registry[current_dni] = current_id
                if current_name != '':
                    farmer_registry[current_name] = current_id
                current_id += 1
        
        # Second pass: propagate IDs to rows missing farmer details
        for sheet_id in combined_df['id_hoja'].unique():
            if pd.notna(sheet_id):
                sheet_mask = combined_df['id_hoja'] == sheet_id
                farmer_ids = combined_df.loc[sheet_mask, 'id_global'].dropna()
                if len(farmer_ids) > 0:
                    main_id = farmer_ids.iloc[0]
                    combined_df.loc[sheet_mask, 'id_global'] = main_id
        
        # Create formatted ID
        combined_df['producers_direct_id_productor'] = (
            po_prefix + combined_df['id_global'].astype(str).str.zfill(5)
        )
        
        # Sort by ID and categoria
        combined_df = combined_df.sort_values(['producers_direct_id_productor', 'categoria'], kind='stable')
        
        return combined_df
    
    def save(self, output_path: str) -> None:
        """
        Save cleaned data to pickle file.
        
        Args:
            output_path: Path where cleaned data should be saved
        """
        if self.data is None:
            raise ValueError("No data to save! Run clean_all_sheets() first.")
        
        self.file_handler.save_pickle(self.data, output_path)
    
    def get_summary(self) -> Dict:
        """
        Get summary statistics about the cleaned data.
        
        Returns:
            Dictionary with summary information
        """
        if self.data is None:
            return {"status": "No data cleaned yet"}
        
        summary = {
            "total_rows": len(self.data),
            "total_columns": len(self.data.columns),
            "ecol_rows": len(self.ecol_df) if self.ecol_df is not None else 0,
            "c0_rows": len(self.c0_df) if self.c0_df is not None else 0,
            "c1_rows": len(self.c1_df) if self.c1_df is not None else 0,
            "c2_rows": len(self.c2_df) if self.c2_df is not None else 0,
            "unique_farmers_dni": self.data['dni'].nunique() if 'dni' in self.data.columns else 0,
            "missing_dni": (self.data['dni'] == '').sum() if 'dni' in self.data.columns else 0
        }
        
        # Add farmer ID stats if generated
        if 'producers_direct_id_productor' in self.data.columns:
            summary['unique_farmers_global'] = self.data['producers_direct_id_productor'].nunique()
        
        return summary


# Convenience function
def clean_bagua_inspections(file_path: str,
                            output_path: Optional[str] = None,
                            base_path: Optional[str] = None,
                            generate_ids: bool = False) -> pd.DataFrame:
    """
    Convenience function to clean Bagua inspections in one call.
    
    Args:
        file_path: Path to Bagua LPA Excel file
        output_path: Optional path to save cleaned data
        base_path: Optional base directory for data files
        generate_ids: Whether to generate farmer IDs
        
    Returns:
        Cleaned DataFrame
    """
    cleaner = BaguaInspectionsCleaner(file_path, base_path)
    clean_data = cleaner.clean_all_sheets()
    
    if generate_ids:
        clean_data = cleaner.generate_farmer_ids()
    
    if output_path:
        cleaner.save(output_path)
    
    return clean_data


if __name__ == "__main__":
    print("Bagua Inspections Cleaner - Full Featured")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ Multi-row header processing")
    print("  ✓ UTM Zone 17S coordinate conversion")
    print("  ✓ Column renaming to standardized names")
    print("  ✓ Data type conversions")
    print("  ✓ CAC010 DNI correction")
    print("  ✓ Optional farmer ID generation")
    print("\nUsage:")
    print("  cleaner = BaguaInspectionsCleaner('LPA 24.xlsx')")
    print("  clean_data = cleaner.clean_all_sheets()")
    print("  clean_data = cleaner.generate_farmer_ids()  # Optional")
    print("  cleaner.save('bagua_clean.pkl')")










