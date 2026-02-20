"""
DNI Cleaner Utility

Standardizes DNI (Documento Nacional de Identidad) values across all datasets.
Handles various input formats and converts them to a consistent 8-digit string format.

Author: Daniela
"""

import pandas as pd
from typing import Any, Union


class DNICleaner:
    """
    Cleans and standardizes DNI values from various formats.
    
    Handles:
    - Floats (33657779.0 → '33657779')
    - Strings with leading apostrophes ("'33657779" → '33657779')
    - Numbers needing padding (1234567 → '01234567')
    - NaN/empty values (→ '')
    - Invalid formats
    
    Usage:
        cleaner = DNICleaner()
        df['dni_clean'] = cleaner.clean(df['DNI'])
    """
    
    def __init__(self, verbose: bool = True):
        """
        Initialize the DNI cleaner.
        
        Args:
            verbose: Whether to print cleaning statistics
        """
        self.verbose = verbose
    
    def clean(self, dni_series: pd.Series, column_name: str = 'dni') -> pd.Series:
        """
        Clean a pandas Series of DNI values.
        
        Args:
            dni_series: Pandas Series containing DNI values in various formats
            column_name: Name of the column (for logging purposes)
            
        Returns:
            Pandas Series with cleaned DNI values as strings
            
        Example:
            Input:  [33657779.0, "'43196560", 1234567, nan, ""]
            Output: ['33657779', '43196560', '01234567', '', '']
        """
        original_count = len(dni_series)
        cleaned = dni_series.apply(self._clean_single_dni)
        
        # Log statistics if verbose
        if self.verbose:
            valid_count = (cleaned != '').sum()
            missing_count = original_count - valid_count
            print(f"  ✅ Cleaned {column_name}: {valid_count:,} valid DNIs, {missing_count:,} missing")
        
        return cleaned
    
    def _clean_single_dni(self, dni: Any) -> str:
        """
        Clean a single DNI value.
        
        Logic (from notebook):
        1. Handle NaN/empty → ''
        2. Convert to int (handles floats like 33657779.0)
        3. Remove leading apostrophes
        4. Keep only digits
        5. Pad to 8 digits with leading zeros
        
        Args:
            dni: Single DNI value (can be str, int, float, or NaN)
            
        Returns:
            Cleaned DNI as 8-digit string, or empty string if invalid
        """
        # Handle NaN and empty values
        if pd.isna(dni) or dni == '':
            return ''
        
        try:
            # Try to convert to int first (handles floats and numeric strings)
            dni_int = int(float(dni))
            dni_str = str(dni_int)
        except (ValueError, TypeError):
            # If conversion fails, treat as string and clean
            dni_str = str(dni).lstrip("'").strip()
            # Keep only digits
            dni_str = ''.join(filter(str.isdigit, dni_str))
        
        # If we got an empty string after cleaning, return empty
        if not dni_str:
            return ''
        
        # Pad to 8 digits with leading zeros
        return dni_str.zfill(8)
    
    def validate(self, dni: str) -> bool:
        """
        Check if a DNI is valid.
        
        Valid DNI:
        - Exactly 8 digits
        - All numeric characters
        - Not empty
        
        Args:
            dni: DNI string to validate
            
        Returns:
            True if valid, False otherwise
            
        Example:
            validate('33657779')  → True
            validate('123')       → False (too short)
            validate('abc12345')  → False (contains letters)
        """
        if not dni or not isinstance(dni, str):
            return False
        
        return len(dni) == 8 and dni.isdigit()
    
    def get_invalid_count(self, dni_series: pd.Series) -> int:
        """
        Count how many invalid DNIs are in a Series.
        
        Useful for data quality checks.
        
        Args:
            dni_series: Series of cleaned DNI values
            
        Returns:
            Count of invalid DNIs (empty or non-conformant)
        """
        return (dni_series == '').sum() + (~dni_series.apply(self.validate)).sum()
    
    def find_invalid(self, df: pd.DataFrame, dni_column: str = 'dni') -> pd.DataFrame:
        """
        Find rows with invalid or missing DNIs.
        
        Args:
            df: DataFrame to check
            dni_column: Name of DNI column
            
        Returns:
            DataFrame with rows that have invalid DNIs
            
        Example:
            invalid_rows = cleaner.find_invalid(df)
            print(f"Found {len(invalid_rows)} invalid DNIs")
        """
        if dni_column not in df.columns:
            print(f"⚠️  Column '{dni_column}' not found in dataframe")
            return pd.DataFrame()
        
        # Find invalid DNIs
        invalid_mask = ~df[dni_column].apply(self.validate)
        invalid_rows = df[invalid_mask].copy()
        
        if self.verbose and len(invalid_rows) > 0:
            print(f"⚠️  Found {len(invalid_rows)} rows with invalid/missing DNIs")
        
        return invalid_rows
    
    def get_statistics(self, dni_series: pd.Series) -> dict:
        """
        Get statistics about DNI values in a Series.
        
        Args:
            dni_series: Series of cleaned DNI values
            
        Returns:
            Dictionary with statistics (total, valid, missing, invalid)
        """
        total = len(dni_series)
        valid = dni_series.apply(self.validate).sum()
        empty = (dni_series == '').sum()
        invalid = total - valid - empty
        
        return {
            'total': total,
            'valid': valid,
            'missing': empty,
            'invalid': invalid,
            'valid_pct': (valid / total * 100) if total > 0 else 0
        }


# Convenience function for quick cleaning
def clean_dni_column(df: pd.DataFrame, column_name: str, 
                     new_column_name: str = None, verbose: bool = True) -> pd.DataFrame:
    """
    Convenience function to clean a DNI column in a DataFrame.
    
    Args:
        df: DataFrame containing DNI column
        column_name: Name of the column to clean
        new_column_name: Name for the cleaned column (if None, replaces original)
        verbose: Whether to print cleaning statistics
        
    Returns:
        DataFrame with cleaned DNI column
        
    Example:
        df = clean_dni_column(df, 'DNI', 'dni_clean')
    """
    cleaner = DNICleaner(verbose=verbose)
    
    if new_column_name is None:
        new_column_name = column_name
    
    df[new_column_name] = cleaner.clean(df[column_name], column_name=column_name)
    
    return df