"""
File Handler Utility

Handles reading and writing files with complex formats, particularly Excel files
with multi-row headers common in Producer Organization inspection files.

Author: Daniela
"""

import pandas as pd
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import warnings
warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)


class FileHandler:
    """
    Handles all file I/O operations for the data pipeline.
    
    Features:
    - Read Excel files with multi-row headers
    - Read/write CSV, pickle files
    - Remove TOTAL rows automatically
    - Create directories as needed
    - Handle encoding issues
    
    Usage:
        handler = FileHandler(base_path='/path/to/data')
        df = handler.read_multi_header(
            'BAGUA GRANDE/raw_data/LPA 24.xlsx',
            sheet_name='Ecol',
            header_rows=[7, 8, 9, 10]
        )
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize file handler.
        
        Args:
            base_path: Base directory for all data files (optional)
                      If provided, all file paths will be relative to this
        """
        self.base_path = Path(base_path) if base_path else None
    
    def _resolve_path(self, file_path: str) -> Path:
        """
        Resolve file path relative to base_path if set.
        
        Args:
            file_path: File path (can be relative or absolute)
            
        Returns:
            Resolved Path object
        """
        path = Path(file_path)
        if self.base_path and not path.is_absolute():
            return self.base_path / path
        return path
    
    # ========================================================================
    # EXCEL READING - Multi-row Headers
    # ========================================================================
    
    def read_multi_header(self,
                         file_path: str,
                         sheet_name: str,
                         header_rows: List[int],
                         data_start_row: Optional[int] = None,
                         remove_total: bool = True,
                         clean_columns: bool = True) -> pd.DataFrame:
        """
        Read Excel file with multi-row headers.
        
        Many PO inspection files have headers spanning multiple rows:
        Row 7:  ['Nº', 'Cod', 'Superficie (ha)',      nan]
        Row 8:  [nan,  nan,  'Area total finca', 'Cultivo']
        Row 9:  [nan,  nan,  nan,                'Prod']
        
        Combined: ['Nº', 'Cod', 'Superficie (ha)_Area total finca', 'Cultivo_Prod']
        
        Args:
            file_path: Path to Excel file
            sheet_name: Name of sheet to read
            header_rows: List of row indices containing header info (0-indexed)
            data_start_row: Row where data starts (if None, uses max(header_rows) + 1)
            remove_total: Remove rows containing 'TOTAL'
            clean_columns: Remove 'Column_' and 'Unnamed:' columns
            
        Returns:
            DataFrame with combined headers and data
            
        Example:
            df = handler.read_multi_header(
                'BAGUA GRANDE/raw_data/LPA 24.xlsx',
                sheet_name='Ecol',
                header_rows=[7, 8, 9, 10]
            )
        """
        full_path = self._resolve_path(file_path)
        print(f"Reading {sheet_name} from {full_path.name}")
        
        # 1. Read header rows
        headers_df = pd.read_excel(
            full_path,
            sheet_name=sheet_name,
            nrows=max(header_rows) + 1,
            header=None
        )
        
        # 2. Combine multi-row headers
        column_names = self.combine_header_rows(headers_df, header_rows)
        
        # 3. Read actual data
        skip_rows = data_start_row if data_start_row else max(header_rows) + 1
        df = pd.read_excel(
            full_path,
            sheet_name=sheet_name,
            skiprows=skip_rows,
            header=None,
            names=column_names
        )
        
        # 4. Clean up
        df = df.dropna(how='all')  # Remove completely empty rows
        
        if remove_total:
            df = self.remove_total_rows(df)
        
        if clean_columns:
            # Remove administrative columns
            columns_to_drop = [
                col for col in df.columns
                if str(col).startswith('Column_') or 'Unnamed:' in str(col)
            ]
            if columns_to_drop:
                df = df.drop(columns=columns_to_drop)
                print(f"  Dropped {len(columns_to_drop)} administrative columns")
        
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    
    def combine_header_rows(self, 
                           headers_df: pd.DataFrame,
                           header_rows: List[int]) -> List[str]:
        """
        Combine multiple header rows into single column names.
        
        Args:
            headers_df: DataFrame containing the header rows
            header_rows: List of row indices to combine
            
        Returns:
            List of combined column names
        """
        combined_headers = []
        
        for col_idx in range(len(headers_df.columns)):
            # Collect all non-empty values for this column
            values = []
            
            for row_idx in header_rows:
                value = headers_df.iloc[row_idx, col_idx]
                
                # Skip NaN, empty, and 'Unnamed:' placeholders
                if pd.notna(value) and 'Unnamed:' not in str(value):
                    values.append(str(value).strip())
            
            # If no valid header found, use generic name
            if not values:
                combined_headers.append(f'Column_{col_idx}')
                continue
            
            # Join with underscore
            final_header = '_'.join(values)
            
            # Clean up whitespace and newlines
            final_header = ' '.join(final_header.split())
            final_header = final_header.replace('\n', '').replace('\r', '')
            
            combined_headers.append(final_header)
        
        return combined_headers
    
    def preview_headers(self,
                       file_path: str,
                       sheet_name: str,
                       header_rows: List[int]) -> pd.DataFrame:
        """
        Preview what header rows look like before combining.
        
        Useful for debugging and understanding file structure.
        
        Args:
            file_path: Path to Excel file
            sheet_name: Sheet name
            header_rows: List of row indices to examine
            
        Returns:
            DataFrame showing the header rows
        """
        full_path = self._resolve_path(file_path)
        
        headers_df = pd.read_excel(
            full_path,
            sheet_name=sheet_name,
            nrows=max(header_rows) + 1,
            header=None
        )
        
        print(f"Header rows for {sheet_name} sheet:")
        for row in header_rows:
            print(f"Row {row}:")
            print(headers_df.iloc[row].tolist())
        
        return headers_df
    
    # ========================================================================
    # EXCEL READING - Simple
    # ========================================================================
    
    def read_excel_simple(self,
                         file_path: str,
                         sheet_name: str = 0,
                         skiprows: int = 0,
                         remove_total: bool = True,
                         **kwargs) -> pd.DataFrame:
        """
        Read Excel file with standard single-row header.
        
        Args:
            file_path: Path to Excel file
            sheet_name: Sheet name or index (default: first sheet)
            skiprows: Number of rows to skip before header
            remove_total: Remove rows containing 'TOTAL'
            **kwargs: Additional arguments passed to pd.read_excel
            
        Returns:
            DataFrame
        """
        full_path = self._resolve_path(file_path)
        print(f"Reading {sheet_name} from {full_path.name}")
        
        df = pd.read_excel(full_path, sheet_name=sheet_name, skiprows=skiprows, **kwargs)
        df = df.dropna(how='all')
        
        if remove_total:
            df = self.remove_total_rows(df)
        
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    
    def get_sheet_names(self, file_path: str) -> List[str]:
        """
        Get all sheet names in an Excel file.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            List of sheet names
        """
        full_path = self._resolve_path(file_path)
        excel_file = pd.ExcelFile(full_path)
        return excel_file.sheet_names
    
    # ========================================================================
    # CSV READING
    # ========================================================================
    
    def read_csv(self,
                file_path: str,
                encoding: str = 'utf-8',
                remove_total: bool = True,
                **kwargs) -> pd.DataFrame:
        """
        Read CSV file with encoding handling.
        
        Args:
            file_path: Path to CSV file
            encoding: File encoding (default: utf-8)
            remove_total: Remove rows containing 'TOTAL'
            **kwargs: Additional arguments passed to pd.read_csv
            
        Returns:
            DataFrame
        """
        full_path = self._resolve_path(file_path)
        print(f"Reading CSV: {full_path.name}")
        
        try:
            df = pd.read_csv(full_path, encoding=encoding, **kwargs)
        except UnicodeDecodeError:
            print(f"  Warning: Failed with {encoding}, trying latin-1")
            df = pd.read_csv(full_path, encoding='latin-1', **kwargs)
        
        df = df.dropna(how='all')
        
        if remove_total:
            df = self.remove_total_rows(df)
        
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    
    # ========================================================================
    # PICKLE READING/WRITING
    # ========================================================================
    
    def read_pickle(self, file_path: str) -> pd.DataFrame:
        """
        Read pickle file (for already-processed data).
        
        Args:
            file_path: Path to pickle file
            
        Returns:
            DataFrame
        """
        full_path = self._resolve_path(file_path)
        print(f"Reading pickle: {full_path.name}")
        
        df = pd.read_pickle(full_path)
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    
    def save_pickle(self,
                   df: pd.DataFrame,
                   file_path: str,
                   create_dir: bool = True) -> None:
        """
        Save DataFrame as pickle file.
        
        Args:
            df: DataFrame to save
            file_path: Destination path
            create_dir: Create parent directory if it doesn't exist
        """
        full_path = self._resolve_path(file_path)
        
        if create_dir:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_pickle(full_path)
        print(f"✅ Saved pickle: {full_path.name} ({len(df)} rows)")
    
    # ========================================================================
    # CSV WRITING
    # ========================================================================
    
    def save_csv(self,
                df: pd.DataFrame,
                file_path: str,
                create_dir: bool = True,
                **kwargs) -> None:
        """
        Save DataFrame as CSV file.
        
        Args:
            df: DataFrame to save
            file_path: Destination path
            create_dir: Create parent directory if it doesn't exist
            **kwargs: Additional arguments passed to df.to_csv
        """
        full_path = self._resolve_path(file_path)
        
        if create_dir:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(full_path, index=False, **kwargs)
        print(f"✅ Saved CSV: {full_path.name} ({len(df)} rows)")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def remove_total_rows(self, df: pd.DataFrame, debug: bool = False) -> pd.DataFrame:
        """
        Remove rows containing 'TOTAL' and all rows after it.
        
        Common in PO Excel files where summary rows appear at the bottom.
        
        Args:
            df: Input DataFrame
            debug: Print debug information
            
        Returns:
            DataFrame with TOTAL rows removed
        """
        result_df = df.copy().reset_index(drop=True)
        total_rows = []
        
        # Check each column for 'TOTAL'
        for col in result_df.columns:
            try:
                col_as_str = result_df[col].astype(str)
                total_mask = col_as_str.str.contains('TOTAL', case=False, na=False)
                
                if total_mask.any():
                    found_rows = result_df.index[total_mask].tolist()
                    if debug:
                        print(f"  Found 'TOTAL' in column {col} at rows: {found_rows}")
                    total_rows.extend(found_rows)
            except Exception as e:
                if debug:
                    print(f"  Error checking column {col}: {str(e)}")
        
        # If TOTAL found, remove from first occurrence onward
        if total_rows:
            first_total_row = min(total_rows)
            if debug:
                print(f"  First TOTAL row at index {first_total_row}")
            
            result_df = result_df.iloc[:first_total_row]
            rows_removed = len(df) - len(result_df)
            print(f"  Removed {rows_removed} rows (TOTAL and after)")
        
        return result_df


# Convenience functions
def read_multi_header_excel(file_path: str,
                            sheet_name: str,
                            header_rows: List[int],
                            data_start_row: Optional[int] = None) -> pd.DataFrame:
    """
    Convenience function to read Excel with multi-row headers.
    
    Args:
        file_path: Path to Excel file
        sheet_name: Sheet name
        header_rows: List of header row indices
        data_start_row: Where data starts (optional)
        
    Returns:
        DataFrame with combined headers and data
    """
    handler = FileHandler()
    return handler.read_multi_header(file_path, sheet_name, header_rows, data_start_row)