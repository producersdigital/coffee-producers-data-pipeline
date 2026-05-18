"""
Norandino — Mapas de Predicción Agrícola
=========================================
Aplicación web para visualizar mapas interactivos de predicción
generados por CrossEurAsia para las parcelas de Norandino.
 
Modelos disponibles:
  1. Salud del Suelo     — 18 nutrientes por parcela (Mar 2026)
  2. Salud del Cultivo   — café y caña, índices NDVI/GNDVI/NDMI etc.
  3. Estimación de Rendimiento — (pendiente URL)
 
Uso local:
    streamlit run src/cea_api/scripts/norandino_mapas.py
"""
 
import streamlit as st
import requests
import pandas as pd
from pathlib import Path
import json
 
# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Norandino — Mapas Agrícolas",
    page_icon="🌱",
    layout="wide",
)
 
# ── Endpoints ─────────────────────────────────────────────────────────────────
SOIL_URL        = "https://ohob6203na.execute-api.ap-south-1.amazonaws.com/farm-soil-mar-2026"
CROP_HEALTH_URL = "https://aw48sjlnf3.execute-api.ap-south-1.amazonaws.com/s1"
 
# ── Traducción de nutrientes (Salud del Suelo) ────────────────────────────────
NUTRIENTES_ES = {
    "Ammoniacal Nitrogen":        "Nitrógeno Amoniacal",
    "Available Nitrogen":         "Nitrógeno Disponible",
    "Available Phosphorus Olsen": "Fósforo Disponible (Olsen)",
    "Available Potassium":        "Potasio Disponible",
    "Boron":                      "Boro",
    "Calcium Change":             "Cambio en Calcio",
    "Copper":                     "Cobre",
    "Effective CEC":              "CIC Efectiva",
    "Electrical Conduit":         "Conductividad Eléctrica",
    "Iron":                       "Hierro",
    "Magnesium Change":           "Cambio en Magnesio",
    "Manganese":                  "Manganeso",
    "Nitric Nitrogen":            "Nitrógeno Nítrico",
    "Organic Matter":             "Materia Orgánica",
    "Potassium Change":           "Cambio en Potasio",
    "Total Organic Carbon":       "Carbono Orgánico Total",
    "Zinc":                       "Zinc",
    "pH":                         "pH",
}
 
INDICES_ES = {
    "NDVI":  "NDVI — Salud del cultivo",
    "GNDVI": "GNDVI — Densidad del dosel",
    "NDMI":  "NDMI — Nivel de humedad",
    "SAVI":  "SAVI — Estrés de vegetación",
    "EVI":   "EVI — Vigor del cultivo",
    "NDRE":  "NDRE — Estado de nitrógeno",
    "CIRE":  "CIRE — Estado de clorofila",
}
 
def es_nutrient(name: str) -> str:
    return NUTRIENTES_ES.get(name, name)
 
def es_index(name: str) -> str:
    return INDICES_ES.get(name, name)
 
 
# ── Cargar parcelas desde CSV (sin DNIs) ──────────────────────────────────────
@st.cache_data(ttl=3600)
def cargar_parcelas_soil():
    """Load plot codes for soil health model from clean CSV."""
    # Try multiple paths — works both locally and on Streamlit Cloud
    search_paths = [
        Path(__file__).parent.parent / 'data' / 'cea_plot_codes.csv',
        Path(__file__).parent.parent.parent / 'src' / 'cea_api' / 'data' / 'cea_plot_codes.csv',
        Path('src/cea_api/data/cea_plot_codes.csv'),
    ]
    for csv_path in search_paths:
        try:
            if csv_path.exists():
                df = pd.read_csv(csv_path, dtype=str)
                codes = df['cea_code'].dropna().str.strip().tolist()
                if codes:
                    return codes
        except Exception:
            continue
    # Fallback — only shown if CSV not found
    return ["NORPIU0954", "NORCAJ2338", "NORLAM1829"]
 
 
@st.cache_data(ttl=1800)
def cargar_parcelas_crop_health():
    """Fetch available farm codes from Crop Health /farms endpoint."""
    try:
        r = requests.get(f"{CROP_HEALTH_URL}/farms", timeout=15)
        if r.status_code == 200:
            data = r.json()
            farms = data.get("farms", [])
            # Return list of dicts with farm code and crop
            return farms
    except Exception as e:
        st.warning(f"No se pudo cargar la lista de parcelas del API: {e}")
    return []
 
 
# ── API calls ─────────────────────────────────────────────────────────────────
def fetch_soil_maps(farm_id: str) -> dict | None:
    """Fetch 18 nutrient map URLs from Soil Health API."""
    try:
        r = requests.get(SOIL_URL, params={"farm_id": farm_id}, timeout=15)
        if r.status_code == 200:
            return r.json().get("maps")
    except Exception as e:
        st.error(f"Error conectando al API de Suelos: {e}")
    return None
 
 
