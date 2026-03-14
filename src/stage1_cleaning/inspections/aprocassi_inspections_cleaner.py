"""
Aprocassi Inspections Data Cleaner
 
Cleans and standardizes inspection (LPA) data from Aprocassi Producer Organization.
Handles single-file dataset with parcela-level data and UTM coordinate conversion.
 
Usage:
    from src.stage1_cleaning.inspections.aprocassi_inspections_cleaner import clean_aprocassi_inspections
    
    df = clean_aprocassi_inspections()
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
 
 
class AprocassiInspectionsCleaner:
    """
    Clean and standardize Aprocassi inspection data.
    
    Key features:
    - Reads from single LPA_PROYECTOS.xlsx file
    - Handles UTM coordinate conversion to lat/lon
    - Converts areas from m² to hectares if needed
    - Generates unique farmer IDs with deduplication
    
    Attributes:
        file_path: Path to the LPA Excel file
        data: Cleaned DataFrame
        dni_cleaner: DNI cleaning utility
    """
    
    def __init__(self):
        """Initialize the cleaner with file path and utilities."""
        self.dni_cleaner = DNICleaner()
        
        # Define file path
        raw_dir = DATA_DIR / 'raw' / 'inspections' / 'aprocassi'
        self.file_path = raw_dir / 'LPA_PROYECTOS.xlsx'
        
        # Output directory
        self.output_dir = DATA_DIR / 'processed' / 'inspections' / 'aprocassi'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data = None
    
    def clean(self) -> pd.DataFrame:
        """
        Clean the Aprocassi inspections data.
        
        Returns:
            Cleaned DataFrame with inspection data
        """
        print("\n" + "="*60)
        print("CLEANING APROCASSI INSPECTIONS")
        print("="*60)
        
        # 1. Read the file
        print(f"\nReading from {self.file_path.name}")
        df = pd.read_excel(self.file_path, sheet_name='PARCELA', header=1)
        print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
        
        # 2. Remove total row (last row)
        df = df.iloc[:-1]
        print(f"  Removed total row: {len(df):,} data rows")
        
        # 3. Select relevant columns
        df = self._select_columns(df)
        
        # 4. Process UTM coordinates
        df = self._process_utm_coordinates(df)
        
        # 5. Rename columns to standard names
        df = self._rename_to_standard(df)
        
        # 6. Convert data types
        df = self._convert_data_types(df)
        
        # 7. Add metadata
        df['org_code'] = 'AP'
        df['country_code'] = 'PER'
        df['data_source'] = 'APROCASSI/raw_data/LPA_PROYECTOS.xlsx'
        print(f"  Added metadata columns")
        
        # 8. Check data quality
        self._check_data_quality(df)
        
        # Store result
        self.data = df
        
        print(f"\n✅ Aprocassi inspections cleaning complete!")
        print(f"   Total inspections: {len(df):,}")
        
        return df
    
    def _select_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Select only the relevant columns for analysis.
        
        Args:
            df: DataFrame with all columns
            
        Returns:
            DataFrame with selected columns
        """
        selected_cols = [
            'SOCIO', 'DNI', 'DISTRITO PROVINCIA', 'BASE', 'ESTATUS 25', 
            'PARCELA', 'COORDENADA UTM', 'ALTITUD', 'Area Total Finca', 
            'Café Producción', 'Renovación', 'Poda/ Rehabilitación',
            'Ha Otros Cultivos', 'Inverna, Rastrojo, Bosque', 
            'Estim 2024', 'Acopio 24', 'Estim(qq) 2025'
        ]
        
        df = df[selected_cols].copy()
        print(f"  Selected {len(selected_cols)} relevant columns")
        
        return df
    
    def _process_utm_coordinates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process UTM coordinates: split and convert to lat/lon.
        
        Args:
            df: DataFrame with COORDENADA UTM column
            
        Returns:
            DataFrame with lat/lon coordinates
        """
        print("\n  Processing UTM coordinates...")
        
        # Split UTM coordinate into three parts
        utm_split = df['COORDENADA UTM'].str.split(expand=True)
        df['Zona_UTM'] = utm_split[0]
        df['X (Este)'] = pd.to_numeric(utm_split[1], errors='coerce')
        df['Y (Norte)'] = pd.to_numeric(utm_split[2], errors='coerce')
        
        print(f"    Split UTM coordinates into Zone, Easting, Northing")
        
        # Convert UTM to lat/lon
        coords = df.apply(
            lambda row: self._utm_to_latlon(row['X (Este)'], row['Y (Norte)']),
            axis=1
        )
        df['latitud'], df['longitud'] = zip(*coords)
        
        print(f"    Converted UTM to lat/lon")
        
        # Drop original UTM column
        df = df.drop(columns=['COORDENADA UTM'])
        
        return df
    
    def _utm_to_latlon(self, easting, northing, zone=17, hemisphere='S'):
        """
        Convert UTM coordinates to latitude/longitude using pyproj.
        
        Args:
            easting: UTM Easting
            northing: UTM Northing  
            zone: UTM zone (default 18 for Aprocassi)
            hemisphere: 'N' or 'S' (default 'S')
        
        Returns:
            Tuple of (latitude, longitude)
        """
        # Handle missing values
        if pd.isna(easting) or pd.isna(northing):
            return (None, None)
        
        try:
            from pyproj import Transformer
            
            # Construct EPSG code for UTM zone
            # Zone 18S = EPSG:32718
            utm_epsg = f'EPSG:327{zone}' if hemisphere == 'S' else f'EPSG:326{zone}'
            
            transformer = Transformer.from_crs(
                utm_epsg,      # UTM Zone 18S
                'EPSG:4326',   # WGS84
                always_xy=True
            )
            
            lon, lat = transformer.transform(float(easting), float(northing))
            return (lat, lon)
            
        except ImportError:
            print(f"    ⚠️  pyproj not installed, skipping UTM conversion")
            return (None, None)
        except Exception as e:
            print(f"    ⚠️  Error converting UTM ({easting}, {northing}): {e}")
            return (None, None)
    
    def _rename_to_standard(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename columns to standard names.
        
        Args:
            df: DataFrame with original column names
            
        Returns:
            DataFrame with standardized column names
        """
        rename_map = {
            'SOCIO': 'nombre_productor',
            'DNI': 'dni',
            'DISTRITO PROVINCIA': 'distrito',
            'BASE': 'base',
            'ESTATUS 25': 'categoria',
            'PARCELA': 'nombre_parcela',
            'ALTITUD': 'altitud',
            'Area Total Finca': 'area_total_ha',
            'Café Producción': 'area_cafe',
            'Renovación': 'area_crecimiento',
            'Poda/ Rehabilitación': 'area_rehabilitacion',
            'Ha Otros Cultivos': 'area_otros_cultivos',
            'Inverna, Rastrojo, Bosque': 'area_bosque',
            'Estim 2024': 'cosecha_estimado_anterior_qq',
            'Acopio 24': 'cosecha_acopio_anterior_qq',
            'Estim(qq) 2025': 'cosecha_estimado_actual_qq',
            'Zona_UTM': 'zona_utm',
            'X (Este)': 'x_este',
            'Y (Norte)': 'y_norte'
        }
        
        df = df.rename(columns=rename_map)
        print(f"  Renamed {len(rename_map)} columns to standard names")
        
        return df
    
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert columns to appropriate data types.
        
        Args:
            df: DataFrame with original types
            
        Returns:
            DataFrame with converted types
        """
        print("\n  Converting data types...")
        
        # 1. Clean DNI
        df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='dni')
        
        # 2. Area columns - check if conversion from m² needed
        area_cols = [col for col in df.columns if 'area_' in col]
        
        for col in area_cols:
            # Convert to numeric
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Check if values are in square meters (average > 100)
            avg_value = df[col].mean()
            if avg_value > 100:
                print(f"    Converting {col} from m² to hectares")
                df[col] = df[col] / 10000
            
            # Round to 2 decimals and fill NaN with 0
            df[col] = df[col].round(2).fillna(0)
        
        print(f"    Converted {len(area_cols)} area columns")
        
        # 3. Geographic coordinates
        geo_cols = ['longitud', 'latitud', 'x_este', 'y_norte']
        for col in geo_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f"    Converted {len([c for c in geo_cols if c in df.columns])} geographic columns")
        
        # 4. Altitude
        if 'altitud' in df.columns:
            df['altitud'] = pd.to_numeric(df['altitud'], errors='coerce').fillna(0).astype(int)
            print(f"    Converted altitude to integer")
        
        # 5. Yield/harvest columns
        yield_cols = [col for col in df.columns if 'cosecha' in col or 'acopio' in col]
        for col in yield_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        
        if yield_cols:
            print(f"    Converted {len(yield_cols)} yield columns")
        
        return df
    
    def _check_data_quality(self, df: pd.DataFrame) -> None:
        """
        Check for data quality issues and print warnings.
        
        Args:
            df: DataFrame to check
        """
        print("\n  Data quality checks...")
        
        # Check for missing DNIs
        missing_dni = df[(df['dni'] == '') | (df['dni'] == 'nan')]
        if not missing_dni.empty:
            print(f"    ⚠️  {len(missing_dni)} rows with missing DNI")
        
        # Check for extreme area values
        large_areas = df[df['area_total_ha'] > 50]
        if not large_areas.empty:
            print(f"    ⚠️  {len(large_areas)} rows with area_total_ha > 50 hectares")
        
        # Check for missing coordinates
        missing_coords = df[df['latitud'].isna() | df['longitud'].isna()]
        if not missing_coords.empty:
            print(f"    ⚠️  {len(missing_coords)} rows with missing lat/lon coordinates")
    
    def generate_farmer_ids(self, po_prefix: str = 'AP') -> pd.DataFrame:
        """
        Generate unique farmer IDs with deduplication.
        Uses the improved version from Chirinos/Huadquiña.
        
        Args:
            po_prefix: Prefix for farmer IDs (default: 'AP' for Aprocassi)
            
        Returns:
            DataFrame with added columns:
            - nombre_estandarizado
            - dni_estandarizado
            - id_global
            - producers_direct_id_productor (formatted ID)
        """
        if self.data is None:
            raise ValueError("No data to process! Run clean() first.")
        
        print("\n" + "="*60)
        print("GENERATING FARMER IDs")
        print("="*60)
        
        df = self.data.copy()
        
        print(f"\nInput: {len(df):,} records")
        
        # STEP 0: Remove invalid rows (empty name AND DNI)
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
        
        # Step 1: Add standardized columns
        df['nombre_estandarizado'] = df['nombre_productor'].apply(self._standardize_name)
        df['dni_estandarizado'] = df['dni'].astype(str).replace('nan', '')
        
        # Step 2: Generate unique farmer IDs
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
        
        # Sort by farmer ID and category
        df = df.sort_values(['producers_direct_id_productor', 'categoria'])
        print(f"  Sorted by farmer ID and category")
        
        # Update stored data
        self.data = df
        
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
    
    def get_summary(self) -> dict:
        """Get summary statistics of the cleaned data."""
        if self.data is None:
            return {"error": "No data available. Run clean() first."}
        
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
    
    def save(self, filename: str = 'aprocassi_inspections_clean.pkl') -> Path:
        """
        Save cleaned data to pickle file.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        if self.data is None:
            raise ValueError("No data to save. Run clean() first.")
        
        output_path = self.output_dir / filename
        self.data.to_pickle(output_path)
        print(f"✅ Saved pickle: {output_path.name} ({len(self.data):,} rows)")
        
        return output_path
 
 
def clean_aprocassi_inspections() -> pd.DataFrame:
    """
    Convenience function to clean Aprocassi inspections data.
    
    Returns:
        Cleaned DataFrame
    """
    cleaner = AprocassiInspectionsCleaner()
    df = cleaner.clean()
    df = cleaner.generate_farmer_ids()
    cleaner.save()
    
    return df
 
 
if __name__ == "__main__":
    # Run the cleaner
    df = clean_aprocassi_inspections()
    
    # Print summary
    cleaner = AprocassiInspectionsCleaner()
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
                                 'dni', 'base', 'area_cafe'] 
                    if c in df.columns]
    print(df[display_cols].head(3).to_string(index=False))
    
    print(f"\nColumn names:")
    print(df.columns.tolist())
    
    print("\n" + "="*60)