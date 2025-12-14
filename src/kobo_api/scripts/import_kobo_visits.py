#!/usr/bin/env python3
"""
Import Kobo technical assistance visits into the database.

Usage:
    python import_kobo_visits.py                    # Full import
    python import_kobo_visits.py --test 100        # Test with first 100 rows
    python import_kobo_visits.py --dry-run         # Simulate without inserting
"""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional

import pandas as pd
import mysql.connector
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import create_connection

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Paths - logs under src/kobo_api/logs/
KOBO_API_DIR = project_root / "src" / "kobo_api"
LOGS_BASE_DIR = KOBO_API_DIR / "logs"
LOGS_BASE_DIR.mkdir(exist_ok=True)

# Cumulative summary log
CUMULATIVE_SUMMARY_LOG = LOGS_BASE_DIR / "import_summary.log"


class KoboImporter:
    def __init__(self, dry_run: bool = False, test_rows: Optional[int] = None):
        self.dry_run = dry_run
        self.test_rows = test_rows
        self.import_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.import_folder_name = datetime.now().strftime("import_%Y%m%d_%H%M%S")

        # Create folder for this import run
        self.import_dir = LOGS_BASE_DIR / self.import_folder_name
        self.import_dir.mkdir(exist_ok=True)

        # Paths for this import
        self.source_csv_path = self.import_dir / "source.csv"
        self.unmatched_farmers_log = self.import_dir / "unmatched_farmers.csv"
        self.unmatched_extensionists_log = self.import_dir / "unmatched_extensionists.csv"
        self.import_summary_file = self.import_dir / "summary.txt"

        # Statistics
        self.stats = {
            'total_records': 0,
            'successful': 0,
            'already_exists': 0,
            'farmer_not_found': 0,
            'extensionist_not_found': 0,
        }

        # Lookup caches (loaded once for performance)
        self.farmers_lookup: Dict[str, int] = {}  # national_id -> farmer_id
        self.extensionists_lookup: Dict[str, int] = {}  # code -> extensionist_id
        self.existing_uuids: Set[str] = set()  # kobo_uuid

        # Batch insert lists
        self.visits_to_insert: List[Tuple] = []
        self.unmatched_farmers: List[Dict] = []
        self.unmatched_extensionists: List[Dict] = []

    def load_lookups(self, connection):
        """Load all lookup data into memory for fast matching."""
        logger.info("Loading lookup data...")
        cursor = connection.cursor(dictionary=True)

        # Load farmers: national_id -> farmer_id
        cursor.execute("SELECT farmer_id, national_id FROM farmers WHERE national_id IS NOT NULL")
        self.farmers_lookup = {row['national_id']: row['farmer_id'] for row in cursor.fetchall()}
        logger.info(f"Loaded {len(self.farmers_lookup)} farmers")

        # Load extensionists: code -> extensionist_id
        cursor.execute("SELECT extensionist_id, extensionist_code FROM extensionists")
        self.extensionists_lookup = {row['extensionist_code']: row['extensionist_id'] for row in cursor.fetchall()}
        logger.info(f"Loaded {len(self.extensionists_lookup)} extensionists")

        # Load existing kobo_uuids to detect duplicates
        cursor.execute("SELECT kobo_uuid FROM technical_assistance_visits")
        self.existing_uuids = {row['kobo_uuid'] for row in cursor.fetchall()}
        logger.info(f"Loaded {len(self.existing_uuids)} existing visit UUIDs")

        cursor.close()

    def get_latest_csv(self) -> Path:
        """Get the most recent Kobo export CSV."""
        exports_dir = project_root / "data" / "kobo_exports"
        csv_files = list(exports_dir.glob("kobo_export_*.csv"))

        if not csv_files:
            raise FileNotFoundError(f"No Kobo export files found in {exports_dir}")

        latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"Using CSV: {latest_csv.name}")
        return latest_csv

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply data cleaning transformations."""
        logger.info("Cleaning data...")

        # Clean DNI (already read as string, just strip and handle NaN)
        df['Insertar No de DNI productor'] = df['Insertar No de DNI productor'].fillna('').str.strip()

        # Convert tiempo_total to number
        df['tiempo_total'] = pd.to_numeric(df['tiempo_total'], errors='coerce')

        # Extract year and month from visit date
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['visit_year'] = df['Fecha'].dt.year.astype(str)
        df['visit_month'] = df['Fecha'].dt.month.astype(str).str.zfill(2)

        return df

    def convert_to_bool(self, value) -> bool:
        """Convert Kobo checkbox value to boolean."""
        if pd.isna(value) or value == '':
            return False
        return True

    def safe_numeric(self, value):
        """Convert to numeric, returning None instead of NaN."""
        result = pd.to_numeric(value, errors='coerce')
        return None if pd.isna(result) else result

    def safe_datetime(self, value):
        """Convert to datetime, returning None instead of NaT."""
        result = pd.to_datetime(value, errors='coerce')
        return None if pd.isna(result) else result

    def process_row(self, row: pd.Series, index: int) -> Optional[Tuple]:
        """Process a single row and return insert tuple or None."""
        kobo_uuid = str(row['_uuid']).strip()

        # Check if already imported
        if kobo_uuid in self.existing_uuids:
            self.stats['already_exists'] += 1
            return None

        # Match DNI to farmer_id
        dni = str(row['Insertar No de DNI productor']).strip()
        farmer_id = self.farmers_lookup.get(dni)

        if not farmer_id:
            self.stats['farmer_not_found'] += 1
            self.unmatched_farmers.append({
                'import_date': self.import_timestamp,
                'kobo_uuid': kobo_uuid,
                'dni': dni,
                'producer_name_from_kobo': str(row.get('nombre_completo', '')),
                'extensionist_code': str(row.get('Nombre_Tecnico', '')),
                'visit_date': str(row.get('Fecha', '')),
                'error_reason': 'DNI not found in farmers table'
            })
            return None

        # Match extensionist code to extensionist_id
        ext_code = str(row['Nombre_Tecnico']).strip()
        extensionist_id = self.extensionists_lookup.get(ext_code)

        if not extensionist_id:
            self.stats['extensionist_not_found'] += 1
            self.unmatched_extensionists.append({
                'import_date': self.import_timestamp,
                'kobo_uuid': kobo_uuid,
                'extensionist_code': ext_code,
                'dni': dni,
                'producer_name': str(row.get('nombre_completo', '')),
                'visit_date': str(row.get('Fecha', '')),
                'error_reason': 'Extensionist code not found in extensionists table'
            })
            return None

        # Build insert tuple (all 50 fields)
        insert_data = (
            kobo_uuid,                                      # kobo_uuid
            str(row.get('_id', '')),                       # kobo_submission_id
            farmer_id,                                      # farmer_id
            extensionist_id,                                # extensionist_id
            row['Fecha'].date() if pd.notna(row['Fecha']) else None,  # visit_date
            str(row['visit_year']),                        # visit_year
            str(row['visit_month']),                       # visit_month
            str(row.get('nombre_completo', '')),           # producer_name_from_kobo
            str(row.get('Producto', '')),                  # product_name_raw

            # Time fields (decimal hours)
            self.safe_numeric(row.get('1.1 Asesoria en la gestión documentaria del SIC y fortalecimiento organizativo')),
            self.safe_numeric(row.get('1.2 Asesoria en acopio y trazabilidad del producto')),
            self.safe_numeric(row.get('1.3 Asistencia técnica a productores en el manejo del cultivo')),
            self.safe_numeric(row.get('1.4 Seguimiento a la cosecha y post cosecha del producto')),
            self.safe_numeric(row.get('1.5 Tiempo de traslado')),
            self.safe_numeric(row.get('1.6 Trabajo de gabinete')),
            self.safe_numeric(row.get('tiempo_total')),

            # Activity details
            str(row.get('Descripción de la actividad', '')),
            str(row.get('Recomendaciones', '')),
            str(row.get('Compromisos para la proxima visita', '')),
            str(row.get('estatus_cert_actual', '')),

            # Disease info
            str(row.get('¿La parcela está con ojo de pollo?', '')),

            # Symptoms (8 booleans)
            self.convert_to_bool(row.get('Qué síntomas presenta/Manchas redondas de color marrón claro o beige en las hojas')),
            self.convert_to_bool(row.get('Qué síntomas presenta/Las manchas tienen un borde más oscuro alrededor')),
            self.convert_to_bool(row.get('Qué síntomas presenta/En el centro de la mancha hay un punto negro, como un ojo')),
            self.convert_to_bool(row.get('Qué síntomas presenta/Las hojas están cayendo')),
            self.convert_to_bool(row.get('Qué síntomas presenta/Manchas en las ramas')),
            self.convert_to_bool(row.get('Qué síntomas presenta/Ramas secando')),
            self.convert_to_bool(row.get('Qué síntomas presenta/Pelusa o capa blanca en las ramas')),
            self.convert_to_bool(row.get('Qué síntomas presenta/Frutos con manchas similares a las de las hojas')),

            # Other diseases (16 booleans)
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Manchas redondas de color marrón claro o beige en las hojas')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Las manchas tienen un borde más oscuro alrededor')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/En el centro de la mancha hay un punto negro, como un ojo')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Las hojas están cayendo')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Manchas en las ramas')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Ramas secando')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Pelusa o capa blanca en las ramas')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Frutos con manchas similares a las de las hojas')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Roya')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Antracnosis')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Broca')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Arañero')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Cercospora')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Minadores')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Pie negro')),
            self.convert_to_bool(row.get('¿Qué otras enfermedades están afectando?/Phoma')),

            # Metadata
            self.safe_datetime(row.get('_submission_time')),
        )

        return insert_data

    def batch_insert(self, connection):
        """Insert all valid visits in a single batch."""
        if not self.visits_to_insert:
            logger.info("No records to insert")
            return

        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert {len(self.visits_to_insert)} records")
            self.stats['successful'] = len(self.visits_to_insert)
            return

        logger.info(f"Inserting {len(self.visits_to_insert)} records...")

        insert_query = """
            INSERT INTO technical_assistance_visits (
                kobo_uuid, kobo_submission_id, farmer_id, extensionist_id,
                visit_date, visit_year, visit_month, producer_name_from_kobo, product_name_raw,
                advisory_sig_time, advisory_traceability_time, technical_crop_management_time,
                harvest_followup_time, travel_time, office_work_time, total_time,
                activity_description, recommendations, commitments_next_visit,
                current_certification_status, has_coffee_eye_spot,
                symptom_brown_spots_leaves, symptom_dark_border, symptom_black_center_eye,
                symptom_falling_leaves, symptom_branch_spots, symptom_drying_branches,
                symptom_white_fuzz_branches, symptom_fruit_spots,
                disease_brown_spots_leaves, disease_dark_border, disease_black_center,
                disease_falling_leaves, disease_branch_spots, disease_drying_branches,
                disease_white_fuzz, disease_fruit_spots, disease_roya, disease_anthracnose,
                disease_broca, disease_spider_mite, disease_cercospora, disease_leaf_miners,
                disease_black_foot, disease_phoma, kobo_submission_time
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        cursor = connection.cursor()
        cursor.executemany(insert_query, self.visits_to_insert)
        connection.commit()
        cursor.close()

        self.stats['successful'] = len(self.visits_to_insert)
        logger.info(f"Successfully inserted {self.stats['successful']} records")

    def copy_source_csv(self, source_path: Path):
        """Copy source CSV to import folder for reference."""
        import shutil
        shutil.copy2(source_path, self.source_csv_path)
        logger.info(f"Archived source CSV to {self.source_csv_path}")

    def write_error_logs(self):
        """Write unmatched records to CSV log files in this import's folder."""
        # Write unmatched farmers
        if self.unmatched_farmers:
            with open(self.unmatched_farmers_log, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['import_date', 'kobo_uuid', 'dni', 'producer_name_from_kobo',
                             'extensionist_code', 'visit_date', 'error_reason']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.unmatched_farmers)
            logger.info(f"Logged {len(self.unmatched_farmers)} unmatched farmers")

        # Write unmatched extensionists
        if self.unmatched_extensionists:
            with open(self.unmatched_extensionists_log, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['import_date', 'kobo_uuid', 'extensionist_code', 'dni',
                             'producer_name', 'visit_date', 'error_reason']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.unmatched_extensionists)
            logger.info(f"Logged {len(self.unmatched_extensionists)} unmatched extensionists")

    def write_summary(self, duration_seconds: float, source_csv_name: str):
        """Write import summary to both import-specific file and cumulative log."""
        summary_content = f"""{'='*60}
Import Run: {self.import_timestamp}
{'='*60}
Source CSV: {source_csv_name}
Import Folder: {self.import_folder_name}
{"[DRY RUN MODE]" if self.dry_run else ""}
{"[TEST MODE: " + str(self.test_rows) + " rows]" if self.test_rows else ""}
{'='*60}
Total records in CSV: {self.stats['total_records']}
Successfully imported: {self.stats['successful']}
Skipped (already exists): {self.stats['already_exists']}
Failed - farmer not found: {self.stats['farmer_not_found']}
Failed - extensionist not found: {self.stats['extensionist_not_found']}
Duration: {duration_seconds:.2f} seconds
{'='*60}
"""

        # Write to import-specific summary
        with open(self.import_summary_file, 'w', encoding='utf-8') as f:
            f.write(summary_content)

        # Append to cumulative log
        with open(CUMULATIVE_SUMMARY_LOG, 'a', encoding='utf-8') as f:
            f.write(f"\n{summary_content}")

        logger.info(f"Summary written to {self.import_dir}")

    def run(self):
        """Main import process."""
        start_time = datetime.now()

        try:
            # Get database connection
            connection = create_connection()

            # Load lookup data
            self.load_lookups(connection)

            # Get latest CSV
            csv_path = self.get_latest_csv()

            # Copy source CSV to import folder
            self.copy_source_csv(csv_path)

            # Read CSV with pandas (semicolon delimiter)
            # Force DNI to be read as string to preserve leading zeros
            logger.info("Reading CSV...")
            df = pd.read_csv(
                csv_path,
                sep=';',
                encoding='utf-8',
                dtype={'Insertar No de DNI productor': str}
            )

            # Apply test mode if specified
            if self.test_rows:
                logger.info(f"TEST MODE: Processing first {self.test_rows} rows")
                df = df.head(self.test_rows)

            self.stats['total_records'] = len(df)
            logger.info(f"Processing {self.stats['total_records']} records...")

            # Clean data
            df = self.clean_data(df)

            # Process each row
            for index, row in df.iterrows():
                insert_data = self.process_row(row, index)
                if insert_data:
                    self.visits_to_insert.append(insert_data)

                # Progress indicator
                if (index + 1) % 500 == 0:
                    logger.info(f"Processed {index + 1}/{self.stats['total_records']} rows...")

            # Batch insert all valid records
            self.batch_insert(connection)

            # Write error logs
            self.write_error_logs()

            # Close connection
            connection.close()

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Write summary
            self.write_summary(duration, csv_path.name)

            # Print summary to console
            print("\n" + "="*60)
            print("IMPORT SUMMARY")
            if self.dry_run:
                print("[DRY RUN MODE]")
            if self.test_rows:
                print(f"[TEST MODE: {self.test_rows} rows]")
            print("="*60)
            print(f"Import folder: {self.import_folder_name}")
            print(f"Total records: {self.stats['total_records']}")
            print(f"Successfully imported: {self.stats['successful']}")
            print(f"Already exists (skipped): {self.stats['already_exists']}")

            # Calculate unique missing farmers/extensionists
            unique_farmers = len(set(f['dni'] for f in self.unmatched_farmers))
            unique_extensionists = len(set(e['extensionist_code'] for e in self.unmatched_extensionists))

            print(f"Farmer not found: {self.stats['farmer_not_found']} visit records ({unique_farmers} unique farmers)")
            print(f"Extensionist not found: {self.stats['extensionist_not_found']} visit records ({unique_extensionists} unique extensionists)")
            print(f"Duration: {duration:.2f} seconds")
            print("="*60)

            if self.stats['farmer_not_found'] > 0:
                print(f"\n⚠️  Check {self.unmatched_farmers_log} for unmatched farmers")
            if self.stats['extensionist_not_found'] > 0:
                print(f"⚠️  Check {self.unmatched_extensionists_log} for unmatched extensionists")

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            raise


def main():
    parser = argparse.ArgumentParser(description='Import Kobo visits into database')
    parser.add_argument('--test', type=int, metavar='N', help='Test mode: import only first N rows')
    parser.add_argument('--dry-run', action='store_true', help='Simulate import without inserting data')

    args = parser.parse_args()

    importer = KoboImporter(dry_run=args.dry_run, test_rows=args.test)
    importer.run()


if __name__ == '__main__':
    main()
