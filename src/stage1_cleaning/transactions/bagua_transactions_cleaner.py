"""
Bagua Grande Transactions Cleaner

Processes Bagua Grande transaction (acopio) data from multiple years.
Each year is stored in a separate Excel file with sheet 'MOVIMIENTO'.

Author: Daniela
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict
from pathlib import Path

# Import utilities
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.utils import FileHandler, DNICleaner, ColumnCleaner


class BaguaTransactionsCleaner:
    """
    Clean Bagua Grande transaction (acopio) data from multiple years.
    
    Bagua stores transaction data in yearly Excel files:
    - ACOPIO 2022.xlsm
    - ACOPIO 2023.xlsm
    - ACOPIO 2024.xlsm
    
    Each file has a 'MOVIMIENTO' sheet with transaction records.
    
    Usage:
        cleaner = BaguaTransactionsCleaner([
            'BAGUA GRANDE/raw_data/ACOPIO 2022.xlsm',
            'BAGUA GRANDE/raw_data/ACOPIO 2023.xlsm',
            'BAGUA GRANDE/raw_data/ACOPIO 2024.xlsm'
        ])
        clean_data = cleaner.clean_all_years()
        cleaner.save('processed_data/bagua_transactions_clean.pkl')
    """
    
    # Sheet name where transaction data is stored
    SHEET_NAME = 'MOVIMIENTO'
    
    # Header is on row 1 (0-indexed)
    HEADER_ROW = 1
    
    # Columns to drop (administrative/unused columns)
    COLUMNS_TO_DROP = ['producto', 'salida', 'guia', 'gr', 'columna1', 'columna2']
    
    def __init__(self, file_paths: List[str], base_path: Optional[str] = None):
        """
        Initialize the Bagua transactions cleaner.
        
        Args:
            file_paths: List of paths to yearly Excel files
            base_path: Optional base directory for all data files
        """
        self.file_paths = file_paths
        
        # Initialize utilities
        self.file_handler = FileHandler(base_path=base_path)
        self.dni_cleaner = DNICleaner(verbose=True)
        self.col_cleaner = ColumnCleaner()
        
        # Storage for cleaned data
        self.data = None
        self.yearly_data = {}  # Store each year separately if needed
    
    def clean_all_years(self) -> pd.DataFrame:
        """
        Clean all yearly files and combine them.
        
        This is the main entry point for cleaning Bagua transactions.
        
        Returns:
            Combined DataFrame with all years' transaction data
        """
        print("\n" + "=" * 60)
        print("CLEANING BAGUA GRANDE TRANSACTIONS")
        print("=" * 60)
        
        yearly_dfs = []
        
        for file_path in self.file_paths:
            # Extract year from filename (e.g., 'ACOPIO 2024.xlsm' → 2024)
            year = self._extract_year_from_filename(file_path)
            
            print(f"\nCleaning {year} transactions...")
            df = self._clean_single_year(file_path, year)
            
            self.yearly_data[year] = df
            yearly_dfs.append(df)
            
            print(f"  ✅ {year}: {len(df)} transactions")
        
        # Combine all years
        print("\nCombining all years...")
        self.data = pd.concat(yearly_dfs, ignore_index=True)
        
        # Final cleaning steps
        self.data = self._final_cleaning(self.data)
        
        print(f"\n✅ Bagua transactions cleaning complete!")
        print(f"   Total transactions: {len(self.data)}")
        print(f"   Years: {sorted(self.yearly_data.keys())}")
        
        return self.data
    
    def _clean_single_year(self, file_path: str, year: int) -> pd.DataFrame:
        """Clean a single year's transaction file."""
        
        # 1. Read Excel file
        df = self.file_handler.read_excel_simple(
            file_path=file_path,
            sheet_name=self.SHEET_NAME,
            header=self.HEADER_ROW,
            remove_total=True
        )
        
        # 2. Lowercase all column names immediately
        df.columns = df.columns.str.lower()
        
        # 3. Rename columns to standard names (DO THIS FIRST!)
        df = self._rename_columns(df, year)
        
        # 4. Year-specific fixes (now we can use renamed columns!)
        if year == 2022:
            # Drop first empty row
            df = df.iloc[1:].reset_index(drop=True)
            print(f"  Removed first empty row from 2022 data")
        
        elif year == 2023:
            # Fix campaign year
            df['campania'] = 2023  # ← Use renamed column name!
            print(f"  Set campania to 2023")
        
        elif year == 2024:
            # Remove rows where fecha is null
            if 'fecha' in df.columns:
                original_len = len(df)
                df = df[df['fecha'].notna()].copy()
                removed = original_len - len(df)
                if removed > 0:
                    print(f"  Removed {removed} rows with null fecha")
        
        # 5. Drop unwanted columns
        cols_to_drop = [col for col in self.COLUMNS_TO_DROP if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            print(f"  Dropped {len(cols_to_drop)} administrative columns")
        
        # 6. Add metadata
        df['org_code'] = 'BG'
        df['country_code'] = 'PER'
        df['product_code'] = 'COFFEE'
        df['data_source'] = f'{Path(file_path).name} - {self.SHEET_NAME}'
        
        return df
    
    def _rename_columns(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Rename columns to standard names.
        
        Each year has slightly different column names, so we standardize them.
        
        Args:
            df: DataFrame with original column names
            year: Year being processed
            
        Returns:
            DataFrame with renamed columns
        """
        # Common renames for all years
        rename_map = {
            'socio': 'nombre_productor',
            'programa': 'categoria',
            'codigo': 'campania',
            'ingreso': 'kg',
            'precio': 'precio_qq',
            'prec. total': 'total_soles',
            'rdto.': 'rendimiento'
        }
        
        # Year-specific renames
        if year == 2022:
            rename_map['cobace'] = 'base'
        elif year == 2023:
            rename_map['cobace'] = 'base'
        elif year == 2024:
            rename_map['cobase'] = 'base'
            
            # Find ANY date-like column (not hardcoded!)
            # Looks for pattern: number/number/number
            import re
            for col in df.columns:
                if re.match(r'\d{1,2}/\d{1,2}/\d{4}', str(col)):
                    rename_map[col] = 'fecha'
                    print(f"  Found date column: '{col}' → 'fecha'")
                    break
        
        # Apply renames (only for columns that exist)
        existing_renames = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=existing_renames)
        
        if existing_renames:
            print(f"  Renamed {len(existing_renames)} columns")
        
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
        
        # 1. Clean DNI if it exists
        if 'dni' in df.columns:
            df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='dni')
        else:
            print("  ℹ️  No DNI column found in transaction data")
        
        # 2. Clean all column names (standardize format)
        df = self.col_cleaner.clean(df)
        
        # 3. Convert campania to string (from your notebook)
        if 'campania' in df.columns:
            df['campania'] = df['campania'].astype(str)
            print("  Converted campania to string")
        
        # 4. Parse dates if fecha exists
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            null_dates = df['fecha'].isna().sum()
            if null_dates > 0:
                print(f"  ⚠️  {null_dates} transactions have invalid dates")
        
        return df
    
    def _extract_year_from_filename(self, file_path: str) -> int:
        """
        Extract year from filename.
        
        Examples:
            'ACOPIO 2024.xlsm' → 2024
            'BAGUA/raw_data/ACOPIO 2023.xlsm' → 2023
        
        Args:
            file_path: Path to file
            
        Returns:
            Year as integer
        """
        filename = Path(file_path).name
        
        # Look for 4-digit year in filename
        import re
        match = re.search(r'20\d{2}', filename)
        
        if match:
            return int(match.group())
        else:
            print(f"  ⚠️  Could not extract year from '{filename}', using 0000")
            return 0
    
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
                "No data to save! Run clean_all_years() first."
            )
        
        # Delegate to FileHandler
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
            "years": sorted(self.yearly_data.keys()),
        }
        
        # Add per-year counts
        for year, df in self.yearly_data.items():
            summary[f"year_{year}_count"] = len(df)
        
        # Add DNI statistics if available
        if 'dni' in self.data.columns:
            summary["unique_farmers"] = self.data['dni'].nunique()
            summary["missing_dni"] = (self.data['dni'] == '').sum()
        
        # Add date range if available
        if 'fecha' in self.data.columns:
            valid_dates = self.data['fecha'].dropna()
            if len(valid_dates) > 0:
                summary["date_range"] = f"{valid_dates.min()} to {valid_dates.max()}"
        
        return summary


# Convenience function
def clean_bagua_transactions(file_paths: List[str],
                             output_path: Optional[str] = None,
                             base_path: Optional[str] = None) -> pd.DataFrame:
    """
    Convenience function to clean Bagua transactions in one call.
    
    Args:
        file_paths: List of paths to yearly Excel files
        output_path: Optional path to save cleaned data
        base_path: Optional base directory for data files
        
    Returns:
        Cleaned DataFrame
        
    Example:
        clean_df = clean_bagua_transactions(
            ['ACOPIO 2022.xlsm', 'ACOPIO 2023.xlsm', 'ACOPIO 2024.xlsm'],
            'processed_data/bagua_transactions_clean.pkl'
        )
    """
    cleaner = BaguaTransactionsCleaner(file_paths, base_path)
    clean_data = cleaner.clean_all_years()
    
    if output_path:
        cleaner.save(output_path)
    
    return clean_data


if __name__ == "__main__":
    # Example usage
    print("Bagua Transactions Cleaner")
    print("=" * 60)
    print("\nUsage:")
    print("  from src.stage1_cleaning.transactions import BaguaTransactionsCleaner")
    print("  ")
    print("  cleaner = BaguaTransactionsCleaner([")
    print("      'raw_data/ACOPIO 2022.xlsm',")
    print("      'raw_data/ACOPIO 2023.xlsm',")
    print("      'raw_data/ACOPIO 2024.xlsm'")
    print("  ])")
    print("  clean_data = cleaner.clean_all_years()")
    print("  cleaner.save('processed_data/bagua_transactions_clean.pkl')")












