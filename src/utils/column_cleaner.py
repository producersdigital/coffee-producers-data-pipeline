"""
Column Cleaner Utility

Standardizes column names across all datasets by applying consistent transformations.
Removes special characters, converts to lowercase, and uses underscores.

Author: Daniela
"""

import pandas as pd
import re
from typing import List


class ColumnCleaner:
    """
    Cleans and standardizes column names in DataFrames.
    
    Transformations:
    - Convert to lowercase
    - Strip whitespace
    - Replace spaces with underscores
    - Remove special characters: . º ñ→n ( ) / \ - etc.
    - Remove accented characters
    
    Usage:
        cleaner = ColumnCleaner()
        df_clean = cleaner.clean(df)
    """
    
    def __init__(self):
        """Initialize the column cleaner."""
        pass
    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean all column names in a DataFrame.
        
        Args:
            df: DataFrame with columns to clean
            
        Returns:
            DataFrame with cleaned column names
            
        Example:
            Input columns:  ['Nombre productor(a)', 'Dirección (Zona)', 'Nº', 'Cosecha/Acopio']
            Output columns: ['nombre_productor', 'direccion_zona', 'n', 'cosecha_acopio']
        """
        df_clean = df.copy()
        df_clean.columns = [self._clean_single_column(col) for col in df_clean.columns]
        return df_clean
    
    def _clean_single_column(self, column_name: str) -> str:
        """
        Clean a single column name.
        
        Steps (from notebook):
        1. Convert to lowercase
        2. Strip whitespace
        3. Replace spaces with underscores
        4. Remove/replace special characters
        
        Args:
            column_name: Original column name
            
        Returns:
            Cleaned column name
        """
        if not isinstance(column_name, str):
            column_name = str(column_name)
        
        # Start with the transformations from the notebook
        cleaned = column_name.lower().strip()
        
        # Replace spaces with underscores
        cleaned = cleaned.replace(' ', '_')
        
        # Remove/replace special characters (from notebook logic)
        cleaned = cleaned.replace('.', '')
        cleaned = cleaned.replace('º', '')
        cleaned = cleaned.replace('ñ', 'n')
        cleaned = cleaned.replace('(', '')
        cleaned = cleaned.replace(')', '')
        cleaned = cleaned.replace('/', '_')
        cleaned = cleaned.replace('\\', '_')
        cleaned = cleaned.replace('-', '_')
        cleaned = cleaned.replace(',', '')
        cleaned = cleaned.replace(':', '')
        cleaned = cleaned.replace(';', '')
        cleaned = cleaned.replace('?', '')
        cleaned = cleaned.replace('¿', '')
        cleaned = cleaned.replace('!', '')
        cleaned = cleaned.replace('¡', '')
        
        # Remove accented characters
        cleaned = self._remove_accents(cleaned)
        
        # Replace multiple underscores with single underscore
        cleaned = re.sub(r'_+', '_', cleaned)
        
        # Remove leading/trailing underscores
        cleaned = cleaned.strip('_')
        
        # If we end up with empty string, use a default
        if not cleaned:
            cleaned = 'unnamed_column'
        
        return cleaned
    
    def _remove_accents(self, text: str) -> str:
        """
        Remove accented characters and convert to ASCII equivalents.
        
        Examples:
            á → a, é → e, í → i, ó → o, ú → u
            
        Args:
            text: String with potential accented characters
            
        Returns:
            String with accents removed
        """
        accent_map = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
            'ã': 'a', 'õ': 'o',
            'ç': 'c',
            'ñ': 'n'
        }
        
        for accented, replacement in accent_map.items():
            text = text.replace(accented, replacement)
        
        return text
    
    def preview_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preview what column names will become after cleaning.
        
        Useful for checking transformations before applying.
        
        Args:
            df: DataFrame to preview
            
        Returns:
            DataFrame with 'original' and 'cleaned' columns showing the mapping
            
        Example:
            preview = cleaner.preview_changes(df)
            print(preview)
        """
        preview = pd.DataFrame({
            'original': df.columns,
            'cleaned': [self._clean_single_column(col) for col in df.columns]
        })
        
        # Highlight any duplicates that might be created
        duplicates = preview['cleaned'].duplicated(keep=False)
        if duplicates.any():
            preview['has_duplicate'] = duplicates
        
        return preview


# Convenience function
def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to clean column names.
    
    Args:
        df: DataFrame with columns to clean
        
    Returns:
        DataFrame with cleaned column names
        
    Example:
        df = clean_column_names(df)
    """
    cleaner = ColumnCleaner()
    return cleaner.clean(df)












