"""
Estimations — Stage 1 Cleaning
==============================================================================
Cleans Norandino "Estimado de acopio" workbooks (one per campaign year) into
two normalized, SDL-ready CSVs:
 
    data/processed/collection_estimations.csv        — one row per producer-year
    data/processed/collection_estimation_crops.csv   — one row per producer-year-crop (long)
 
Why long-format crops:
    Each source file is WIDE across three crops (café / caña / cacao). Melting
    to long means adding a fourth crop later is a data change, not a schema
    migration, and the join to collection_transactions in the acopio dashboard
    is a single (year, farmer, crop) join instead of a per-crop column pick.
 
Design notes (the file drifts every year — nothing is positional-safe):
    * Header row is located by scanning for the 'Departamento' token, not a
      fixed offset.
    * Columns are mapped by REGEX against normalized header text. A required
      column that fails to map raises — we never silently load NULLs.
    * 'TOTAL GENERAL' grand-total rows (null DNI) are dropped, then reused as a
      control: the sum of loaded coffee kg must equal the file's own total row
      where present. This is the guardrail against a future column shift.
    * Panela changes units mid-history: 2021-2024 headers say 'QQ DE 50 KGS'
      (quintales), 2025-2026 say 'KG'. Verified against data: panela is a
      derived column = cane x 10%, exact to every row, so the QQ years are
      normalized to kg (x50). source_value/source_unit keep the audit trail.
    * DNIs are cleaned with the shared DNICleaner (float->int, strip apostrophe,
      zero-pad to 8) so '03212564' survives instead of becoming 3212564.0.
 
Run directly from inside this folder:
    python clean_estimations.py            # clean all years in data/raw/
    python clean_estimations.py --year 2026
 
Author: Daniela (assisted)
"""
 
import argparse
import hashlib
import re
import sys
from pathlib import Path
 
import pandas as pd
 
# ── project bootstrap (repo convention) ──────────────────────────────────────
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from src.utils.dni_cleaner import DNICleaner  # noqa: E402
 
# ── paths ────────────────────────────────────────────────────────────────────
MODULE_DIR = Path(__file__).parent.parent
RAW_DIR = MODULE_DIR / 'data' / 'raw'
PROCESSED_DIR = MODULE_DIR / 'data' / 'processed'
 
# ── header detection ─────────────────────────────────────────────────────────
HEADER_TOKEN = 'Departamento'   # present in every file's header row
MAX_HEADER_SCAN = 15
 
# ── column mapping ───────────────────────────────────────────────────────────
# canonical_field -> list of regex (matched against normalized header text).
# First matching header wins. required=True fields raise if unmapped.
_norm = lambda s: re.sub(r'\s+', ' ', str(s)).strip().lower()
 
HEADER_COLUMN_MAP = {
    # identity / org hierarchy
    'org_first_level':   (r'organizaci.n primer nivel',                 True),
    'org_coordination':  (r'.rgano de coordinaci.n',                    False),
    'org_base_internal': (r'base interna',                              False),
    'unit_code':         (r'^unidad$',                                  False),
    'sic_name':          (r'nombre sic',                                False),
    'caserio':           (r'caser.o',                                   False),
    'district':          (r'^distrito$',                                True),
    'province':          (r'^provincia$',                               True),
    'department':        (r'^departamento$',                            True),
    'farmer_identifier': (r'c.dula.*(n.mero|numero).*c.digo|del productor', True),
    'producer_name':     (r'nombre productor',                          True),
    'membership_status': (r'estatus de miembro',                        False),
    'member_since_year': (r'asociado desde',                            False),
    'farm_area_ha':          (r'.rea total de su unidad de producci.n \(has\)', False),
    'farm_area_certified_ha':(r'.rea total.*certificada',               False),
    # certification status — the "current year" column name embeds the year,
    # so match "status certificacion" NOT followed by "anterior"
    'cert_status':       (r'status certificacion(?!.*anterior)',        False),
    'cert_status_prior': (r'status certificacion.*anterior',            False),
}
 