def fetch_crop_latest(farm: str) -> dict | None:
    """Fetch latest crop health map."""
    try:
        r = requests.get(f"{CROP_HEALTH_URL}/map", params={"farm": farm}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        st.error(f"Error conectando al API de Cultivo: {e}")
    return None
 
 
def fetch_crop_history(farm: str) -> list:
    """Fetch all available crop health maps for a farm."""
    try:
        r = requests.get(f"{CROP_HEALTH_URL}/map",
                         params={"farm": farm, "mode": "history"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("maps", [])
    except Exception as e:
        st.error(f"Error obteniendo historial: {e}")
    return []
 
 
def fetch_crop_range(farm: str, start: str, end: str) -> list:
    """Fetch crop health maps within date range."""
    try:
        r = requests.get(f"{CROP_HEALTH_URL}/map",
                         params={"farm": farm, "mode": "range",
                                 "start_date": start, "end_date": end},
                         timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("maps", [])
    except Exception as e:
        st.error(f"Error obteniendo rango: {e}")
    return []
 
 
def render_map_html(url: str, height: int = 550) -> None:
    """Fetch HTML server-side and render inline — avoids S3 CORS download issue."""
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            st.components.v1.html(r.text, height=height, scrolling=True)
            st.caption("⏰ Este mapa expira en 1 hora. Recarga para obtener uno nuevo.")
        else:
            st.error(f"No se pudo cargar el mapa (error {r.status_code})")
    except Exception as e:
        st.error(f"Error cargando el mapa: {e}")
 
 
# ── Modelo 1: Salud del Suelo ─────────────────────────────────────────────────
def render_soil_health():
    st.caption("18 nutrientes del suelo analizados por satélite — Mar 2026")
    st.divider()
 
    col_left, col_right = st.columns([1, 3])
 
    with col_left:
        st.markdown("#### Parcela")
        parcelas = cargar_parcelas_soil()
        codigo = st.selectbox("Código:", parcelas, key="soil_code")
 
        if st.button("Cargar mapas", type="primary",
                     use_container_width=True, key="soil_load"):
            with st.spinner("Conectando con CrossEurAsia..."):
                maps = fetch_soil_maps(codigo)
            if maps:
                st.session_state["soil_maps"]  = maps
                st.session_state["soil_farm"]  = codigo
                st.success(f"✅ {len(maps)} nutrientes disponibles")
            else:
                st.session_state["soil_maps"] = None
                st.warning("No hay datos para esta parcela.")
 
        if (st.session_state.get("soil_maps") and
                st.session_state.get("soil_farm") == codigo):
            maps = st.session_state["soil_maps"]
            names_en = list(maps.keys())
            names_es = [es_nutrient(n) for n in names_en]
 
            st.markdown("#### Nutriente")
            selected_es = st.radio("Selecciona:", names_es,
                                   label_visibility="collapsed",
                                   key="soil_nutrient")
            idx = names_es.index(selected_es)
            st.session_state["soil_selected"] = names_en[idx]
 
    with col_right:
        maps   = st.session_state.get("soil_maps")
        sel    = st.session_state.get("soil_selected")
        farm   = st.session_state.get("soil_farm")
 
        if maps and sel and farm == codigo:
            url = maps.get(sel)
            if url:
                st.markdown(f"**{es_nutrient(sel)}** — Parcela `{codigo}`")
                render_map_html(url)
        else:
            _empty_state()
 
 
# ── Modelo 2: Salud del Cultivo ───────────────────────────────────────────────
def render_crop_health():
    st.caption("Índices NDVI · GNDVI · NDMI · SAVI · EVI · NDRE · CIRE — café y caña")
    st.divider()
 
    col_left, col_right = st.columns([1, 3])
 
    with col_left:
        st.markdown("#### Parcela")
 
        # Load farm list from API
        farms_data = cargar_parcelas_crop_health()
        if not farms_data:
            st.warning("No se pudo cargar la lista de parcelas del API.")
            return
 
        # Group by crop for display
        coffee_farms = [f["farm"] for f in farms_data if f.get("crop") == "coffee"]
        cane_farms   = [f["farm"] for f in farms_data if f.get("crop") == "cane"]
        all_farms    = [f["farm"] for f in farms_data]
 
        crop_filter = st.radio("Cultivo:", ["☕ Café", "🌿 Caña", "Todos"],
                               horizontal=True, key="crop_filter")
        if crop_filter == "☕ Café":
            farm_list = coffee_farms
        elif crop_filter == "🌿 Caña":
            farm_list = cane_farms
        else:
            farm_list = all_farms
 
        farm_code = st.selectbox(
            f"Parcela ({len(farm_list)} disponibles):",
            farm_list, key="crop_farm"
        )
 
        # Mode selector
        st.markdown("#### Modo de consulta")
        mode = st.radio(
            "Modo:",
            ["Más reciente", "Historial completo", "Rango de fechas"],
            label_visibility="collapsed",
            key="crop_mode"
        )
 
        start_date = end_date = None
        if mode == "Rango de fechas":
            from datetime import date, timedelta
            col_a, col_b = st.columns(2)
            with col_a:
                start = st.date_input("Desde:", value=date.today() - timedelta(days=30),
                                      key="crop_start")
            with col_b:
                end = st.date_input("Hasta:", value=date.today(), key="crop_end")
            start_date = start.strftime("%Y%m%d")
            end_date   = end.strftime("%Y%m%d")
 
        if st.button("Cargar mapa", type="primary",
                     use_container_width=True, key="crop_load"):
            with st.spinner("Conectando con CrossEurAsia..."):
                if mode == "Más reciente":
                    result = fetch_crop_latest(farm_code)
                    if result and "url" in result:
                        st.session_state["crop_maps"]        = [result]
                        st.session_state["crop_farm_loaded"] = farm_code
                        st.success(f"✅ Mapa del {result.get('date', 'fecha desconocida')}")
                    else:
                        st.session_state["crop_maps"] = None
                        st.warning("No hay datos para esta parcela.")
 
                elif mode == "Historial completo":
                    maps = fetch_crop_history(farm_code)
                    if maps:
                        st.session_state["crop_maps"]        = maps
                        st.session_state["crop_farm_loaded"] = farm_code
                        st.success(f"✅ {len(maps)} mapas disponibles")
                    else:
                        st.session_state["crop_maps"] = None
                        st.warning("No hay historial para esta parcela.")
 
                else:  # Rango
                    maps = fetch_crop_range(farm_code, start_date, end_date)
                    if maps:
                        st.session_state["crop_maps"]        = maps
                        st.session_state["crop_farm_loaded"] = farm_code
                        st.success(f"✅ {len(maps)} mapas en el rango")
                    else:
                        st.session_state["crop_maps"] = None
                        st.warning("No hay mapas en ese rango de fechas.")
 
        # Date selector when multiple maps available
        if (st.session_state.get("crop_maps") and
                st.session_state.get("crop_farm_loaded") == farm_code and
                len(st.session_state["crop_maps"]) > 1):
            maps = st.session_state["crop_maps"]
            dates = [m.get("date", f"Mapa {i+1}") for i, m in enumerate(maps)]
            st.markdown("#### Fecha")
            selected_date = st.radio("Selecciona:", dates,
                                     label_visibility="collapsed",
                                     key="crop_date")
            idx = dates.index(selected_date)
            st.session_state["crop_selected_idx"] = idx
 
    with col_right:
        maps  = st.session_state.get("crop_maps")
        farm  = st.session_state.get("crop_farm_loaded")
        idx   = st.session_state.get("crop_selected_idx", 0)
 
        if maps and farm == farm_code:
            selected_map = maps[idx] if idx < len(maps) else maps[0]
            url  = selected_map.get("url")
            date = selected_map.get("date", "")
            crop = selected_map.get("crop", "")
 
            date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 else date
            st.markdown(f"**Salud del Cultivo** — Parcela `{farm_code}`")
            crop_es = {"coffee": "Café", "cane": "Caña"}.get(crop.lower() if crop else "", crop.title() if crop else "—")
            if date_fmt:
                st.caption(f"📅 Fecha: {date_fmt}  |  🌱 Cultivo: {crop_es}")
 
            if url:
                render_map_html(url)
        else:
            _empty_state()
 
 
# ── Helper: empty state placeholder ──────────────────────────────────────────
def _empty_state():
    st.markdown("""
    <div style='
        border: 2px dashed #ccc;
        border-radius: 12px;
        height: 400px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        color: #888;
        padding: 2rem;
    '>
        <div>
            <div style='font-size:2.5rem'>🗺️</div>
            <div style='margin-top:1rem; font-size:1.1rem'>
                Selecciona una parcela y haz clic en<br><strong>Cargar mapa</strong>
            </div>
            <div style='font-size:0.9rem; margin-top:0.5rem; color:#aaa;'>
                Mapas generados por CrossEurAsia con datos satelitales
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
 
 
# ── Main UI ───────────────────────────────────────────────────────────────────
def main():
    # Header with logo
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        logo_path = Path(__file__).parent.parent / 'assets' / 'logo_norandino.png'
        if logo_path.exists():
            st.image(str(logo_path), width=80)
        else:
            st.markdown("## 🌱")
    with col_title:
        st.markdown("# Norandino — Mapas de Predicción Agrícola")
        st.caption("Análisis satelital y machine learning por CrossEurAsia")
 
    st.divider()
 
    # Model selector
    modelo = st.selectbox(
        "Selecciona el modelo de predicción:",
        [
            "🌿 Salud del Suelo",
            "🌾 Salud del Cultivo",
            "📈 Estimación de Rendimiento",
        ],
        key="modelo"
    )
 
    if modelo == "🌿 Salud del Suelo":
        render_soil_health()
 
    elif modelo == "🌾 Salud del Cultivo":
        render_crop_health()
 
    elif modelo == "📈 Estimación de Rendimiento":
        st.info("⏳ Este modelo estará disponible próximamente (mayo 2026+).")
 
 
if __name__ == "__main__":
    main()