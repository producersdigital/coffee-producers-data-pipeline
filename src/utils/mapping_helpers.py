"""
Mapping Helpers - Shared Utilities
====================================
Lookup-based mapping functions shared across Stage 2 modules.
 
Used by:
    src/stage2_integration/po_transformers.py
    src/stage2_integration/transactions_processor.py
 
Functions:
    map_gender_to_id()   - Maps gender text values to gender_code (M/F/O)
    map_unit_to_id()     - Maps unit text values to unit_code (KG/QQ/TM)
"""
 
import pandas as pd
 
 
def map_gender_to_id(gender_series: pd.Series, lookup_genders_df: pd.DataFrame) -> pd.Series:
    """
    Map gender text values to gender_code using lookup table.
    Handles Spanish and English variants.
 
    Args:
        gender_series:      Series of raw gender strings
        lookup_genders_df:  lookup_genders DataFrame from create_lookup_tables()
 
    Returns:
        Series of gender_code strings (M / F / O / <NA>)
    """
    gender_mapping = {}
 
    for _, row in lookup_genders_df.iterrows():
        gender_code = row['gender_code']
        if gender_code == 'M':
            gender_mapping.update({
                'm': 'M', 'male': 'M', 'masculino': 'M', 'hombre': 'M', 'h': 'M'
            })
        elif gender_code == 'F':
            gender_mapping.update({
                'f': 'F', 'female': 'F', 'femenino': 'F', 'mujer': 'F', 'w': 'F'
            })
        elif gender_code == 'O':
            gender_mapping.update({
                'o': 'O', 'other': 'O', 'otro': 'O', 'otros': 'O'
            })
 
    mapped_series = gender_series.str.lower().str.strip().map(gender_mapping)
 
    unmapped_count = mapped_series.isna().sum()
    if unmapped_count > 0:
        print(f"  ⚠️  Warning: {unmapped_count} genders could not be mapped")
        print(f"  Unmapped values: {gender_series[mapped_series.isna()].unique()}")
 
    return mapped_series.astype('string')
 
 
def map_unit_to_id(unit_series: pd.Series) -> pd.Series:
    """
    Map unit text values to unit_code (KG / QQ / TM).
 
    Args:
        unit_series:  Series of raw unit strings
 
    Returns:
        Series of unit_code strings
    """
    unit_mapping = {
        'kg': 'KG', 'kgs': 'KG', 'kilo': 'KG', 'kilos': 'KG',
        'kilogram': 'KG', 'kilogramos': 'KG',
        'qq': 'QQ', 'quintal': 'QQ', 'quintales': 'QQ', 'q': 'QQ',
        'tm': 'TM', 'ton': 'TM', 'tons': 'TM',
        'tonelada': 'TM', 'toneladas': 'TM', 't': 'TM',
    }
 
    mapped_series = unit_series.str.lower().str.strip().map(unit_mapping)
 
    unmapped_count = mapped_series.isna().sum()
    if unmapped_count > 0:
        print(f"  ⚠️  Warning: {unmapped_count} units could not be mapped")
        print(f"  Unmapped values: {unit_series[mapped_series.isna()].unique()}")
 
    return mapped_series.astype('string')