# crop_code -> dict of the wide columns that belong to that crop.
# volume regexes accept both the old ('Volumen Producción cultivo X') and the
# new ('ESTIMADO X') header wordings.
CROP_SPECS = {
    'COFFEE': {
        'product_form': 'PERGAMINO',
        'area_total':      r'area cultivo caf. ha',
        'area_production': r'.rea cultivo caf. producci.n',
        'area_growth':     r'.rea cultivo caf. crecimiento',
        'volume':          r'(volumen producci.n cultivo caf.|estimado caf. pergamino)',
    },
    'SUGARCANE': {
        'product_form': 'CANE',
        'area_total':      r'area cultivo ca.a ha',
        'area_production': r'.rea cultivo ca.a producci.n',
        'area_growth':     r'.rea cultivo ca.a crecimiento',
        'volume':          r'(volumen producci.n cultivo ca.a de azucar|estimado ca.a azucar)',
        # panela is a derived product on the cane row (cane x 10%)
        'derived_product': 'PANELA',
        'derived_volume':  r'(volumen producci.n panela|estimado panela)',
    },
    'CACAO': {
        'product_form': 'DRY_BEAN',
        'area_total':      r'area cultivo cacao ha',
        'area_production': r'.rea cultivo cacao producci.n',
        'area_growth':     r'.rea cultivo cacao crecimiento',
        'volume':          r'(volumen producci.n cultivo cacao kg seco|estimado cacao seco)',
    },
}
 
QQ_TO_KG = 50.0   # a quintal of panela = 50 kg (per the header wording)
 
 
# =============================================================================
# HELPERS
# =============================================================================
def _find_header_row(path: Path) -> int:
    raw = pd.read_excel(path, sheet_name=0, header=None,
                        nrows=MAX_HEADER_SCAN, dtype=object)
    for i, row in raw.iterrows():
        if any(str(v).strip() == HEADER_TOKEN for v in row):
            return i
    raise ValueError(f"Header row (containing '{HEADER_TOKEN}') not found in {path.name}")
 
 
def _year_from_name(path: Path) -> int:
    m = re.search(r'(20\d{2})', path.name)
    if not m:
        raise ValueError(f"Cannot infer year from filename: {path.name}")
    return int(m.group(1))
 
 
def _match_column(norm_headers: dict, pattern: str):
    """Return the ORIGINAL header string whose normalized form matches, else None."""
    rx = re.compile(pattern)
    for norm, original in norm_headers.items():
        if rx.search(norm):
            return original
    return None
 
 
def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce')
 
 
def _row_hash(*parts) -> str:
    payload = '|'.join('' if p is None else str(p) for p in parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
 
 
def _clean_text(series: pd.Series) -> pd.Series:
    s = series.astype('string').str.strip()
    return s.replace({'nan': pd.NA, 'None': pd.NA, 'NaN': pd.NA, '': pd.NA})
 
 
# =============================================================================
# LOAD & MAP ONE FILE
# =============================================================================
def _read_file(path: Path):
    """Return (dataframe, {canonical_field: original_header}) for one workbook."""
    hrow = _find_header_row(path)
    df = pd.read_excel(path, sheet_name=0, header=hrow, dtype=object).dropna(how='all')
    df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]
 
    norm_headers = {}
    for c in df.columns:
        norm_headers.setdefault(_norm(c), c)   # first occurrence wins (handles '.1' dupes)
 
    mapping = {}
    missing_required = []
    for field, (pattern, required) in HEADER_COLUMN_MAP.items():
        col = _match_column(norm_headers, pattern)
        if col is not None:
            mapping[field] = col
        elif required:
            missing_required.append((field, pattern))
    if missing_required:
        raise ValueError(
            f"{path.name}: required columns unmapped -> "
            + ", ".join(f for f, _ in missing_required)
        )
 
    # crop columns
    crop_mapping = {}
    for crop, spec in CROP_SPECS.items():
        cm = {}
        for key in ('area_total', 'area_production', 'area_growth', 'volume', 'derived_volume'):
            if key in spec:
                cm[key] = _match_column(norm_headers, spec[key])
        crop_mapping[crop] = cm
 
    # drop TOTAL GENERAL grand-total rows; keep them for the control check
    org_col = mapping['org_first_level']
    is_total = df[org_col].astype(str).str.upper().str.contains('TOTAL', na=False)
    total_rows = df[is_total].copy()
    data = df[~is_total].copy()
    return data, mapping, crop_mapping, total_rows
 
 
