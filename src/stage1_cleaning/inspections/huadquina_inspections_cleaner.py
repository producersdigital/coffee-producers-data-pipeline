"""
Huadquiña Inspections Cleaner

Processes Huadquiña inspection data from their standardized template.
Unlike Bagua's 4-sheet structure, Huadquiña uses a single template sheet.

Author: Daniela
"""

import pandas as pd
import numpy as np
import unicodedata
from typing import Optional, Dict
from pathlib import Path

# Import utilities
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.utils import FileHandler, DNICleaner, ColumnCleaner


class HuadquinaInspectionsCleaner:
    """
    Clean Huadquiña inspection data from their template.
    
    Huadquiña uses a standardized Excel template with a single sheet.
    This is much simpler than Bagua's multi-sheet LPA structure.
    
    The template is already at farmer-level (not plot-level), so we don't
    need to handle multiple plot rows per farmer.
    
    Usage:
        cleaner = HuadquinaInspectionsCleaner('raw_data/Plantilla de Inspecciones vf.xlsx')
        clean_data = cleaner.clean()
        clean_data = cleaner.generate_farmer_ids()  # Optional
        cleaner.save('processed_data/huadquina_inspections_clean.pkl')
    """
    
    # Sheet name in template
    SHEET_NAME = 'Hoja1'
    
    def __init__(self, file_path: str, base_path: Optional[str] = None):
        """
        Initialize the Huadquiña inspections cleaner.
        
        Args:
            file_path: Path to the Huadquiña template Excel file
            base_path: Optional base directory for all data files
        """
        self.file_path = file_path
        
        # Initialize utilities
        self.file_handler = FileHandler(base_path=base_path)
        self.dni_cleaner = DNICleaner(verbose=True)
        self.col_cleaner = ColumnCleaner()
        
        # Storage for cleaned data
        self.data = None
    
    def clean(self) -> pd.DataFrame:
        """
        Clean the Huadquiña inspections data.
        
        This is the main entry point.
        
        Returns:
            Cleaned DataFrame with inspection data
        """
        print("\n" + "=" * 60)
        print("CLEANING HUADQUIÑA INSPECTIONS")
        print("=" * 60)
        
        # 1. Read the template file
        print(f"\nReading template from {Path(self.file_path).name}")
        df = self.file_handler.read_excel_simple(
            file_path=self.file_path,
            sheet_name=self.SHEET_NAME,
            header=0,  # Template has header on first row
            remove_total=False  # Template is already clean
        )
        
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
        
        # 2. Clean DNI
        if 'dni' in df.columns:
            df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='DNI')
        else:
            print(f"  ⚠️  No DNI column found")
            df['dni'] = ''
        
        # 3. Clean phone numbers
        df = self._clean_phone_numbers(df)
        
        # 4. Convert data types
        df = self._convert_data_types(df)
        
        # 5. Lowercase categoria
        if 'categoria' in df.columns:
            df['categoria'] = df['categoria'].str.lower()
            print(f"  Converted categoria to lowercase")
        
        # 6. Add metadata
        df['org_code'] = 'HU'
        df['country_code'] = 'PER'
        df['data_source'] = f'{Path(self.file_path).name} - {self.SHEET_NAME}'
        print(f"  Added metadata columns")
        
        # 7. Data quality warnings
        self._check_data_quality(df)
        
        # Store cleaned data
        self.data = df
        
        print(f"\n✅ Huadquiña inspections cleaning complete!")
        print(f"   Total rows: {len(df)}")
        
        return df
    
    def _clean_phone_numbers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean phone number columns.
        
        Args:
            df: DataFrame with phone columns
            
        Returns:
            DataFrame with cleaned phone numbers
        """
        phone_columns = ['telefono']
        
        for col in phone_columns:
            if col in df.columns:
                # Convert to string
                df[col] = df[col].astype(str)
                # Replace 'nan' string with empty
                df[col] = df[col].replace('nan', '')
                # Remove non-numeric except + (for country code)
                df[col] = df[col].str.replace(r'[^0-9+]', '', regex=True)
                print(f"  ✅ Cleaned {col} column")
        
        return df
    
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert columns to appropriate data types.
        
        Handles:
        - Area columns → numeric, 2 decimals, fillna(0)
        - Geo columns → numeric
        - Altitude → integer
        - Number of plots → integer
        - Date columns → datetime
        - Yield columns → numeric, 2 decimals, fillna(0)
        
        Args:
            df: DataFrame to convert
            
        Returns:
            DataFrame with converted types
        """
        print("\n  Converting data types...")
        
        # 1. Area columns
        area_columns = [col for col in df.columns if 'area_' in col or 'area' in col.lower()]
        for col in area_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        
        if area_columns:
            print(f"    Converted {len(area_columns)} area columns")
        
        # 2. Geolocation columns
        geo_columns = ['longitud', 'latitud', 'x_este', 'y_norte']
        for col in geo_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        geo_found = [c for c in geo_columns if c in df.columns]
        if geo_found:
            print(f"    Converted {len(geo_found)} geo columns")
        
        # 3. Altitude (integer)
        if 'altitud' in df.columns:
            df['altitud'] = pd.to_numeric(df['altitud'], errors='coerce').fillna(0).astype(int)
            print(f"    Converted altitud to integer")
        
        # 4. Number of plots (integer)
        if 'numero_parcelas' in df.columns:
            df['numero_parcelas'] = pd.to_numeric(df['numero_parcelas'], errors='coerce').fillna(0).astype(int)
            print(f"    Converted numero_parcelas to integer")
        
        # 5. Date columns
        date_columns = [
            'fecha_ultimo_control_interno',
            'fecha_ingreso',
            'fecha_inicio_conversion'
        ]
        
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # Try dayfirst if many NaT
                if df[col].isna().mean() > 0.5:
                    df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
        
        date_found = [c for c in date_columns if c in df.columns]
        if date_found:
            print(f"    Converted {len(date_found)} date columns")
        
        # 6. Yield/harvest columns
        yield_columns = [col for col in df.columns 
                        if 'cosecha' in col or 'rendimiento_' in col or 'acopio' in col]
        
        for col in yield_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        
        if yield_columns:
            print(f"    Converted {len(yield_columns)} yield columns")
        
        # 7. Check for remaining object columns that should be numeric
        for col in df.columns:
            if df[col].dtype == 'object' and col not in ['nombre_productor', 'categoria', 
                                                          'org_code', 'country_code', 
                                                          'data_source', 'dni', 'telefono']:
                # Try to convert to numeric
                numeric_test = pd.to_numeric(df[col], errors='coerce')
                if numeric_test.notna().sum() / len(df) > 0.5:
                    df[col] = numeric_test
                    print(f"    Auto-converted {col} to numeric")
        
        return df
    
    def _check_data_quality(self, df: pd.DataFrame) -> None:
        """
        Check for potential data quality issues and print warnings.
        
        Args:
            df: DataFrame to check
        """
        print("\n  Data quality checks:")
        
        # Missing DNIs
        missing_dni = (df['dni'] == '') | (df['dni'] == 'nan')
        if missing_dni.sum() > 0:
            print(f"    ⚠️  {missing_dni.sum()} rows with missing DNI")
        
        # Extreme area values
        if 'area_total_ha' in df.columns:
            large_areas = df['area_total_ha'] > 50
            if large_areas.sum() > 0:
                print(f"    ⚠️  {large_areas.sum()} rows with area_total_ha > 50 hectares")
    
    def generate_farmer_ids(self, po_prefix: str = 'HU') -> pd.DataFrame:
        """
        Generate unique farmer IDs with deduplication.
        
        This method:
        1. Removes invalid rows (empty name or DNI)
        2. Standardizes names and DNIs
        3. Matches farmers by DNI first, then name
        4. Generates unique IDs
        
        Args:
            po_prefix: Prefix for farmer IDs (default: 'HU' for Huadquiña)
            
        Returns:
            DataFrame with added columns:
            - nombre_estandarizado
            - dni_estandarizado
            - id_global
            - producers_direct_id_productor (formatted ID)
        """
        if self.data is None:
            raise ValueError("No data to process! Run clean() first.")
        
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
    
    def save(self, output_path: str) -> None:
        """
        Save cleaned data to pickle file.
        
        Args:
            output_path: Path where cleaned data should be saved
        """
        if self.data is None:
            raise ValueError("No data to save! Run clean() first.")
        
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
        }
        
        # Add DNI statistics
        if 'dni' in self.data.columns:
            summary["unique_dni"] = self.data['dni'].nunique()
            summary["missing_dni"] = (self.data['dni'] == '').sum()
        
        # Add farmer ID stats if generated
        if 'producers_direct_id_productor' in self.data.columns:
            summary["unique_farmers"] = self.data['producers_direct_id_productor'].nunique()
        
        # Add categoria info
        if 'categoria' in self.data.columns:
            summary["categorias"] = self.data['categoria'].value_counts().to_dict()
        
        return summary


# Convenience function
def clean_huadquina_inspections(file_path: str,
                                output_path: Optional[str] = None,
                                base_path: Optional[str] = None,
                                generate_ids: bool = False) -> pd.DataFrame:
    """
    Convenience function to clean Huadquiña inspections in one call.
    
    Args:
        file_path: Path to Huadquiña template Excel file
        output_path: Optional path to save cleaned data
        base_path: Optional base directory for data files
        generate_ids: Whether to generate farmer IDs
        
    Returns:
        Cleaned DataFrame
    """
    cleaner = HuadquinaInspectionsCleaner(file_path, base_path)
    clean_data = cleaner.clean()
    
    if generate_ids:
        clean_data = cleaner.generate_farmer_ids()
    
    if output_path:
        cleaner.save(output_path)
    
    return clean_data


if __name__ == "__main__":
    print("Huadquiña Inspections Cleaner")
    print("=" * 60)
    print("\nUsage:")
    print("  cleaner = HuadquinaInspectionsCleaner('Plantilla de Inspecciones vf.xlsx')")
    print("  clean_data = cleaner.clean()")
    print("  clean_data = cleaner.generate_farmer_ids()  # Optional")
    print("  cleaner.save('huadquina_inspections_clean.pkl')")