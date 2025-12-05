"""
File Handler Utilities

Handles reading/writing files across different Producer Organizations.
Supports Excel files with complex headers, CSV files, and pickle files.
"""

import pandas as pd
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
import warnings
warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)


class FileHandler:
    """Handle all file I/O operations for the pipeline"""
    
    def __init__(self, base_path: str):
        """
        Initialize file handler with base directory path
        
        Args:
            base_path: Base directory for all PO data
        """
        self.base_path = Path(base_path)
    
    def read_excel_with_multirow_header(
        self,
        file_path: str,
        sheet_name: str,
        header_rows: List[int],
        skiprows: int = None,
        clean_columns: bool = True
    ) -> pd.DataFrame:
        """
        Read Excel file with multi-row headers (like Bagua format)
        
        Args:
            file_path: Path to Excel file
            sheet_name: Name of sheet to read
            header_rows: List of row indices that contain header information
            skiprows: Number of rows to skip after processing headers
            clean_columns: Whether to clean up 'Column_' and 'Unnamed:' columns
            
        Returns:
            DataFrame with processed headers
        """
        print(f"Reading {sheet_name} from {file_path}")
        
        # 1. Read header rows to understand structure
        headers_df = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            nrows=max(header_rows) + 1,
            header=None
        )
        
        # 2. Process multi-row headers
        processed_headers = []
        for col_idx in range(len(headers_df.columns)):
            # Collect all non-empty values for this column
            values = []
            for row_idx in header_rows:
                value = headers_df.iloc[row_idx, col_idx]
                if pd.notna(value) and 'Unnamed:' not in str(value):
                    values.append(str(value).strip())
            
            if not values:
                # No valid header found, use generic name
                processed_headers.append(f'Column_{col_idx}')
                continue
            
            # Join multi-row header with underscore
            final_header = '_'.join(values)
            # Clean up spaces and newlines
            final_header = ' '.join(final_header.split()).replace('\n', '')
            processed_headers.append(final_header)
        
        # 3. Read actual data with processed headers
        skip_rows = skiprows if skiprows else max(header_rows) + 1
        df = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            skiprows=skip_rows,
            header=None,
            names=processed_headers
        )
        
        # 4. Clean up
        df = df.dropna(how='all')  # Remove completely empty rows
        
        if clean_columns:
            # Remove columns that are purely administrative (Column_, Unnamed)
            columns_to_drop = [
                col for col in df.columns 
                if col.startswith('Column_') or col.startswith('Unnamed:')
            ]
            if columns_to_drop:
                df = df.drop(columns=columns_to_drop)
                print(f"  Dropped {len(columns_to_drop)} administrative columns")
        
        print(f"  Loaded {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    def read_excel_simple(
        self,
        file_path: str,
        sheet_name: str = 0,
        skiprows: int = 0,
        **kwargs
    ) -> pd.DataFrame:
        """
        Read Excel file with standard single-row header
        
        Args:
            file_path: Path to Excel file
            sheet_name: Sheet name or index (default: first sheet)
            skiprows: Number of rows to skip before header
            **kwargs: Additional arguments passed to pd.read_excel
            
        Returns:
            DataFrame
        """
        print(f"Reading {sheet_name} from {file_path}")
        df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=skiprows, **kwargs)
        df = df.dropna(how='all')
        print(f"  Loaded {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    def read_csv(
        self,
        file_path: str,
        encoding: str = 'utf-8',
        **kwargs
    ) -> pd.DataFrame:
        """
        Read CSV file with encoding handling
        
        Args:
            file_path: Path to CSV file
            encoding: File encoding (default: utf-8)
            **kwargs: Additional arguments passed to pd.read_csv
            
        Returns:
            DataFrame
        """
        print(f"Reading CSV: {file_path}")
        try:
            df = pd.read_csv(file_path, encoding=encoding, **kwargs)
        except UnicodeDecodeError:
            print(f"  Warning: Failed with {encoding}, trying latin-1")
            df = pd.read_csv(file_path, encoding='latin-1', **kwargs)
        
        df = df.dropna(how='all')
        print(f"  Loaded {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    def read_pickle(self, file_path: str) -> pd.DataFrame:
        """
        Read pickle file (for already-processed data)
        
        Args:
            file_path: Path to pickle file
            
        Returns:
            DataFrame
        """
        print(f"Reading pickle: {file_path}")
        df = pd.read_pickle(file_path)
        print(f"  Loaded {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    def save_pickle(
        self,
        df: pd.DataFrame,
        file_path: str,
        create_dir: bool = True
    ) -> None:
        """
        Save DataFrame as pickle file
        
        Args:
            df: DataFrame to save
            file_path: Destination path
            create_dir: Create parent directory if it doesn't exist
        """
        path = Path(file_path)
        if create_dir:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_pickle(path)
        print(f"✅ Saved pickle: {path} ({df.shape[0]} rows)")
    
    def save_csv(
        self,
        df: pd.DataFrame,
        file_path: str,
        create_dir: bool = True,
        **kwargs
    ) -> None:
        """
        Save DataFrame as CSV file
        
        Args:
            df: DataFrame to save
            file_path: Destination path
            create_dir: Create parent directory if it doesn't exist
            **kwargs: Additional arguments passed to df.to_csv
        """
        path = Path(file_path)
        if create_dir:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(path, index=False, **kwargs)
        print(f"✅ Saved CSV: {path} ({df.shape[0]} rows)")
    
    def remove_total_rows(self, df: pd.DataFrame, debug: bool = False) -> pd.DataFrame:
        """
        Remove rows containing 'TOTAL' and all rows after it
        Common in PO Excel files
        
        Args:
            df: Input DataFrame
            debug: Print debug information
            
        Returns:
            DataFrame with total rows removed
        """
        result_df = df.copy().reset_index(drop=True)
        total_rows = []
        
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
        
        if total_rows:
            first_total_row = min(total_rows)
            if debug:
                print(f"  First TOTAL row at index {first_total_row}")
            result_df = result_df.iloc[:first_total_row]
            rows_removed = len(df) - len(result_df)
            print(f"  Removed {rows_removed} rows (TOTAL and after)")
        
        return result_df


# Test function
if __name__ == "__main__":
    print("Testing FileHandler...")
    
    # Test with a sample path (adjust to your actual structure)
    handler = FileHandler(base_path=".")
    
    print("\n✅ FileHandler module ready!")
    print("\nUsage examples:")
    print("  handler = FileHandler('/path/to/data')")
    print("  df = handler.read_excel_with_multirow_header(file, sheet, [7,8,9,10])")
    print("  df = handler.read_excel_simple(file, sheet)")
    print("  df = handler.read_pickle(file)")
    print("  handler.save_csv(df, 'output.csv')")