# =============================================================================
# BUILD NORMALIZED RECORDS
# =============================================================================
def _build_header(data: pd.DataFrame, mapping: dict, year: int, source_file: str) -> pd.DataFrame:
    out = pd.DataFrame()
    out['estimation_year'] = year
    out['farmer_identifier'] = DNICleaner(verbose=False).clean(
        data[mapping['farmer_identifier']], column_name=f'DNI {year}'
    )
    text_fields = ['producer_name', 'org_first_level', 'org_coordination',
                   'org_base_internal', 'unit_code', 'sic_name', 'caserio',
                   'district', 'province', 'department', 'membership_status',
                   'cert_status', 'cert_status_prior']
    for f in text_fields:
        out[f] = _clean_text(data[mapping[f]]) if f in mapping else pd.NA
    out['member_since_year'] = _num(data[mapping['member_since_year']]) if 'member_since_year' in mapping else pd.NA
    out['farm_area_ha'] = _num(data[mapping['farm_area_ha']]) if 'farm_area_ha' in mapping else pd.NA
    out['farm_area_certified_ha'] = _num(data[mapping['farm_area_certified_ha']]) if 'farm_area_certified_ha' in mapping else pd.NA
    out['source_file'] = source_file
 
    out = out[out['farmer_identifier'] != '']
    out['estimation_year'] = year
    out['row_hash'] = out.apply(lambda r: _row_hash(
        r['estimation_year'], r['farmer_identifier'], r['producer_name'],
        r['org_first_level'], r['org_coordination'], r['org_base_internal'],
        r['district'], r['province'], r['department'], r['membership_status'],
        r['member_since_year'], r['farm_area_ha'], r['farm_area_certified_ha'],
        r['cert_status'], r['cert_status_prior']), axis=1)
    return out.reset_index(drop=True)
 
 
def _build_crops(data: pd.DataFrame, mapping: dict, crop_mapping: dict,
                 year: int, source_file: str) -> pd.DataFrame:
    dni = DNICleaner(verbose=False).clean(data[mapping['farmer_identifier']])
    records = []
    for crop, spec in CROP_SPECS.items():
        cm = crop_mapping[crop]
        vol_col = cm.get('volume')
        if vol_col is None:
            continue
        vol = _num(data[vol_col])
 
        area_total = _num(data[cm['area_total']]) if cm.get('area_total') else pd.Series(pd.NA, index=data.index)
        area_prod = _num(data[cm['area_production']]) if cm.get('area_production') else pd.Series(pd.NA, index=data.index)
        area_grow = _num(data[cm['area_growth']]) if cm.get('area_growth') else pd.Series(pd.NA, index=data.index)
 
        # derived product (panela on the cane row) + its unit normalization
        derived_product = spec.get('derived_product')
        dcol = cm.get('derived_volume')
        if dcol is not None:
            is_qq = 'qq' in _norm(dcol)
            factor = QQ_TO_KG if is_qq else 1.0
            derived_src = _num(data[dcol])
            derived_kg = derived_src * factor
            derived_unit = 'QQ_50KG' if is_qq else 'KG'
        else:
            derived_src = derived_kg = pd.Series(pd.NA, index=data.index)
            derived_unit = None
 
        block = pd.DataFrame({
            'estimation_year': year,
            'farmer_identifier': dni,
            'crop_code': crop,
            'product_form': spec['product_form'],
            'area_total_ha': area_total,
            'area_production_ha': area_prod,
            'area_growth_ha': area_grow,
            'estimated_volume_kg': vol,            # coffee/cacao/cane already kg
            'source_value': vol,
            'source_unit': 'KG',
            'derived_product': derived_product,
            'derived_volume_kg': derived_kg,
            'derived_source_value': derived_src,
            'derived_source_unit': derived_unit,
            'source_file': source_file,
        })
        records.append(block)
 
    crops = pd.concat(records, ignore_index=True)
    crops = crops[crops['farmer_identifier'] != '']
    # keep only crop rows that carry any signal (volume or area present)
    signal = (_num(crops['estimated_volume_kg']).fillna(0) != 0) | \
             (_num(crops['area_total_ha']).fillna(0) != 0) | \
             (_num(crops['derived_volume_kg']).fillna(0) != 0)
    crops = crops[signal].copy()
 
    crops['row_hash'] = crops.apply(lambda r: _row_hash(
        r['estimation_year'], r['farmer_identifier'], r['crop_code'],
        r['area_total_ha'], r['area_production_ha'], r['area_growth_ha'],
        r['estimated_volume_kg'], r['derived_volume_kg'],
        r['source_value'], r['source_unit']), axis=1)
    return crops.reset_index(drop=True)
 
 
