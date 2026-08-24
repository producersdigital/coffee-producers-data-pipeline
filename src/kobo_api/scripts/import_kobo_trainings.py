"""
Import Kobo Trainings ("Capacitaciones Norandino") into the SDL.
 
Repeat-group form -> two SDL tables:
    trainings              (parent, one row per event)
    training_participants  (unified: registered + non-registered attendees)
 
Matches the Visits idiom (src/kobo_api/scripts/import_kobo_visits.py): a KoboImporter
class, argparse (--dry-run / --test N / --file), lookup dicts for FK resolution,
error-CSV logging, a run summary. The download half mirrors the Visits
KoboCSVExporter, but pulls the XLSX export (data_url_xlsx) because a repeat-group
form's three sheets survive in XLSX and are lost/flattened in CSV.
 
Usage:
    python import_kobo_trainings.py                 # download latest from Kobo, load
    python import_kobo_trainings.py --dry-run       # download + process, no writes
    python import_kobo_trainings.py --test 50       # only first 50 trainings
    python import_kobo_trainings.py --file <path>   # skip download, use a local .xlsx
 
Requires in .env (same token as Visits):
    KOBO_API_TOKEN, KOBO_SERVER_URL (default https://eu.kobotoolbox.org)
"""
 
import argparse
import hashlib
import logging
import os
import re
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
 
import pandas as pd
 
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, '.env'), override=True)
except Exception:
    pass
from src.database.connection import create_connection
from src.utils.dni_cleaner import DNICleaner
 
# ── config ───────────────────────────────────────────────────────────────────
KOBO_API_DIR = project_root / "src" / "kobo_api"
EXPORTS_DIR = project_root / "data" / "kobo_exports"
LOGS_DIR = KOBO_API_DIR / "logs"
 
ASSET_UID = "aEhGgarqvLn9gqQ7CxyXS8"     # Capacitaciones Norandino
EXPORT_NAME = "Trainings"                 # named XLSX export created once in the Kobo UI
SOURCE_ORG_CODE = "NO"                    # Norandino -> org_id via producer_organizations
 
