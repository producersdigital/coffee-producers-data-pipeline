"""
DNI (National ID) Cleaning Utilities

Standardizes national ID formats from different Producer Organizations.
DNIs should be 8-digit strings with leading zeros preserved.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional


def clean_dni(dni: Union[str, int, float]) -> str:
    """
    Clean and standardize a single DNI value.
    
    Args:
        dni: DNI value (can be string, int, or float)
    
    Returns:
        str: Standardized 8-digit DNI string, or empty string if invalid
    
    Examples:
        >>> clean_dni(12345678)
        '12345678'
        >>> clean_dni(1234567.0)
        '01234567'
        >>> clean_dni('  12345  ')
        '00012345'
        >>> clean_dni("'12345678")
        '12345678'
        >>> clean_dni(None)
        ''
    """
    # Handle None, NaN, or empty values
    if pd.isna(dni) or dni == '' or dni is None:
        return ''
    
    try:
        # Try converting to int first (handles both float and string floats)
        if isinstance(dni, (int, float)):
            dni_int = int(dni)
            dni_str = str(dni_int)
        else:
            # Handle string cases
            dni_str = str(dni).strip()
            
            # Remove leading apostrophe if present (Excel formatting)
            dni_str = dni_str.lstrip("'")
            
            # Remove any non-digit characters
            dni_str = ''.join(filter(str.isdigit, dni_str))
            
            # If empty after cleaning, return empty string
            if not dni_str:
                return ''
        
        # Pad to 8 digits with leading zeros
        return dni_str.zfill(8)
        
    except (ValueError, TypeError):
        # If all conversion attempts fail, return empty string
        return ''


def clean_dni_series(dni_series: pd.Series, column_name: str = 'dni') -> pd.Series:
    """
    Clean an entire pandas Series of DNI values.
    
    Args:
        dni_series: Pandas Series containing DNI values
        column_name: Name of the column (for logging)
    
    Returns:
        pd.Series: Cleaned DNI series
    
    Example:
        >>> df['dni'] = clean_dni_series(df['dni'])
    """
    original_count = len(dni_series)
    
    # Apply cleaning function to entire series
    cleaned = dni_series.apply(clean_dni)
    
    # Count valid DNIs (non-empty)
    valid_count = (cleaned != '').sum()
    missing_count = original_count - valid_count
    
    print(f"  ✅ Cleaned {column_name}: {valid_count:,} valid DNIs, {missing_count:,} missing")
    
    return cleaned


def validate_dni(dni: str) -> bool:
    """
    Validate if a DNI is properly formatted.
    
    Args:
        dni: DNI string to validate
    
    Returns:
        bool: True if valid (8 digits), False otherwise
    
    Examples:
        >>> validate_dni('12345678')
        True
        >>> validate_dni('123')
        False
        >>> validate_dni('')
        False
    """
    return len(dni) == 8 and dni.isdigit()


def find_invalid_dnis(df: pd.DataFrame, dni_column: str = 'dni') -> pd.DataFrame:
    """
    Find rows with invalid or missing DNIs.
    
    Args:
        df: DataFrame to check
        dni_column: Name of DNI column
    
    Returns:
        pd.DataFrame: Rows with invalid DNIs
    
    Example:
        >>> invalid = find_invalid_dnis(df)
        >>> print(f"Found {len(invalid)} invalid DNIs")
    """
    if dni_column not in df.columns:
        print(f"⚠️  Column '{dni_column}' not found in dataframe")
        return pd.DataFrame()
    
    # Find invalid DNIs
    invalid_mask = ~df[dni_column].apply(validate_dni)
    invalid_rows = df[invalid_mask].copy()
    
    if len(invalid_rows) > 0:
        print(f"⚠️  Found {len(invalid_rows)} rows with invalid/missing DNIs")
    
    return invalid_rows


def deduplicate_dnis(df: pd.DataFrame, dni_column: str = 'dni', 
                     keep: str = 'first') -> pd.DataFrame:
    """
    Remove duplicate DNI entries.
    
    Args:
        df: DataFrame to deduplicate
        dni_column: Name of DNI column
        keep: Which duplicate to keep ('first', 'last', or False to remove all)
    
    Returns:
        pd.DataFrame: Deduplicated dataframe
    
    Example:
        >>> df_clean = deduplicate_dnis(df, keep='first')
    """
    original_count = len(df)
    
    # Don't count empty DNIs as duplicates
    df_with_dni = df[df[dni_column] != ''].copy()
    df_without_dni = df[df[dni_column] == ''].copy()
    
    # Remove duplicates from records with DNI
    df_deduped = df_with_dni.drop_duplicates(subset=[dni_column], keep=keep)
    
    # Recombine
    result = pd.concat([df_deduped, df_without_dni], ignore_index=True)
    
    removed_count = original_count - len(result)
    if removed_count > 0:
        print(f"  ℹ️  Removed {removed_count} duplicate DNI entries")
    
    return result


# Convenience function for complete DNI cleaning workflow
def clean_and_validate_dnis(df: pd.DataFrame, dni_column: str = 'dni', 
                            remove_duplicates: bool = False) -> pd.DataFrame:
    """
    Complete DNI cleaning workflow: clean, validate, and optionally deduplicate.
    
    Args:
        df: DataFrame with DNI column
        dni_column: Name of DNI column
        remove_duplicates: Whether to remove duplicate DNIs
    
    Returns:
        pd.DataFrame: Cleaned dataframe
    
    Example:
        >>> df_clean = clean_and_validate_dnis(df, remove_duplicates=True)
    """
    df_clean = df.copy()
    
    print(f"Cleaning DNI column: {dni_column}")
    
    # Clean DNIs
    df_clean[dni_column] = clean_dni_series(df_clean[dni_column], dni_column)
    
    # Find and report invalid DNIs
    find_invalid_dnis(df_clean, dni_column)
    
    # Optionally remove duplicates
    if remove_duplicates:
        df_clean = deduplicate_dnis(df_clean, dni_column)
    
    return df_clean


if __name__ == "__main__":
    # Test the functions
    print("Testing DNI Cleaner...")
    print("\nTest cases:")
    
    test_cases = [
        (12345678, '12345678'),
        (1234567.0, '01234567'),
        ('  12345  ', '00012345'),
        ("'12345678", '12345678'),
        (None, ''),
        ('', ''),
        ('abc123def456gh78', '12345678'),
    ]
    
    for input_val, expected in test_cases:
        result = clean_dni(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} clean_dni({repr(input_val)}) = '{result}' (expected: '{expected}')")
    
    # Test with a sample dataframe
    print("\nTesting with DataFrame:")
    sample_df = pd.DataFrame({
        'dni': [12345678, 1234567.0, '  123  ', None, 87654321],
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve']
    })
    
    print("\nBefore cleaning:")
    print(sample_df)
    
    cleaned_df = clean_and_validate_dnis(sample_df)
    
    print("\nAfter cleaning:")
    print(cleaned_df)