# =============================================================================
# VALIDATION
# =============================================================================
def _validate_control_total(crops_year: pd.DataFrame, total_rows: pd.DataFrame,
                            mapping: dict, crop_mapping: dict, year: int):
    """Assert loaded coffee kg == file's own TOTAL GENERAL coffee kg (if present)."""
    vol_col = crop_mapping['COFFEE'].get('volume')
    if total_rows.empty or vol_col is None:
        return None
    control = _num(total_rows[vol_col]).sum()
    loaded = crops_year.loc[crops_year['crop_code'] == 'COFFEE', 'estimated_volume_kg'].sum()
    diff = abs(control - loaded)
    ok = diff < 1.0
    flag = '✅' if ok else '❌'
    print(f"    {flag} control check {year}: file total {control:,.1f} kg vs "
          f"loaded {loaded:,.1f} kg (Δ {diff:,.2f})")
    return ok
 
 
# =============================================================================
# ORCHESTRATOR
# =============================================================================
def clean_estimations(years=None) -> bool:
    raw_files = sorted(RAW_DIR.glob('*.xlsx'))
    if years:
        raw_files = [f for f in raw_files if _year_from_name(f) in set(years)]
    if not raw_files:
        print(f"  ❌ No matching .xlsx files in {RAW_DIR}")
        return False
 
    print("=" * 62)
    print("ESTIMATIONS — STAGE 1 CLEANING")
    print("=" * 62)
 
    all_headers, all_crops, control_ok = [], [], True
    for path in raw_files:
        year = _year_from_name(path)
        print(f"\n── {path.name} (year {year}) {'─' * 10}")
        data, mapping, crop_mapping, total_rows = _read_file(path)
        print(f"    ℹ️  {len(data):,} producer rows "
              f"({len(total_rows)} total-row dropped)")
 
        headers = _build_header(data, mapping, year, path.name)
        crops = _build_crops(data, mapping, crop_mapping, year, path.name)
 
        # uniqueness guard (should hold after dropping TOTAL rows)
        dup = headers['farmer_identifier'].duplicated().sum()
        if dup:
            print(f"    ⚠️  {dup} duplicate farmer_identifier within {year} — keeping first")
            headers = headers.drop_duplicates('farmer_identifier', keep='first')
            crops = crops.drop_duplicates(['farmer_identifier', 'crop_code'], keep='first')
 
        ok = _validate_control_total(crops, total_rows, mapping, crop_mapping, year)
        control_ok = control_ok and (ok is not False)
 
        n_coffee = (crops['crop_code'] == 'COFFEE').sum()
        print(f"    ✅ {len(headers):,} header rows, {len(crops):,} crop rows "
              f"({n_coffee:,} coffee)")
        all_headers.append(headers)
        all_crops.append(crops)
 
    headers_all = pd.concat(all_headers, ignore_index=True)
    crops_all = pd.concat(all_crops, ignore_index=True)
 
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    hpath = PROCESSED_DIR / 'collection_estimations.csv'
    cpath = PROCESSED_DIR / 'collection_estimation_crops.csv'
    headers_all.to_csv(hpath, index=False)
    crops_all.to_csv(cpath, index=False)
 
    print("\n" + "=" * 62)
    print("SUMMARY")
    print("=" * 62)
    print(f"  Header rows : {len(headers_all):,}  -> {hpath.relative_to(MODULE_DIR)}")
    print(f"  Crop rows   : {len(crops_all):,}  -> {cpath.relative_to(MODULE_DIR)}")
    print("\n  Coffee estimated kg by year:")
    piv = (crops_all[crops_all['crop_code'] == 'COFFEE']
           .groupby('estimation_year')['estimated_volume_kg'].sum())
    for y, v in piv.items():
        print(f"    {y}: {v:,.0f} kg")
    print(f"\n  Control totals reconciled: {'✅ all pass' if control_ok else '❌ MISMATCH — review above'}")
    print("=" * 62)
    return control_ok
 
 
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Clean Norandino estimation workbooks.")
    ap.add_argument('--year', type=int, action='append',
                    help="Restrict to specific year(s); repeatable. Default: all.")
    args = ap.parse_args()
    ok = clean_estimations(years=args.year)
    sys.exit(0 if ok else 1)