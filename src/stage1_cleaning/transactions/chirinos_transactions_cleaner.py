"""
Chirinos Transactions Cleaner

Processes Chirinos transaction data from yearly Excel files (2020-2024+).
Handles year-specific column structure differences and combines all years.

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


class ChirinosTransactionsCleaner:
    """
    Clean Chirinos transaction data from multiple yearly files.
    
    Chirinos provides yearly Excel files with transaction data.
    Each year may have slight structural differences that need handling.
    
    Key features:
    - Handles 2020-2024 with year-specific column adjustments
    - Removes total rows automatically
    - Drops administrative columns
    - Future-proof for new years
    
    Usage:
        cleaner = ChirinosTransactionsCleaner([
            'data/raw/transactions/chirinos/ACOPIO 2020.xlsx',
            'data/raw/transactions/chirinos/ACOPIO 2021.xlsx',
            ...
        ])
        clean_data = cleaner.clean_all_years()
        cleaner.save('processed_data/chirinos_transactions_clean.pkl')
    """
    
    # Sheet name used in all Chirinos files
    SHEET_NAME = 'Sheet1'
    
    # Administrative columns to drop (from your notebook)
    # NOTE: These match the lowercased column names (with spaces, not underscores)
    ADMIN_COLUMNS = [
        'base sectorial', 'nº ticket', 'fec. co', 'doc',
        'serie', 'número', '% d', '% c', 'p. prima', 'p. total',
        't. prima s/.', 'propio', 'tipo', 'sellos', 'almacén',
        'parcela', 'sac.'
    ]
    
    def __init__(self, file_paths: List[str], base_path: Optional[str] = None):
        """
        Initialize the Chirinos transactions cleaner.
        
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
        self.year_data = {}
    
    def clean_all_years(self) -> pd.DataFrame:
        """
        Clean all yearly transaction files and combine them.
        
        Returns:
            Combined DataFrame with all years' transactions
        """
        print("\n" + "=" * 60)
        print("CLEANING CHIRINOS TRANSACTIONS")
        print("=" * 60)
        
        all_years = []
        
        for file_path in self.file_paths:
            # Extract year from filename
            year = self._extract_year_from_filename(file_path)
            
            print(f"\nCleaning {year} transactions...")
            
            # Read the file
            df = self.file_handler.read_excel_simple(
                file_path=file_path,
                sheet_name=self.SHEET_NAME,
                header=0,
                remove_total=False
            )
            
            print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
            
            # Clean this year's data
            df = self._clean_single_year(df, year)
            
            # Store for reference
            self.year_data[year] = df
            all_years.append(df)
            
            print(f"  ✅ {year}: {len(df)} transactions")
        
        # Combine all years
        print(f"\nCombining all years...")
        combined_df = pd.concat(all_years, ignore_index=True)
        
        # Apply final cleaning
        combined_df = self._final_cleaning(combined_df)
        
        print(f"\n✅ Chirinos transactions cleaning complete!")
        print(f"   Total transactions: {len(combined_df)}")
        print(f"   Years: {sorted(self.year_data.keys())}")
        
        # Store final data
        self.data = combined_df
        
        return combined_df
    
    def _clean_single_year(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Clean a single year's transaction data.
        
        Args:
            df: DataFrame for one year
            year: Year being processed
            
        Returns:
            Cleaned DataFrame for that year
        """
        # 1. Remove last row (total row)
        df = self._remove_total_row(df)
        
        # 2. Handle year-specific column structure
        df = self._handle_year_specific_columns(df, year)
        
        # 3. Add campania column
        df['campania'] = year
        print(f"  Added campania: {year}")
        
        return df
    
    def _remove_total_row(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove the last row if it's a total row.
        
        Chirinos files have a "Totales:" row at the end with sum totals.
        We detect this by checking if the first column contains "totales".
        
        Args:
            df: DataFrame potentially with total row
            
        Returns:
            DataFrame without total row
        """
        if len(df) == 0:
            return df
        
        # Check if last row is a total row
        last_row = df.iloc[-1]
        
        # Get first few values and check for "totales" (case insensitive)
        first_vals = last_row.iloc[:3].astype(str)
        is_total = any('totales' in str(val).lower() for val in first_vals)
        
        if is_total:
            df = df.iloc[:-1].copy()
            print(f"  Removed last row (detected 'Totales:' row)")
        else:
            print(f"  No total row detected, keeping all data")
        
        return df
    
    def _handle_year_specific_columns(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Handle column structure differences between years.
        
        2024: Has 'Total S/.' column already
        2020-2023: Need to rename 'Estatus' → 'Total S/.', 'Sellos' → 'Estatus'
        
        Args:
            df: DataFrame with original columns
            year: Year being processed
            
        Returns:
            DataFrame with adjusted columns
        """
        if year <= 2023:
            # Older years need column adjustment
            if 'Total S/.' in df.columns:
                # Drop if exists
                df = df.drop(columns=['Total S/.'])
                print(f"  Dropped 'Total S/.' column")
            
            # Rename columns
            rename_map = {
                'Estatus': 'Total S/.',
                'Sellos': 'Estatus'
            }
            
            existing_renames = {k: v for k, v in rename_map.items() if k in df.columns}
            if existing_renames:
                df = df.rename(columns=existing_renames)
                print(f"  Renamed columns for {year}: {list(existing_renames.keys())}")
        
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
        
        # 1. Lowercase columns FIRST
        df.columns = df.columns.str.lower()
        print(f"  Converted column names to lowercase")
        
        # 2. Drop admin columns (now they match!)
        df = self._drop_administrative_columns(df)
        
        
        # 3. Add metadata
        df['org_code'] = 'CH'
        df['country_code'] = 'PER'
        df['product_code'] = 'COFFEE'
        
        # Build data source string
        years = sorted([self._extract_year_from_filename(fp) for fp in self.file_paths])
        data_source = f"Chirinos ACOPIO files: {', '.join(map(str, years))}"
        df['data_source'] = data_source
        
        print(f"  Added metadata columns")
        
        # 4. Rename columns to standard names
        df = self._rename_to_standard(df)
        
        # 5. Clean DNI if it exists
        if 'dni' in df.columns:
            df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='dni')
        
        # 6. Convert data types
        df = self._convert_data_types(df)
        
        # 7. Drop any unnamed columns
        unnamed_cols = [col for col in df.columns if col.startswith('unnamed')]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols)
            print(f"  Dropped {len(unnamed_cols)} unnamed (empty) columns")
        
        return df
    
    def _drop_administrative_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Drop administrative columns that aren't needed for analysis.
        
        NOTE: Columns are already lowercased when this runs.
        
        Args:
            df: DataFrame with all columns
            
        Returns:
            DataFrame without administrative columns
        """
        # Find columns to drop (columns are already lowercased)
        cols_to_drop = [col for col in self.ADMIN_COLUMNS if col in df.columns]
        
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            print(f"  Dropped {len(cols_to_drop)} administrative columns")
        
        return df
    
    def _rename_to_standard(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename columns to standard names used across all POs.
        
        NOTE: This runs AFTER lowercasing, so we match the lowercased names
        which have SPACES (e.g., 'fec. tk'), not underscores.
        
        Args:
            df: DataFrame with original column names
            
        Returns:
            DataFrame with standardized column names
        """
        # Standard renames (from your notebook)
        # These match the LOWERCASED column names (with spaces)
        rename_map = {
            'nombre': 'nombre_productor',
            'fec. tk': 'fecha',
            'kg.': 'kg',
            'qq.': 'qq',
            '% r': 'rendimiento',
            'hum': 'porcentaje_humedad',
            'kg h.': 'kg_ha',
            'prec. kg': 'precio_kg',
            'prec. qq': 'precio_qq',
            'total s/.': 'total_soles',
            'estatus': 'categoria'
        }
        
        # Apply renames (only for columns that exist)
        existing_renames = {k: v for k, v in rename_map.items() if k in df.columns}
        
        if existing_renames:
            df = df.rename(columns=existing_renames)
            print(f"  Renamed {len(existing_renames)} columns to standard names")
        
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
        
        # 1. Convert campania to string (categorical, not numeric)
        if 'campania' in df.columns:
            df['campania'] = df['campania'].astype(str)
            print("    Converted campania to string")
        
        # 2. Convert date column if exists
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            null_dates = df['fecha'].isna().sum()
            if null_dates > 0:
                print(f"    ⚠️  {null_dates} transactions have invalid dates")
        
        # 3. Convert numeric columns
        numeric_cols = ['kg', 'qq', 'rendimiento', 'porcentaje_humedad', 
                       'kg_ha', 'precio_kg', 'precio_qq', 'total_soles']
        
        converted = 0
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                converted += 1
        
        if converted > 0:
            print(f"    Converted {converted} numeric columns")
        
        return df
    
    def _extract_year_from_filename(self, file_path: str) -> int:
        """
        Extract year from filename.
        
        Args:
            file_path: Path to the file
            
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
            raise ValueError(f"Could not extract year from filename: {filename}")
    
    def save(self, output_path: str) -> None:
        """
        Save cleaned data to pickle file.
        
        Args:
            output_path: Path where cleaned data should be saved
        """
        if self.data is None:
            raise ValueError("No data to save! Run clean_all_years() first.")
        
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
            "years": sorted(self.year_data.keys())
        }
        
        # Add year counts
        for year, df in self.year_data.items():
            summary[f'year_{year}_count'] = len(df)
        
        # Add date range if available
        if 'fecha' in self.data.columns:
            dates = self.data['fecha'].dropna()
            if len(dates) > 0:
                summary['date_range'] = f"{dates.min()} to {dates.max()}"
        
        # Add unique farmers if nombre_productor exists
        if 'nombre_productor' in self.data.columns:
            summary['unique_farmers'] = self.data['nombre_productor'].nunique()
        
        return summary


# Convenience function
def clean_chirinos_transactions(file_paths: List[str],
                                output_path: Optional[str] = None,
                                base_path: Optional[str] = None) -> pd.DataFrame:
    """
    Convenience function to clean Chirinos transactions in one call.
    
    Args:
        file_paths: List of paths to yearly Excel files
        output_path: Optional path to save cleaned data
        base_path: Optional base directory for data files
        
    Returns:
        Cleaned DataFrame
    """
    cleaner = ChirinosTransactionsCleaner(file_paths, base_path)
    clean_data = cleaner.clean_all_years()
    
    if output_path:
        cleaner.save(output_path)
    
    return clean_data


if __name__ == "__main__":
    print("Chirinos Transactions Cleaner")
    print("=" * 60)
    print("\nUsage:")
    print("  cleaner = ChirinosTransactionsCleaner([")
    print("      'data/raw/transactions/chirinos/ACOPIO 2020.xlsx',")
    print("      'data/raw/transactions/chirinos/ACOPIO 2021.xlsx',")
    print("      ...])")
    print("  clean_data = cleaner.clean_all_years()")
    print("  cleaner.save('chirinos_transactions_clean.pkl')")