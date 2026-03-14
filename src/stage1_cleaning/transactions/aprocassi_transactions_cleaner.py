"""
Aprocassi Transactions Data Cleaner
 
Cleans and standardizes transaction (acopio) data from Aprocassi Producer Organization.
Handles multi-year files (2022-2024).
 
Usage:
    from src.stage1_cleaning.transactions.aprocassi_transactions_cleaner import clean_aprocassi_transactions
    
    df = clean_aprocassi_transactions()
"""
 
import pandas as pd
from pathlib import Path
import sys
 
# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
 
from src.utils.dni_cleaner import DNICleaner
 
# Define DATA_DIR
DATA_DIR = project_root / 'data'
 
 
class AprocassiTransactionsCleaner:
    """
    Clean and standardize Aprocassi transaction data from multiple years.
    
    Attributes:
        file_paths: Dictionary mapping years to file paths
        data: Cleaned DataFrame
        dni_cleaner: DNI cleaning utility
    """
    
    # Administrative columns to drop
    ADMIN_COLUMNS = [
        'columna1', 'columna2', 'columna3', 'columna4', 'columna5',
        'columna6', 'columna7', 'columna8', 'doc', 'serie', 'número',
        'nº ticket', 'fec. co', 'sellos', 'parcela', 'almacén'
    ]
    
    def __init__(self):
        """Initialize the cleaner with file paths and utilities."""
        self.dni_cleaner = DNICleaner()
        
        # Define file paths for all years
        raw_dir = DATA_DIR / 'raw' / 'transactions' / 'aprocassi'
        self.file_paths = {
            2022: raw_dir / 'Acopio_2022.xlsx',
            2023: raw_dir / 'Acopio_2023.xlsx',
            2024: raw_dir / 'Acopio_2024.xlsx'
        }
        
        # Output directory
        self.output_dir = DATA_DIR / 'processed' / 'transactions' / 'aprocassi'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data = None
    
    def clean_all_years(self) -> pd.DataFrame:
        """
        Clean all transaction years and combine them.
        
        Returns:
            Combined and cleaned DataFrame
        """
        print("\n" + "="*60)
        print("CLEANING APROCASSI TRANSACTIONS")
        print("="*60)
        
        all_years = []
        
        for year, file_path in sorted(self.file_paths.items()):
            if not file_path.exists():
                print(f"\n⚠️  Skipping {year}: File not found")
                continue
            
            print(f"\nCleaning {year} transactions...")
            df = self._clean_single_year(file_path, year)
            all_years.append(df)
            print(f"  ✅ {year}: {len(df):,} transactions")
        
        # Combine all years
        print("\nCombining all years...")
        combined = pd.concat(all_years, ignore_index=True)
        
        # Apply final cleaning
        combined = self._final_cleaning(combined)
        
        # Store result
        self.data = combined
        
        print(f"\n✅ Aprocassi transactions cleaning complete!")
        print(f"   Total transactions: {len(combined):,}")
        print(f"   Years: {sorted(combined['campania'].unique())}")
        
        return combined
    
    def _clean_single_year(self, file_path: Path, year: int) -> pd.DataFrame:
        """
        Clean a single year's transaction file.
        
        Args:
            file_path: Path to the Excel file
            year: Year being processed
            
        Returns:
            Cleaned DataFrame for this year
        """
        # Read the file
        df = pd.read_excel(file_path, sheet_name='Sheet1', header=0)
        print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
        
        # Add campaign year
        df['campania'] = year
        print(f"  Added campania: {year}")
        
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
        
        # 1. Drop administrative columns
        df = self._drop_administrative_columns(df)
        
        # 2. Lowercase all column names
        df.columns = df.columns.str.lower().str.strip()
        print(f"  Converted column names to lowercase")
        
        # 3. Add metadata
        df['org_code'] = 'AP'
        df['country_code'] = 'PER'
        df['product_code'] = 'COFFEE'
        
        # Build data source string
        years = sorted(df['campania'].unique())
        data_source = f"Aprocassi Acopio files: {', '.join(map(str, years))}"
        df['data_source'] = data_source
        
        print(f"  Added metadata columns")
        
        # 4. Rename columns to standard names
        df = self._rename_to_standard(df)
        
        # 5. Normalize column names
        df = self.col_cleaner.clean(df)
        print(f"  Normalized column names")
        
        # 6. Clean DNI if it exists
        if 'dni' in df.columns:
            df['dni'] = self.dni_cleaner.clean(df['dni'], column_name='dni')
        
        # 7. Convert data types
        df = self._convert_data_types(df)
        
        # 8. Drop any unnamed columns
        unnamed_cols = [col for col in df.columns if 'unnamed' in col.lower()]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols)
            print(f"  Dropped {len(unnamed_cols)} unnamed (empty) columns")
        
        return df
    
    def _drop_administrative_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Drop administrative columns that aren't needed for analysis.
        
        Args:
            df: DataFrame with all columns
            
        Returns:
            DataFrame without administrative columns
        """
        # Lowercase for matching
        df_cols_lower = df.columns.str.lower()
        
        # Find columns to drop
        cols_to_drop = []
        for admin_col in self.ADMIN_COLUMNS:
            matching = [col for col, col_lower in zip(df.columns, df_cols_lower) 
                       if col_lower == admin_col.lower()]
            cols_to_drop.extend(matching)
        
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            print(f"  Dropped {len(cols_to_drop)} administrative columns")
        
        return df
    
    def _rename_to_standard(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename columns to standard names used across all POs.
        
        Args:
            df: DataFrame with original column names (already lowercased)
            
        Returns:
            DataFrame with standardized column names
        """
        # Standard renames (from notebook)
        rename_map = {
            'nombre': 'nombre_productor',
            'base sectorial': 'base',
            'fec. tk': 'fecha',
            'kg.': 'kg',
            'qq.': 'qq',
            '%': 'rendimiento',
            'hum': 'porcentaje_humedad',
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
        """Convert columns to appropriate data types."""
        print("\n  Converting data types...")
        
        # Campaign as string (categorical identifier)
        if 'campania' in df.columns:
            df['campania'] = df['campania'].astype(str)
            print(f"    Converted campania to string")
        
        # Date columns
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        
        # Numeric columns
        numeric_cols = ['kg', 'qq', 'rendimiento', 'porcentaje_humedad',
                       'precio_kg', 'precio_qq', 'total_soles']
        
        converted = 0
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                converted += 1
        
        if converted > 0:
            print(f"    Converted {converted} numeric columns")
        
        return df
    
    def get_summary(self) -> dict:
        """Get summary statistics of the cleaned data."""
        if self.data is None:
            return {"error": "No data available. Run clean_all_years() first."}
        
        df = self.data
        
        summary = {
            "total_transactions": len(df),
            "years": sorted(df['campania'].unique().tolist()),
            "transactions_by_year": df['campania'].value_counts().sort_index().to_dict(),
            "columns": len(df.columns),
            "column_names": df.columns.tolist()
        }
        
        if 'dni' in df.columns:
            summary["unique_farmers"] = df['dni'].nunique()
        
        if 'fecha' in df.columns:
            dates = pd.to_datetime(df['fecha'], errors='coerce').dropna()
            if len(dates) > 0:
                summary["date_range"] = f"{dates.min()} to {dates.max()}"
        
        if 'kg' in df.columns:
            summary["total_kg"] = df['kg'].sum()
        
        return summary
    
    def save(self, filename: str = 'aprocassi_transactions_clean.pkl') -> Path:
        """
        Save cleaned data to pickle file.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        if self.data is None:
            raise ValueError("No data to save. Run clean_all_years() first.")
        
        output_path = self.output_dir / filename
        self.data.to_pickle(output_path)
        print(f"✅ Saved pickle: {output_path.name} ({len(self.data):,} rows)")
        
        return output_path
 
 
def clean_aprocassi_transactions() -> pd.DataFrame:
    """
    Convenience function to clean Aprocassi transactions data.
    
    Returns:
        Cleaned DataFrame
    """
    cleaner = AprocassiTransactionsCleaner()
    df = cleaner.clean_all_years()
    cleaner.save()
    
    return df
 
 
if __name__ == "__main__":
    # Run the cleaner
    df = clean_aprocassi_transactions()
    
    # Print summary
    cleaner = AprocassiTransactionsCleaner()
    cleaner.data = df
    summary = cleaner.get_summary()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total transactions: {summary['total_transactions']:,}")
    print(f"Years processed: {summary['years']}")
    for year, count in summary['transactions_by_year'].items():
        print(f"  - {year}: {count:,} transactions")
    
    if 'date_range' in summary:
        print(f"Date range: {summary['date_range']}")
    
    if 'unique_farmers' in summary:
        print(f"Unique farmers: {summary['unique_farmers']}")
    
    if 'total_kg' in summary:
        print(f"Total KG: {summary['total_kg']:,.2f}")
    
    print("\nFirst 3 transactions preview:")
    display_cols = [c for c in ['fecha', 'campania', 'nombre_productor', 'kg', 'categoria'] 
                    if c in df.columns]
    print(df[display_cols].head(3))
    
    print(f"\nColumn names:")
    print(df.columns.tolist())
    
    print("\n" + "="*60)