# Known test/junk submissions to drop at load (form trials, not real trainings).
# Compared case-insensitively against Nombre_Tecnico. Add codes here as they appear.
TEST_CODES = {"testeopd", "croppietest"}
 
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)
 
 
# =============================================================================
# DOWNLOAD  (mirrors Visits' KoboCSVExporter, but grabs data_url_xlsx)
# =============================================================================
class KoboXLSXExporter:
    def __init__(self):
        self.server_url = os.getenv('KOBO_SERVER_URL', 'https://eu.kobotoolbox.org')
        self.api_token = os.getenv('KOBO_API_TOKEN')
        if not self.api_token:
            raise ValueError("KOBO_API_TOKEN not found in environment (.env)")
        self.headers = {'Authorization': f'Token {self.api_token}'}
 
    def _export_settings(self, asset_uid: str) -> list:
        import requests
        url = f"{self.server_url}/api/v2/assets/{asset_uid}/export-settings/"
        r = requests.get(url, headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json().get('results', [])
 
    def download(self, asset_uid: str = ASSET_UID, export_name: str = EXPORT_NAME) -> Path:
        import requests
        settings = self._export_settings(asset_uid)
        if not settings:
            raise RuntimeError(
                "No named exports found. In the Kobo UI (form 'Capacitaciones Norandino'): "
                "DATA > Downloads > format XLSX, check 'Include labels', keep repeat groups as "
                f"separate sheets, then Save selection as '{export_name}'."
            )
        chosen = next((s for s in settings if s.get('name') == export_name), None)
        if chosen is None:
            names = ", ".join(s.get('name', '?') for s in settings)
            raise RuntimeError(f"Export '{export_name}' not found. Available: {names}")
        xlsx_url = chosen.get('data_url_xlsx')
        if not xlsx_url:
            raise RuntimeError(f"Export '{export_name}' has no XLSX URL (was it saved as CSV?).")
        logger.info(f"Downloading XLSX export '{export_name}'...")
        r = requests.get(xlsx_url, headers=self.headers, timeout=300)
        r.raise_for_status()
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = EXPORTS_DIR / f"kobo_trainings_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        out.write_bytes(r.content)
        logger.info(f"Saved {out.name} ({out.stat().st_size/1024/1024:.2f} MB)")
        return out
 
 
# =============================================================================
# HELPERS
# =============================================================================
def _val(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    return None if s in ('', 'nan', 'NaN', 'None', 'NaT') else s
 
 
def _int(v):
    try:
        f = float(v)
        return None if pd.isna(f) else int(f)
    except (ValueError, TypeError):
        return None
 
 
def _num(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None
 
 
def _date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        # Birth-date strings are MIXED d/m/Y and m/d/Y across devices. Parsing per value
        # with dayfirst=True lets pandas fall back to m/d/Y when day-first is impossible
        # (e.g. '08/28/1976'), so both unambiguous forms parse correctly; only genuinely
        # ambiguous values (both parts <=12) default to day-first. Warning is expected noise.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            d = pd.to_datetime(v, errors='coerce', dayfirst=True)
        return None if pd.isna(d) else d.date()
    except Exception:
        return None
 
 
def _dt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            d = pd.to_datetime(v, errors='coerce', dayfirst=True)
        return None if pd.isna(d) else d.to_pydatetime()
    except Exception:
        return None
 
 
def _bool(v):
    s = _val(v)
    if s is None:
        return None
    return 1 if s.strip().lower() in ('si', 'sí', 'yes', 'true', '1') else 0
 
 
def _hash(*parts) -> str:
    return hashlib.sha256('|'.join('' if p is None else str(p) for p in parts).encode()).hexdigest()
 
 
def _coalesce(row: pd.Series, cols: List[str]):
    for c in cols:
        if c in row.index:
            v = _val(row[c])
            if v is not None:
                return v
    return None
 
 
# =============================================================================
# IMPORTER
# =============================================================================
class KoboImporter:
    # sheet detection
    def __init__(self, dry_run: bool = False, test_rows: Optional[int] = None,
                 file: Optional[Path] = None):
        self.dry_run = dry_run
        self.test_rows = test_rows
        self.file = file
        self.farmers_lookup: Dict[str, int] = {}
        self.extensionists_lookup: Dict[str, int] = {}
        self.org_id: Optional[int] = None
        self.existing_uuids: Set[str] = set()
        self.existing_part_hashes: Set[str] = set()
        self.trainings_rows: List[tuple] = []
        self.participant_rows: List[tuple] = []
        self.stats = {'trainings': 0, 'participants': 0, 'ext_unmatched': 0,
                      'dup_dropped': 0, 'test_dropped': 0,
                      'farmer_matched': 0, 'farmer_unmatched': 0, 'dni_blank': 0}
        self.unmatched_ext: List[dict] = []
 
    # ---- lookups -----------------------------------------------------------
    def load_lookups(self, conn):
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT org_id FROM producer_organizations WHERE org_code = %s", (SOURCE_ORG_CODE,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"org_code '{SOURCE_ORG_CODE}' not in producer_organizations")
        self.org_id = row['org_id']
 
        cur.execute("SELECT farmer_id, national_id FROM farmers WHERE national_id IS NOT NULL")
        self.farmers_lookup = {str(r['national_id']).strip(): r['farmer_id'] for r in cur.fetchall()}
 
        cur.execute("SELECT extensionist_id, extensionist_code FROM extensionists")
        self.extensionists_lookup = {str(r['extensionist_code']).strip(): r['extensionist_id']
                                     for r in cur.fetchall()}
 
        cur.execute("SELECT kobo_uuid FROM trainings")
        self.existing_uuids = {r['kobo_uuid'] for r in cur.fetchall()}
        cur.execute("SELECT row_hash FROM training_participants")
        self.existing_part_hashes = {r['row_hash'] for r in cur.fetchall()}
        cur.close()
        logger.info(f"Lookups: org_id={self.org_id}, farmers={len(self.farmers_lookup):,}, "
                    f"extensionists={len(self.extensionists_lookup)}, "
                    f"existing trainings={len(self.existing_uuids):,}")
 
    # ---- read the 3 sheets -------------------------------------------------
    def read_sheets(self, path: Path):
        xls = pd.ExcelFile(path)
        names = xls.sheet_names
        nonreg = next((s for s in names if 'no_registrados' in s.lower()), None)
        reg = next((s for s in names if 'registrados' in s.lower() and 'no_registrados' not in s.lower()), None)
        parent = next((s for s in names if s not in (reg, nonreg)), names[0])
        p = pd.read_excel(xls, sheet_name=parent, dtype=object)
        r = pd.read_excel(xls, sheet_name=reg, dtype=object) if reg else pd.DataFrame()
        n = pd.read_excel(xls, sheet_name=nonreg, dtype=object) if nonreg else pd.DataFrame()
        p.columns = [str(c).strip() for c in p.columns]
        r.columns = [str(c).strip() for c in r.columns]
        n.columns = [str(c).strip() for c in n.columns]
        logger.info(f"Sheets: parent='{parent}' ({len(p)}), registered='{reg}' ({len(r)}), "
                    f"non-registered='{nonreg}' ({len(n)})")
        return p, r, n
 
    # ---- parent trainings --------------------------------------------------
    @staticmethod
    def _canonical_uuid(u: str) -> str:
        """Kobo flags duplicate submissions with a DUPLICATE-<ts>-<n>-<asset>-<uuid>
        _uuid. Return the trailing real UUID so all copies of one submission share a
        key; a normal _uuid is returned unchanged."""
        m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                      str(u))
        return m.group(0) if m else str(u)
 
    def _dedupe_trainings(self, p: pd.DataFrame) -> pd.DataFrame:
        """Collapse Kobo-flagged duplicate submissions to one row per real training.
        Keep the most complete copy (most non-null fields), tie-break on the latest
        _submission_time, then lowest _id for determinism. Kobo clones the repeat
        children too, so dropping the extra parent (and excluding its participants via
        the `valid` set) removes the duplicated participants along with it."""
        p = p.copy()
        p['_canon'] = p['_uuid'].map(self._canonical_uuid)
        dup_groups = p['_canon'].duplicated(keep=False)
        if not dup_groups.any():
            return p.drop(columns='_canon')
        biz_cols = [c for c in p.columns if not c.startswith('_')]
        p['_nonnull'] = p[biz_cols].notna().sum(axis=1)
        p['_st'] = pd.to_datetime(p['_submission_time'], errors='coerce')
        # richest first, then newest, then lowest _id
        ordered = p.sort_values(
            ['_canon', '_nonnull', '_st', '_id'],
            ascending=[True, False, False, True])
        kept = ordered.drop_duplicates('_canon', keep='first')
        dropped = len(p) - len(kept)
        if dropped:
            self.stats['dup_dropped'] = dropped
            logger.info(f"De-duplicated {dropped} Kobo-flagged duplicate training "
                        f"copy(ies); kept the most complete of each")
        return kept.drop(columns=['_canon', '_nonnull', '_st'])
 
    def process_trainings(self, p: pd.DataFrame) -> Set[str]:
        p = self._dedupe_trainings(p)
        if self.test_rows:
            p = p.head(self.test_rows)
        loaded_submissions: Set[str] = set()
        for _, row in p.iterrows():
            raw_uuid = _val(row.get('_uuid'))
            if raw_uuid is None:
                continue
            tech = _val(row.get('Nombre_Tecnico'))
            # drop known test/junk submissions (form trials, not real trainings).
            # Done before the valid-set add, so their participants are excluded too.
            if tech and tech.strip().lower() in TEST_CODES:
                self.stats['test_dropped'] += 1
                continue
            uuid = self._canonical_uuid(raw_uuid)   # store the clean 36-char uuid as the key
            submission_id = _val(row.get('_id'))
            loaded_submissions.add(submission_id)
 
            # store the technician code as-is (always); report codes not yet in
            # extensionists so they can be added (name then appears with no re-import)
            if tech and tech not in self.extensionists_lookup:
                self.stats['ext_unmatched'] += 1
                self.unmatched_ext.append({'kobo_uuid': uuid, 'extensionist_code': tech})
 
            fields = (
                uuid, submission_id, self.org_id, tech,
                _val(row.get('ID registro')), _date(row.get('Fecha del evento')),
                _val(row.get('Ciclo')),
                _num(row.get('_Coordenadas_latitude')), _num(row.get('_Coordenadas_longitude')),
                _num(row.get('_Coordenadas_altitude')),
                _val(row.get('Tipo de evento')), _val(row.get('Objetivo')),
                _val(row.get('Tipo de Capacitación')), _val(row.get('Seleccionar gerencia')),
                _val(row.get('Seleccionar area')), _val(row.get('Seleccionar tema')),
                _val(row.get('Nombre de la capacitacion o reunion')),
                _val(row.get('Seleccionar producto')), _val(row.get('Institución')),
                _val(row.get('Responsable:')), _val(row.get('Duracion:')),
                _val(row.get('Dirigida a:')), _val(row.get('Modalidad:')), _val(row.get('Lugar')),
                _bool(row.get('Registrar participantes a traves de listas?')),
                _bool(row.get('Registrar participantes no Registrados en Sistema?')),
                _int(row.get('hombres')), _int(row.get('mujeres')), _int(row.get('total_participantes')),
                _val(row.get('Conclusiones - Resultados')), _val(row.get('Observaciones generales')),
                _val(row.get('Firma del Responsable_URL')), _val(row.get('Tomar fotografia del evento_URL')),
                _dt(row.get('_submission_time')),
            )
            row_hash = _hash(*fields)
            self.trainings_rows.append(fields + (row_hash,))
        self.stats['trainings'] = len(self.trainings_rows)
        return loaded_submissions
 
    # ---- participants (unified) -------------------------------------------
    def _clean_dni(self, raw) -> Optional[str]:
        s = _val(raw)
        if s is None:
            return None
        cleaned = DNICleaner(verbose=False).clean(pd.Series([s])).iloc[0]
        cleaned = _val(cleaned)
        if cleaned is None or set(cleaned) == {'0'} or len(cleaned) < 7:
            return None
        return cleaned
 
    def _emit_participant(self, submission_id, is_registered, dni, profile, full_name,
                          organization, appagrop, area, reference, gender, birth_date, signature):
        farmer_id = self.farmers_lookup.get(dni) if dni else None
        if dni:
            if farmer_id:
                self.stats['farmer_matched'] += 1
            else:
                self.stats['farmer_unmatched'] += 1
        else:
            self.stats['dni_blank'] += 1
        row_hash = _hash(submission_id, is_registered, dni, profile, full_name,
                         organization, gender, birth_date)
        self.participant_rows.append((
            submission_id, is_registered, farmer_id, dni, profile, full_name,
            organization, appagrop, area, reference, gender, birth_date, signature, row_hash))
 
    def process_participants(self, r: pd.DataFrame, n: pd.DataFrame, valid: Set[str]):
        # registered — coalesce per-profile columns
        NAME = ['nombre_completo_int', 'nombre_completo_socio', 'nombre_completo_personal', 'nombre_completo_reforestacion']
        ORG = ['organizacion_int', 'organizacion_socio', 'organizacion_personal', 'organizacion_reforestacion']
        GEN = ['genero_int', 'genero_socio', 'genero_personal', 'genero_reforestacion']
        BIRTH = ['fecha_nacimiento_int', 'fecha_nacimiento_socio', 'fecha_nacimiento_personal', 'fecha_nacimiento_reforestacion']
        for _, row in r.iterrows():
            sub = _val(row.get('_submission__id'))
            if sub not in valid:
                continue
            self._emit_participant(
                sub, 1, self._clean_dni(row.get('DNI Participante')),
                _val(row.get('Perfil de participante')), _coalesce(row, NAME), _coalesce(row, ORG),
                _coalesce(row, ['appagrop_socio', 'appagrop_reforestacion']),
                _val(row.get('area_personal')), _val(row.get('referencia_int')),
                _coalesce(row, GEN), _date(_coalesce(row, BIRTH)),
                _val(row.get('Firma participante_URL')))
        # non-registered — plain single columns
        for _, row in n.iterrows():
            sub = _val(row.get('_submission__id'))
            if sub not in valid:
                continue
            self._emit_participant(
                sub, 0, self._clean_dni(row.get('DNI Participante')),
                _val(row.get('Perfil de participante')), _val(row.get('Nombre Completo:')),
                _val(row.get('Organizacion:')), None, None, None,
                _val(row.get('Genero')), _date(row.get('Fecha de nacimiento:')),
                _val(row.get('Firma participante_URL')))
        self.stats['participants'] = len(self.participant_rows)
 
    # ---- writes ------------------------------------------------------------
    def _insert_trainings(self, conn):
        new = [t for t in self.trainings_rows if t[0] not in self.existing_uuids]
        if self.dry_run:
            logger.info(f"[DRY RUN] trainings: {len(new)} new / {len(self.trainings_rows)-len(new)} existing")
            return
        sql = """
            INSERT INTO trainings (
                kobo_uuid, kobo_submission_id, org_id, extensionist_code,
                registration_id, event_date, cycle, latitude, longitude, altitude,
                event_type, objective, training_type, management_area, area, topic,
                training_name, product, institution, responsible, duration, directed_to,
                modality, place, has_registered_list, has_nonregistered_list,
                reported_men, reported_women, reported_total, conclusions, observations,
                signature_url, photo_url, submission_time, row_hash
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                extensionist_code=VALUES(extensionist_code), event_date=VALUES(event_date),
                reported_men=VALUES(reported_men), reported_women=VALUES(reported_women),
                reported_total=VALUES(reported_total), conclusions=VALUES(conclusions),
                observations=VALUES(observations), row_hash=VALUES(row_hash)
        """
        cur = conn.cursor()
        cur.executemany(sql, self.trainings_rows)
        conn.commit()
        cur.close()
        logger.info(f"trainings: upserted {len(self.trainings_rows)} ({len(new)} new)")
 
    def _insert_participants(self, conn):
        new = [p for p in self.participant_rows if p[-1] not in self.existing_part_hashes]
        if self.dry_run:
            logger.info(f"[DRY RUN] participants: {len(new)} new / {len(self.participant_rows)-len(new)} existing")
            return
        sql = """
            INSERT IGNORE INTO training_participants (
                training_submission_id, is_registered, farmer_id, dni, profile,
                full_name, organization, appagrop, area, reference, gender,
                birth_date, signature_url, row_hash
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cur = conn.cursor()
        cur.executemany(sql, self.participant_rows)
        conn.commit()
        cur.close()
        logger.info(f"participants: inserted {len(new)} new (INSERT IGNORE)")
 
    def _write_error_log(self):
        if not self.unmatched_ext:
            return
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        path = LOGS_DIR / f"trainings_unmatched_ext_{datetime.now():%Y%m%d_%H%M%S}.csv"
        pd.DataFrame(self.unmatched_ext).to_csv(path, index=False)
        logger.info(f"Wrote {len(self.unmatched_ext)} unmatched-extensionist rows -> {path.name}")
 
    # ---- orchestration -----------------------------------------------------
    def run(self):
        started = datetime.now()
        path = self.file or KoboXLSXExporter().download()
        logger.info(f"Reading {path.name}")
        p, r, n = self.read_sheets(path)
 
        conn = create_connection()
        if not conn:
            logger.error("No DB connection")
            return False
        try:
            self.load_lookups(conn)
            valid = self.process_trainings(p)
            self.process_participants(r, n, valid)
            self._insert_trainings(conn)
            self._insert_participants(conn)
            self._write_error_log()
        finally:
            conn.close()
 
        matched = self.stats['farmer_matched']
        with_dni = matched + self.stats['farmer_unmatched']
        pct = (matched / with_dni * 100) if with_dni else 0
        dur = (datetime.now() - started).total_seconds()
        print("\n" + "=" * 62)
        print(f"TRAININGS IMPORT {'(DRY RUN)' if self.dry_run else 'COMPLETE'}")
        print("=" * 62)
        print(f"  trainings              : {self.stats['trainings']:,}")
        print(f"  participants           : {self.stats['participants']:,}")
        print(f"  farmer match (w/ DNI)  : {matched:,}/{with_dni:,} ({pct:.1f}%)")
        print(f"  participants w/o DNI   : {self.stats['dni_blank']:,}")
        print(f"  extensionists unmatched: {self.stats['ext_unmatched']:,}")
        print(f"  duplicate copies dropped: {self.stats['dup_dropped']:,}")
        print(f"  test submissions dropped: {self.stats['test_dropped']:,}")
        print(f"  elapsed                : {dur:.1f}s")
        print("=" * 62)
        return True
 
 
def main():
    ap = argparse.ArgumentParser(description="Import Kobo Trainings into the SDL")
    ap.add_argument('--dry-run', action='store_true', help="Process without writing")
    ap.add_argument('--test', type=int, metavar='N', help="Only first N trainings")
    ap.add_argument('--file', type=str, help="Use a local .xlsx instead of downloading")
    args = ap.parse_args()
    importer = KoboImporter(dry_run=args.dry_run, test_rows=args.test,
                            file=Path(args.file) if args.file else None)
    ok = importer.run()
    sys.exit(0 if ok else 1)
 
 
if __name__ == '__main__':
    main()
 