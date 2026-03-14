"""
Huadquiña Transactions Cleaner

Processes Huadquiña transaction data from their standardized template.
Unlike Bagua, Huadquiña uses a single template file (not yearly files).

Author: Daniela
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict
from pathlib import Path

# Import utilities
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.utils import FileHandler, ColumnCleaner


class HuadquinaTransactionsCleaner:
    """
    Clean Huadquiña transaction data from their acopio template.
    
    Huadquiña uses a standardized Excel template with a single sheet.
    This is simpler than Bagua's multi-year approach.
    
    Usage:
        cleaner = HuadquinaTransactionsCleaner('raw_data/Plantilla de Acopio vf.xlsx')
        clean_data = cleaner.clean()
        cleaner.save('processed_data/huadquina_transactions_clean.pkl')
    """
    
    # Sheet name in the template
    SHEET_NAME = 'Plantilla Acopio'
    
    # Column renaming map
    COLUMN_RENAMES = {
        'fecha_transaccion': 'fecha',
        'campaña': 'campania',
        'cantidad_kgs': 'kg',
        'cantidad_qq': 'qq',
        'qq_despues_de_humedad': 'qq_porcentaje_humedad',
        'calidad_taza': 'taza_rango',
        'monto_total_soles': 'total_soles'
    }
    
    def __init__(self, file_path: str, base_path: Optional[str] = None):
        """
        Initialize the Huadquiña transactions cleaner.
        
        Args:
            file_path: Path to the Huadquiña template Excel file
            base_path: Optional base directory for all data files
        """
        self.file_path = file_path
        
        # Initialize utilities
        self.file_handler = FileHandler(base_path=base_path)
        self.col_cleaner = ColumnCleaner()
        
        # Storage for cleaned data
        self.data = None
    
    def clean(self) -> pd.DataFrame:
        """
        Clean the Huadquiña transactions data.
        
        This is the main entry point.
        
        Returns:
            Cleaned DataFrame with transaction data
        """
        print("\n" + "=" * 60)
        print("CLEANING HUADQUIÑA TRANSACTIONS")
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
        
        # 2. Clean DNI (Huadquiña-specific logic)
        if 'dni' in df.columns:
            df['dni'] = df['dni'].apply(self._clean_dni)
            print(f"  ✅ Cleaned DNI column")
        else:
            print(f"  ⚠️  No DNI column found")
        
        # 3. Rename columns 
        df = df.rename(columns=self.COLUMN_RENAMES)
        renamed_count = len([k for k in self.COLUMN_RENAMES.keys() if k in df.columns])
        if renamed_count > 0:
            print(f"  Renamed {renamed_count} columns")

        
        # 4. Add metadata
        df['org_code'] = 'HU'
        df['country_code'] = 'PER'
        df['product_code'] = 'COFFEE'
        df['data_source'] = f'{Path(self.file_path).name} - {self.SHEET_NAME}'
        print(f"  Added metadata columns")
        
        # 5. Final column cleaning
        df = self.col_cleaner.clean(df)
        
        # 6. Data type conversions
        df = self._convert_data_types(df)
        
        # Store cleaned data
        self.data = df
        
        print(f"\n✅ Huadquiña transactions cleaning complete!")
        print(f"   Total transactions: {len(df)}")
        
        return df
    
    def _clean_dni(self, dni) -> str:
        """
        Clean DNI using Huadquiña-specific logic.
        
        Huadquiña DNI cleaning is different from standard DNICleaner:
        - If >8 digits: Extract middle 8 digits (positions 2-10)
        - If <8 digits: Pad with zeros
        - If 8 digits: Keep as is
        
        Args:
            dni: Raw DNI value
            
        Returns:
            Cleaned 8-digit DNI string
        """
        # Convert to string and remove whitespace
        dni = str(dni).strip()
        
        # Handle NaN
        if dni == 'nan' or dni == '':
            return ''
        
        # Remove any non-digit characters
        dni = ''.join(c for c in dni if c.isdigit())
        
        if len(dni) > 8:
            # Extract middle 8 digits (positions 2-10)
            return dni[2:10]
        elif len(dni) < 8:
            # Pad with zeros
            return dni.zfill(8)
        else:
            # Already 8 digits
            return dni
    
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert columns to appropriate data types.
        
        Args:
            df: DataFrame to convert
            
        Returns:
            DataFrame with converted types
        """
        print("\n  Converting data types...")
        
        # Convert fecha to datetime
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            null_dates = df['fecha'].isna().sum()
            if null_dates > 0:
                print(f"    ⚠️  {null_dates} transactions have invalid dates")
        
        # Convert campania to string
        if 'campania' in df.columns:
            df['campania'] = df['campania'].astype(str)
            print(f"    Converted campania to string")
        
        # Convert numeric columns
        numeric_cols = ['kg', 'qq', 'precio_kg', 'precio_qq', 'porcentaje_humedad', 
                       'qq_porcentaje_humedad', 'rendimiento', 'total_soles']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        converted = [c for c in numeric_cols if c in df.columns]
        if converted:
            print(f"    Converted {len(converted)} numeric columns")
        
        return df
    
    def save(self, output_path: str) -> None:
        """
        Save cleaned data to pickle file.
        
        Args:
            output_path: Path where cleaned data should be saved
            
        Raises:
            ValueError: If no data has been cleaned yet
        """
        if self.data is None:
            raise ValueError(
                "No data to save! Run clean() first."
            )
        
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
            "total_transactions": len(self.data),
            "total_columns": len(self.data.columns),
        }
        
        # Add DNI statistics if available
        if 'dni' in self.data.columns:
            summary["unique_farmers"] = self.data['dni'].nunique()
            summary["missing_dni"] = (self.data['dni'] == '').sum()
        
        # Add date range if available
        if 'fecha' in self.data.columns:
            valid_dates = self.data['fecha'].dropna()
            if len(valid_dates) > 0:
                summary["date_range"] = f"{valid_dates.min()} to {valid_dates.max()}"
        
        # Add campaign info
        if 'campania' in self.data.columns:
            summary["campaigns"] = sorted(self.data['campania'].unique().tolist())
        
        return summary
    
# Convenience function
def clean_huadquina_transactions(file_path: str,
                                 output_path: Optional[str] = None,
                                 base_path: Optional[str] = None) -> pd.DataFrame:
    """
    Convenience function to clean Huadquiña transactions in one call.
    
    Args:
        file_path: Path to Huadquiña template Excel file
        output_path: Optional path to save cleaned data
        base_path: Optional base directory for data files
        
    Returns:
        Cleaned DataFrame
        
    Example:
        clean_df = clean_huadquina_transactions(
            'raw_data/Plantilla de Acopio vf.xlsx',
            'processed_data/huadquina_transactions_clean.pkl'
        )
    """
    cleaner = HuadquinaTransactionsCleaner(file_path, base_path)
    clean_data = cleaner.clean()
    
    if output_path:
        cleaner.save(output_path)
    
    return clean_data


if __name__ == "__main__":
    print("Huadquiña Transactions Cleaner")
    print("=" * 60)
    print("\nUsage:")
    print("  from src.stage1_cleaning.transactions import HuadquinaTransactionsCleaner")
    print("  ")
    print("  cleaner = HuadquinaTransactionsCleaner('raw_data/Plantilla de Acopio vf.xlsx')")
    print("  clean_data = cleaner.clean()")
    print("  cleaner.save('processed_data/huadquina_transactions_clean.pkl')")