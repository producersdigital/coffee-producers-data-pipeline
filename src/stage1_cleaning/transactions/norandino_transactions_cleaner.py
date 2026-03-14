"""
Norandino Transactions Data Cleaner
 
Cleans and standardizes transaction (acopio) data from Norandino Producer Organization.
Handles multi-year files (2021-2025) with different structures.
 
Usage:
    from src.stage1_cleaning.transactions.norandino_transactions_cleaner import clean_norandino_transactions
    
    df = clean_norandino_transactions()
"""
 
import pandas as pd
from pathlib import Path
import sys
 
# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
 
from src.utils.dni_cleaner import DNICleaner
from src.utils.column_cleaner import ColumnCleaner
 
# Define DATA_DIR
DATA_DIR = project_root / 'data'
 
 
class NorandinoTransactionsCleaner:
    """
    Clean and standardize Norandino transaction data from multiple years.
    
    Handles 4 yearly files (2021, 2022, 2023-2024, 2025) with different
    file names, sheet names, and total row counts.
    
    Attributes:
        file_configs: Dictionary mapping years to file configurations
        data: Cleaned DataFrame
        dni_cleaner: DNI cleaning utility
        col_cleaner: Column cleaning utility
    """
    
    # Administrative columns to drop
    ADMIN_COLUMNS = [
        'ley 31335', 'guia remision', 'lote recep', 'codprod', 
        'pu', 'cliente', 'organización', 'zonal', 'base'
    ]
    
    def __init__(self):
        """Initialize the cleaner with file paths and utilities."""
        self.dni_cleaner = DNICleaner()
        self.col_cleaner = ColumnCleaner()
        
        # Define file configurations for each year
        raw_dir = DATA_DIR / 'raw' / 'transactions' / 'norandino'
        
        self.file_configs = {
            2021: {
                'path': raw_dir / '2021_.xlsx',
                'sheet': 'Hoja1',
                'header': 6,
                'remove_last_rows': 1
            },
            2022: {
                'path': raw_dir / 'Cafe Socios Natural 2022_PD.xlsx',
                'sheet': 'Socios2022',
                'header': 6,
                'remove_last_rows': 3
            },
            2023: {
                'path': raw_dir / 'Socios_Naturales_2024.xlsx',
                'sheet': 'Socios2023',
                'header': 6,
                'remove_last_rows': 0  # No total rows to remove
            },
            2025: {
                'path': raw_dir / 'ACOPIO 2025.xlsx',
                'sheet': 'Hoja1',
                'header': 6,
                'remove_last_rows': 1
            }
        }
        
        # Output directory
        self.output_dir = DATA_DIR / 'processed' / 'transactions' / 'norandino'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data = None
    
    def clean_all_years(self) -> pd.DataFrame:
        """
        Clean all transaction years and combine them.
        
        Returns:
            Combined and cleaned DataFrame
        """
        print("\n" + "="*60)
        print("CLEANING NORANDINO TRANSACTIONS")
        print("="*60)
        
        all_years = []
        
        for year, config in sorted(self.file_configs.items()):
            if not config['path'].exists():
                print(f"\n⚠️  Skipping {year}: File not found")
                continue
            
            # Special label for 2023 config (file is Socios_Naturales_2024.xlsx with 2023-2024 data)
            year_label = "2023-2024" if year == 2023 else str(year)
            
            print(f"\nCleaning {year_label} transactions...")
            df = self._clean_single_year(config, year)
            all_years.append(df)
            print(f"  ✅ {year_label}: {len(df):,} transactions")
        
        # Combine all years
        print("\nCombining all years...")
        combined = pd.concat(all_years, ignore_index=True)
        
        # Apply final cleaning
        combined = self._final_cleaning(combined)
        
        # Store result
        self.data = combined
        
        print(f"\n✅ Norandino transactions cleaning complete!")
        print(f"   Total transactions: {len(combined):,}")
        print(f"   Years: {sorted([y for y in self.file_configs.keys() if (self.file_configs[y]['path']).exists()])}")
        
        return combined
    
    def _clean_single_year(self, config: dict, year: int) -> pd.DataFrame:
        """
        Clean a single year's transaction file.
        
        Args:
            config: Configuration dict with path, sheet, header, remove_last_rows
            year: Year being processed
            
        Returns:
            Cleaned DataFrame for this year
        """
        # Read the file
        df = pd.read_excel(
            config['path'],
            sheet_name=config['sheet'],
            header=config['header']
        )
        print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
        
        # Remove total rows if specified
        if config['remove_last_rows'] > 0:
            df = df.iloc[:-config['remove_last_rows']]
            print(f"  Removed last {config['remove_last_rows']} row(s)")
        
        # Special note for 2023 config (file Socios_Naturales_2024.xlsx contains both years)
        if year == 2023:
            print(f"  ℹ️  Note: File 'Socios_Naturales_2024.xlsx' contains combined 2023 and 2024 campaign data")
                
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
        
        # 3. Rename columns to standard names
        df = self._rename_to_standard(df)
        
        # 4. Normalize column names
        df = self.col_cleaner.clean(df)
        print(f"  Normalized column names")
        
        # 5. Add metadata
        df['org_code'] = 'NO'
        df['country_code'] = 'PER'
        df['product_code'] = 'COFFEE'
        
        # Build data source string
        years = sorted([y for y in self.file_configs.keys() 
                       if self.file_configs[y]['path'].exists()])
        data_source = f"Norandino ACOPIO files: {', '.join(map(str, years))}"
        df['data_source'] = data_source
        
        print(f"  Added metadata columns")
        
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
            'campaña': 'campania',
            'apellidos y nombres': 'nombre_productor',
            'und': 'unidad',
            'total soles': 'total_soles',
            'rend': 'rendimiento',
            '(%hum)': 'porcentaje_humedad',
            'qq recep': 'qq',
            'qq (%hum)': 'qq_porcentaje_humedad',
            'kg recepcionados': 'kg',
            'kg brutos': 'kg_brutos',
            'kgsnetos': 'kg_netos'
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
        date_cols = ['fecha', 'fecha_recepcion', 'fec_recep']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Numeric columns
        numeric_cols = ['kg', 'qq', 'rendimiento', 'porcentaje_humedad',
                       'qq_porcentaje_humedad', 'kg_brutos', 'kg_netos',
                       'total_soles', 'precio_kg', 'precio_qq']
        
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
            "years": sorted(df['campania'].unique().tolist()) if 'campania' in df.columns else [],
            "transactions_by_year": df['campania'].value_counts().sort_index().to_dict() if 'campania' in df.columns else {},
            "columns": len(df.columns),
            "column_names": df.columns.tolist()
        }
        
        if 'dni' in df.columns:
            summary["unique_farmers"] = df['dni'].nunique()
        
        if 'nombre_productor' in df.columns:
            summary["unique_farmers_by_name"] = df['nombre_productor'].nunique()
        
        if 'fecha' in df.columns:
            dates = pd.to_datetime(df['fecha'], errors='coerce').dropna()
            if len(dates) > 0:
                summary["date_range"] = f"{dates.min()} to {dates.max()}"
        
        if 'kg' in df.columns:
            summary["total_kg"] = df['kg'].sum()
        
        return summary
    
    def save(self, filename: str = 'norandino_transactions_clean.pkl') -> Path:
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
 
 
def clean_norandino_transactions() -> pd.DataFrame:
    """
    Convenience function to clean Norandino transactions data.
    
    Returns:
        Cleaned DataFrame
    """
    cleaner = NorandinoTransactionsCleaner()
    df = cleaner.clean_all_years()
    cleaner.save()
    
    return df
 
 
if __name__ == "__main__":
    # Run the cleaner
    df = clean_norandino_transactions()
    
    # Print summary
    cleaner = NorandinoTransactionsCleaner()
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
        print(f"Unique farmers (by DNI): {summary['unique_farmers']}")
    
    if 'unique_farmers_by_name' in summary:
        print(f"Unique farmers (by name): {summary['unique_farmers_by_name']}")
    
    if 'total_kg' in summary:
        print(f"Total KG: {summary['total_kg']:,.2f}")
    
    print("\nFirst 3 transactions preview:")
    display_cols = [c for c in ['fecha', 'campania', 'nombre_productor', 'kg', 'qq'] 
                    if c in df.columns]
    if display_cols:
        print(df[display_cols].head(3).to_string(index=False))
    
    print(f"\nColumn names:")
    print(df.columns.tolist())
    
    print("\n" + "="*60)