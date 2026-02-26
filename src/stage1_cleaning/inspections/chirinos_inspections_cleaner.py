"""
Chirinos Inspections Cleaner

Handles cleaning and harmonization of Chirinos inspection files
across multiple years (2020-2024).

Each year's file gets:
    1. Column name stripping (whitespace / newlines)
    2. TOTAL row removal (same logic as 2024 cleaning notebook)
    3. Column renaming via CHIRINOS_MAPPINGS
    4. año_inspeccion column added as second column
    5. Concatenation across all years
    6. Data type conversion (once, after concat)
"""

import pandas as pd
import pickle
from pathlib import Path

from src.stage1_cleaning.inspections.chirinos_column_mappings import CHIRINOS_MAPPINGS


class ChirinosInspectionsCleaner:
    """
    Cleaner for Chirinos multi-year inspection data.

    Parameters
    ----------
    year_files : dict
        Mapping of {year: file_path} for each inspection year to load.
        Example: {2024: 'data/raw/inspections/chirinos/chirinos_2024.xlsx'}
    base_path : str or Path, optional
        Base path prepended to all file paths if provided.
    """

    def __init__(self, year_files: dict, base_path=None, sheet_names: dict = None):
        self.year_files = year_files
        self.base_path = Path(base_path) if base_path else None
        self.sheet_names = sheet_names or {}  # e.g. {2024: 'LPA-General 2024'}
        self.clean_data = None
        self._summary = {}

    # ─── PRIVATE HELPERS ──────────────────────────────────────────────────────

    def _resolve_path(self, filepath) -> Path:
        p = Path(filepath)
        if self.base_path:
            return self.base_path / p
        return p

    def _strip_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Strip leading/trailing whitespace and normalize internal newlines
        in column names. Handles invisible-character mismatches between years.

        Steps applied in order:
          1. Strip leading/trailing whitespace
          2. Replace newlines with a single space
          3. Collapse any resulting double spaces to single space
        This ensures mapping keys only need to worry about single spaces.
        """
        df.columns = (
            df.columns
            .str.strip()
            .str.replace('\n', ' ', regex=False)
            .str.replace('\r', ' ', regex=False)
            .str.replace(r'  +', ' ', regex=True)   # collapse double spaces
        )
        return df

    def _remove_totals_and_after(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Remove the TOTAL row and all rows that follow it.
        Mirrors the logic from the 2024 Chirinos cleaning notebook.
        """
        df = df.copy().reset_index(drop=True)
        total_rows = []

        for col in df.columns:
            try:
                mask = df[col].astype(str).str.contains('TOTAL', case=False, na=False)
                if mask.any():
                    total_rows.extend(df.index[mask].tolist())
            except Exception:
                pass

        if total_rows:
            first_total = min(total_rows)
            print(f"    [{year}] TOTAL row found at index {first_total} — removing it and everything after")
            df = df.iloc[:first_total]
        else:
            print(f"    [{year}] No TOTAL row found")

        return df.reset_index(drop=True)

    def _apply_column_mapping(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Rename columns using CHIRINOS_MAPPINGS for the given year.
        Columns not present in the mapping keep their original name.
        Warns about any expected mapping keys missing from the file.
        """
        mapping = CHIRINOS_MAPPINGS.get(year, {})

        missing = [col for col in mapping if col not in df.columns]
        if missing:
            print(f"    [{year}] WARNING — mapped columns not found in file: {missing}")

        existing_mapping = {k: v for k, v in mapping.items() if k in df.columns}
        return df.rename(columns=existing_mapping)

    def _add_inspection_year(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """Insert año_inspeccion as the second column (right after dni)."""
        df.insert(1, 'año_inspeccion', year)
        return df

    def _load_year(self, year: int, filepath) -> pd.DataFrame:
        """Full preparation pipeline for a single year's raw file."""
        path = self._resolve_path(filepath)
        print(f"\n  Loading {year} — {path.name}")

        sheet = self.sheet_names.get(year, 0)
        df = pd.read_excel(path, sheet_name=sheet)
        if isinstance(sheet, str):
            print(f"    Using sheet: '{sheet}'")

        df = self._strip_column_names(df)
        df = self._remove_totals_and_after(df, year)
        df = self._apply_column_mapping(df, year)
        df = self._add_inspection_year(df, year)

        print(f"    Prepared shape: {df.shape}")
        return df

    # ─── DATA TYPE CONVERSION (runs after concat) ─────────────────────────────

    def _convert_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert data types on the combined dataframe.
        Applied once after concat — mirrors the 2024 cleaning notebook logic.
        """
        print("\n  Converting data types...")

        # --- DNI columns: 8-digit zero-padded string ---
        # Cast to object first to avoid FutureWarning when assigning strings into float column
        dni_cols = ['dni', 'dni_inspector_interno', 'dni_verificacion']
        for col in dni_cols:
            if col in df.columns:
                numeric = pd.to_numeric(df[col], errors='coerce')
                mask = numeric.notna()
                result = numeric.copy().astype(object)
                result[mask] = numeric[mask].astype(int).astype(str).str.zfill(8)
                result[~mask] = ''
                df[col] = result
                print(f"    {col}: standardized to 8-digit string")

        # --- Phone: digits only, no formatting ---
        if 'telefono' in df.columns:
            df['telefono'] = (
                df['telefono']
                .astype(str)
                .replace('nan', '')
                .str.replace(r'[^0-9+]', '', regex=True)
            )
            print(f"    telefono: cleaned to digits only")

        # --- Date columns ---
        date_cols = [
            'fecha_nacimiento',
            'fecha_ingreso',
            'fecha_inicio_conversion',
            'fecha_ultimo_control_interno',
        ]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                print(f"    {col}: converted to datetime")

        # --- Area columns: float, 2 decimal places, NaN → 0 ---
        area_cols = [c for c in df.columns if c.startswith('area_')]
        for col in area_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        if area_cols:
            print(f"    area columns ({len(area_cols)}): float, 2dp, NaN→0")

        # --- Harvest / yield columns: float, 2 decimal places, NaN → 0 ---
        harvest_keywords = [
            'cosecha_', 'rendimiento_', 'compromiso_acopio',
            'cosecha_acopio', 'saldo_acopio', 'pct_cumplimiento',
            'cultivo_total'
        ]
        harvest_cols = [
            c for c in df.columns
            if any(k in c for k in harvest_keywords)
        ]
        for col in harvest_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2).fillna(0)
        if harvest_cols:
            print(f"    harvest columns ({len(harvest_cols)}): float, 2dp, NaN→0")

        # --- Geolocation: float ---
        for col in ['latitud', 'longitud']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                print(f"    {col}: float")

        # --- Altitud, parcelas: nullable integer (supports NaN across years) ---
        for col in ['altitud', 'numero_parcelas']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                print(f"    {col}: Int64 (nullable integer)")

        # --- Categorical text: lowercase and strip ---
        text_cols = [
            'genero', 'categoria', 'categoria_propuesta', 'estado_socio',
            'resultado_control_interno', 'certificacion', 'nombre_productor'
        ]
        for col in text_cols:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str)
                    .str.lower()
                    .str.strip()
                    .replace('nan', '')
                )
        print(f"    text/category columns: lowercased and stripped")

        return df

    # ─── PUBLIC API ───────────────────────────────────────────────────────────

    def diagnose_columns(self, year: int, filepath):
        """
        Diagnostic helper: prints the actual column names in a file AFTER
        strip normalization, so you can verify mapping keys are correct.
        Use this when you see 'mapped columns not found' warnings.

        Usage:
            cleaner.diagnose_columns(2024, 'data/raw/inspections/chirinos/chirinos_2024.xlsx')
        """
        path = self._resolve_path(filepath)
        df = pd.read_excel(path)
        df = self._strip_column_names(df)
        print(f"\n[{year}] Actual column names after stripping ({len(df.columns)} cols):")
        for i, col in enumerate(df.columns):
            mapped_to = CHIRINOS_MAPPINGS.get(year, {}).get(col, '— NOT IN MAPPING')
            print(f"  {i:3d}: '{col}'  →  {mapped_to}")
        return df.columns.tolist()

    def clean_all_years(self) -> pd.DataFrame:
        """
        Load, prepare and concatenate all year files.
        Data type conversion is applied after concat.

        Returns
        -------
        pd.DataFrame
            Combined cleaned dataframe with all years stacked.
        """
        year_dfs = []

        for year, filepath in sorted(self.year_files.items()):
            path = self._resolve_path(filepath)
            if not path.exists():
                print(f"\n  SKIPPING {year} — file not found: {path}")
                continue
            df = self._load_year(year, filepath)
            year_dfs.append(df)

        if not year_dfs:
            raise FileNotFoundError("No year files were successfully loaded.")

        print(f"\n  Concatenating {len(year_dfs)} year(s)...")
        combined = pd.concat(year_dfs, axis=0, ignore_index=True)
        print(f"  Combined shape before dtype conversion: {combined.shape}")

        combined = self._convert_dtypes(combined)

        # Sort by DNI then year for readability
        combined = combined.sort_values(
            ['dni', 'año_inspeccion'], na_position='last'
        ).reset_index(drop=True)

        # Add metadata
        combined['org_code'] = 'CH'
        combined['country_code'] = 'PER'

        self.clean_data = combined
        self._build_summary()

        return self.clean_data

    def _build_summary(self):
        """Compute summary statistics from the cleaned data."""
        if self.clean_data is None:
            return
        df = self.clean_data
        self._summary = {
            'total_rows': len(df),
            'years_present': sorted(df['año_inspeccion'].unique().tolist()),
            'rows_per_year': df.groupby('año_inspeccion').size().to_dict(),
            'unique_farmers_dni': df['dni'].replace('', pd.NA).nunique(),
            'missing_dni': (df['dni'] == '').sum(),
            'total_columns': len(df.columns),
        }

    def get_summary(self) -> dict:
        """Return summary statistics from the last clean_all_years() run."""
        return self._summary

    def save(self, output_path: str):
        """
        Save the cleaned dataframe to a pickle file.

        Parameters
        ----------
        output_path : str
            Path ending in .pkl where the dataframe will be saved.
        """
        if self.clean_data is None:
            raise ValueError("No cleaned data to save. Run clean_all_years() first.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'wb') as f:
            pickle.dump(self.clean_data, f)

        print(f"  Saved pickle: {path}")


















