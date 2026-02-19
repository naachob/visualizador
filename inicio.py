# -*- coding: utf-8 -*-
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import folium
from folium.features import DivIcon
from streamlit_folium import st_folium
import time
import random
import matplotlib
import matplotlib.pyplot as plt
import io
import base64
import matplotlib.dates as mdates

# Configurar backend no interactivo
matplotlib.use('Agg')

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Cuenca del Laja",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILOS CSS (RESPONSIVE INDUSTRIAL UI) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

    :root {
        --bg-core: #0e1117;
        --bg-card: #161b22;
        --bg-hover: #1f2630;
        --accent: #2e9eff;
        --success: #00d084;
        --warning: #fcb900;
        --danger: #ff4b4b;
        --text-primary: #f0f6fc;
        --text-secondary: #8b949e;
        --border: 1px solid rgba(240, 246, 252, 0.1);
    }

    /* Global Overrides */
    .stApp {
        background-color: var(--bg-core);
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3 { font-family: 'Inter', sans-serif; letter-spacing: -0.5px; }
    code, .mono { font-family: 'JetBrains Mono', monospace !important; }

    /* Custom Cards */
    .eng-card {
        background-color: var(--bg-card);
        border: var(--border);
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 16px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .eng-card:hover {
        border-color: var(--accent);
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }

    /* Metrics Styling */
    .metric-value {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 2.2rem;
        color: var(--text-primary);
        line-height: 1.1;
    }
    .metric-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        text-transform: uppercase;
        color: var(--text-secondary);
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    
    /* Progress Bar Override */
    .stProgress > div > div > div > div {
        background-color: var(--accent);
    }

    /* DGA Link Section */
    .dga-container {
        border: 1px solid #238636;
        background: rgba(35, 134, 54, 0.05);
        border-radius: 8px;
        padding: 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        flex-wrap: wrap; /* Permitir wrap en móvil */
    }
    .dga-link {
        background-color: #238636;
        color: white !important;
        text-decoration: none;
        padding: 12px 20px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.9rem;
        transition: background 0.2s;
        text-align: center;
        white-space: nowrap;
    }
    .dga-link:hover { background-color: #2ea043; }

    /* Welcome Box */
    .welcome-box {
        text-align: center;
        padding: 60px 20px;
        border: 1px dashed var(--text-secondary);
        border-radius: 12px;
        margin-top: 40px;
    }

    /* --- MOBILE OPTIMIZATIONS --- */
    @media (max-width: 768px) {
        /* Ajustar padding global */
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        
        /* Tarjetas más compactas */
        .eng-card { padding: 15px; margin-bottom: 12px; }
        .metric-value { font-size: 1.8rem; }
        
        /* Header adaptable */
        h1 { font-size: 1.5rem; }
        p { font-size: 0.85rem; }
        
        /* DGA Link Stacked */
        .dga-container { flex-direction: column; text-align: left; align-items: stretch; padding: 15px; }
        .dga-link { width: 100%; margin-top: 10px; }
        
        /* Ajustes de Mapa */
        iframe { border-radius: 8px; }
    }

    /* Hide Streamlit Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES ---
INFO_CENTRALES = {
    'HE EL TORO': {'id': 121, 'coords': [-37.2750, -71.4528]},
    'HE ANTUCO':  {'id': 116, 'coords': [-37.3098, -71.6267]},
    'HP ABANICO': {'id': 115, 'coords': [-37.3644, -71.4894]},
}
EFICIENCIAS = {
    'HE EL TORO': 4.5,
    'HE ANTUCO':  1.6,
    'HP ABANICO': 1.2,
}
CAPACIDADES_MW = {
    'HE EL TORO': 450,
    'HE ANTUCO':  320,
    'HP ABANICO': 90,
}
EMBALSES = {
    'HE EL TORO': 'Embalse El Toro',
    'HE ANTUCO':  'Canal Laja',
    'HP ABANICO': 'Embalse Abanico',
}

# --- SESIÓN DE REQUESTS ---
if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

# --- LÓGICA DE CONSULTA API ---
@st.cache_data(ttl=600)
def obtener_datos_central(id_central, nombre_central):
    url = "https://sipub.api.coordinador.cl/generacion-real/v3/findByDate"
    hoy = datetime.now()
    startDate = (hoy - timedelta(days=1)).strftime('%Y-%m-%d')
    endDate = (hoy + timedelta(days=1)).strftime('%Y-%m-%d')
    
    params = {
        'startDate': startDate,
        'endDate':   endDate,
        'user_key':  st.secrets["CEN_KEY"],
        'pageSize':  '50',
        'idCentral': str(id_central),
    }
    
    response = None
    for i in range(4):
        try:
            response = st.session_state.session.get(url, params=params, timeout=20)
            if response.status_code == 200:
                break
            if response.status_code in [429, 500, 502, 503, 504]:
                wait_time = 2 + (i * 3) + random.random()
                time.sleep(wait_time)
                continue
            return {'error': True, 'mensaje': f"HTTP {response.status_code}"}
        except Exception as e:
            if i < 3: 
                time.sleep(2)
                continue
            return {'error': True, 'mensaje': f'Timeout: {e}'}

    if response is None or response.status_code != 200:
        code = getattr(response,'status_code','?')
        msg = "Tráfico Alto (429)" if code == 429 else f"Falla CEN ({code})"
        return {'error': True, 'mensaje': msg}

    try:
        lista = response.json().get('data', [])
        lista.sort(key=lambda x: x.get('fecha_hora', ''), reverse=True)
        
        if not lista:
            return {'error': True, 'mensaje': 'Sin datos'}

        registros_cero, dato_activo = [], None
        for d in lista:
            gen = d.get('gen_real_mw', 0)
            fh  = d.get('fecha_hora', '')
            hs  = fh.split(' ')[1][:5] if ' ' in fh else fh
            
            if gen == 0:
                registros_cero.append(hs)
            else:
                dato_activo = d
                break 

        if dato_activo is None:
            dato_activo = lista[0]

        gen_mw    = dato_activo.get('gen_real_mw', 0)
        factor    = EFICIENCIAS.get(nombre_central, 1)
        caudal    = round(gen_mw / factor, 1) if factor > 0 else 0
        capacidad = CAPACIDADES_MW.get(nombre_central, 100)
        uso_pct   = round((gen_mw / capacidad) * 100, 1) if capacidad > 0 else 0

        status = 'online' if gen_mw > 0 else 'offline'

        return {
            'error': False,
            'nombre':         nombre_central,
            'embalse':        EMBALSES.get(nombre_central, '—'),
            'gen_mw':         gen_mw,
            'caudal':         caudal,
            'uso_pct':        uso_pct,
            'capacidad':      capacidad,
            'last_update':    dato_activo.get('fecha_hora', 'N/A').split(' ')[1][:5], 
            'status':         status,
            'raw_data':       dato_activo,
            'full_history':   lista 
        }
    except Exception as e:
        return {'error': True, 'mensaje': f'Parseo: {e}'}

# Variables de estado
if 'datos'     not in st.session_state: st.session_state.datos     = None
if 'ts_update' not in st.session_state: st.session_state.ts_update = None


# --- UI COMPONENTS ---

def render_header():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        <div>
            <h1 style='margin-bottom:0;'>MONITOR HIDRÁULICO</h1>
            <p style='color:var(--text-secondary); font-family:"JetBrains Mono"; font-size:0.9rem;'>
                CUENCA DEL LAJA
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("↻ ACTUALIZAR DATOS", type="primary", use_container_width=True):
            st.cache_data.clear()
            temp = []
            progress_text = st.empty()
            bar = st.progress(0)
            
            n = len(INFO_CENTRALES)
            for i, (nombre, info) in enumerate(INFO_CENTRALES.items()):
                progress_text.text(f"Consultando {nombre}...")
                bar.progress((i + 0.5) / n)
                if i > 0: time.sleep(1.5) 
                resultado = obtener_datos_central(info['id'], nombre)
                temp.append({'nombre': nombre, 'info': info, 'datos': resultado})
            
            bar.progress(1.0)
            time.sleep(0.2)
            bar.empty()
            progress_text.empty()
            
            st.session_state.datos = temp
            st.session_state.ts_update = datetime.now().strftime("%H:%M:%S")
            st.rerun()
            
        if st.session_state.ts_update:
            st.caption(f"Última sync: {st.session_state.ts_update}")

def render_kpi_card(item):
    """Renderiza tarjeta de métricas con estilo industrial."""
    res = item['datos']
    if res.get('error'):
        st.markdown(f"""
        <div class="eng-card" style="border-color:var(--danger);">
            <div class="metric-label" style="color:var(--danger);">{res.get('nombre')}</div>
            <div style="font-size:0.9rem; color:var(--text-secondary); margin-top:10px;">
                ⚠️ {res.get('mensaje')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    status_color = "var(--text-secondary)"
    if res['status'] == 'online':
        status_color = "var(--success)" if res['uso_pct'] < 90 else "var(--warning)"
    elif res['status'] == 'offline':
        status_color = "var(--danger)"

    html = f"""
<div class="eng-card">
    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
            <div class="metric-label">{res['nombre']}</div>
            <div class="metric-value">{res['gen_mw']:.1f} <span style="font-size:1rem; color:var(--text-secondary);">MW</span></div>
        </div>
        <div style="text-align:right;">
            <div class="metric-label" style="color:{status_color}">● {res['status'].upper()}</div>
            <div style="font-family:'JetBrains Mono'; font-size:0.8rem; color:var(--text-secondary); margin-top:5px;">
                {res['last_update']} UTC-3
            </div>
        </div>
    </div>
    <div style="margin-top:15px; margin-bottom:5px;">
        <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:4px; font-family:'JetBrains Mono';">
            <span>Carga: {res['uso_pct']}%</span>
            <span>Caudal Est: {res['caudal']} m³/s</span>
        </div>
        <div style="width:100%; height:4px; background:rgba(255,255,255,0.1); border-radius:2px;">
            <div style="width:{res['uso_pct']}%; height:100%; background:{status_color}; border-radius:2px; transition:width 0.5s;"></div>
        </div>
    </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)

# --- CHART GENERATION (MATPLOTLIB) ---

def generate_chart_img(data_list, efficiency=1.0):
    """Genera una imagen PNG base64 de un gráfico de dos ejes."""
    if not data_list: return None
    
    # Preparar DataFrame
    df = pd.DataFrame(data_list)
    df['dt'] = pd.to_datetime(df['fecha_hora'])
    df = df.sort_values('dt').tail(24) 
    
    if df.empty: return None

    # Cálculos
    df['gen'] = df['gen_real_mw']
    df['caudal'] = df['gen'] / efficiency

    # Estilo Dark Mode Profesional
    plt.style.use('dark_background')
    
    # Dimensiones optimizadas para móvil/web
    fig, ax1 = plt.subplots(figsize=(5.5, 3), dpi=100)
    fig.patch.set_facecolor('#0e1117') 
    ax1.set_facecolor('#0e1117')

    # Eje 1: Generación (Área Azul)
    color_gen = '#2e9eff'
    ax1.plot(df['dt'], df['gen'], color=color_gen, linewidth=2, label='Gen (MW)')
    ax1.fill_between(df['dt'], df['gen'], color=color_gen, alpha=0.15)
    
    # Configuración Eje Y Izquierdo
    ax1.set_ylabel('Generación (MW)', color=color_gen, fontsize=8, fontweight='bold', labelpad=5)
    ax1.tick_params(axis='y', labelcolor=color_gen, labelsize=8, color=color_gen)
    ax1.spines['left'].set_color(color_gen)
    ax1.spines['left'].set_linewidth(0.5)

    # Eje 2: Caudal (Línea Verde Punteada)
    ax2 = ax1.twinx()
    color_flow = '#00e5b0'
    ax2.plot(df['dt'], df['caudal'], color=color_flow, linewidth=2, linestyle='--', label='Caudal (m³/s)')
    
    # Configuración Eje Y Derecho
    ax2.set_ylabel('Caudal Est. (m³/s)', color=color_flow, fontsize=8, fontweight='bold', rotation=270, labelpad=15)
    ax2.tick_params(axis='y', labelcolor=color_flow, labelsize=8, color=color_flow)
    ax2.spines['right'].set_color(color_flow)
    ax2.spines['right'].set_linewidth(0.5)

    # Configuración Eje X (Tiempo)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.tick_params(axis='x', rotation=0, labelsize=8, colors='#8b949e')
    
    # Limpieza visual general
    ax1.spines['top'].set_visible(False)
    ax2.spines['top'].set_visible(False)
    ax1.spines['bottom'].set_color('#30363d')
    ax2.spines['bottom'].set_visible(False)
    
    # Grid
    ax1.grid(visible=True, axis='y', color='#30363d', linestyle=':', linewidth=0.5)
    ax1.grid(visible=False, axis='x')

    # Layout y guardado
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return f'<img src="data:image/png;base64,{img_base64}" style="width:100%; border-radius:6px;">'

def render_map(data_list):
    """Mapa satelital interactivo con gráficos responsive."""
    # MAPA SATELITAL ESRI
    m = folium.Map(
        location=[-37.32, -71.55], 
        zoom_start=11, 
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        prefer_canvas=True
    )
    folium.TileLayer(
        tiles='https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        overlay=True,
        opacity=0.5
    ).add_to(m)
    
    for item in data_list:
        res = item['datos']
        if res.get('error'): continue
        
        is_active = res['gen_mw'] > 0
        color = "#00e5b0" if is_active else "#8b949e"
        
        # Generar gráfico
        eficiencia = EFICIENCIAS.get(res['nombre'], 1.0)
        chart_img = generate_chart_img(res.get('full_history', []), efficiency=eficiencia)
        
        # Popup Responsive: max-width relativo al viewport
        popup_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;700;800&display=swap');
                body {{ margin: 0; padding: 0; background: transparent; font-family: 'Inter', sans-serif; }}
                .popup-card {{
                    width: 85vw; /* ANCHO RESPONSIVE */
                    max-width: 380px; /* TOPE MÁXIMO */
                    background: rgba(14, 17, 23, 0.95);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    padding: 16px;
                    color: #f0f6fc;
                    box-shadow: 0 14px 40px rgba(0,0,0,0.6);
                }}
                .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 12px; }}
                .title {{ font-size: 16px; font-weight: 800; color: #fff; letter-spacing: -0.5px; }}
                .status {{ font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 700; color: {color}; background: rgba(255,255,255,0.05); padding: 4px 8px; border-radius: 4px; text-transform: uppercase; }}
                .chart-container {{ margin-top: 5px; margin-bottom: 5px; }}
                .footer {{ display: flex; justify-content: space-between; align-items: center; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); }}
                .ts {{ font-size: 10px; color: #666; font-family: 'JetBrains Mono'; }}
                .val-highlight {{ font-size: 12px; font-weight: 700; color: #fff; }}
            </style>
        </head>
        <body>
            <div class="popup-card">
                <div class="header">
                    <div class="title">{res['nombre']}</div>
                    <div class="status">● {res['status']}</div>
                </div>
                <div class="chart-container">
                    {chart_img if chart_img else '<div style="padding:20px;text-align:center;color:#666">Esperando datos...</div>'}
                </div>
                <div class="footer">
                    <div class="ts">Último: {res['last_update']} UTC-3</div>
                    <div class="val-highlight">{res['gen_mw']:.1f} MW</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Marcador "Baliza"
        marker_html = f"""
        <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px;">
            <div style="
                position: absolute;
                width: 12px; height: 12px;
                background-color: {color};
                border-radius: 50%;
                border: 2px solid #0e1117;
                z-index: 2;
                box-shadow: 0 0 10px {color};
            "></div>
            <div style="
                position: absolute;
                width: 24px; height: 24px;
                background-color: {color};
                border-radius: 50%;
                opacity: 0.4;
                z-index: 1;
                animation: pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
            "></div>
            <style>
                @keyframes pulse-ring {{
                    0% {{ transform: scale(0.5); opacity: 0; }}
                    50% {{ opacity: 0.5; }}
                    100% {{ transform: scale(1.5); opacity: 0; }}
                }}
            </style>
        </div>
        """

        folium.Marker(
            location=item['info']['coords'],
            popup=folium.Popup(popup_html, max_width=400), # Ancho máximo contenedor
            tooltip=f"{res['nombre']} | {res['gen_mw']} MW",
            icon=DivIcon(html=marker_html, icon_size=(24, 24), icon_anchor=(12, 12))
        ).add_to(m)
    
    # CSS Hack para popups transparentes
    st.markdown("""
    <style>
    .leaflet-popup-content-wrapper { background: transparent !important; box-shadow: none !important; border: none !important; }
    .leaflet-popup-tip { display: none; }
    </style>
    """, unsafe_allow_html=True)
    
    st_folium(m, width="100%", height=500, returned_objects=[])

def render_dga_section():
    """Sección DGA."""
    st.markdown("### 📡 DIRECCIÓN GENERAL DE AGUAS")
    
    st.markdown("""
    <div class="dga-container">
        <div>
            <h4 style="margin:0; color:#2da44e;">Portal Hidrológico</h4>
            <p style="margin:5px 0 0 0; font-size:0.9rem; color:var(--text-secondary);">
                Acceso datos oficiales de limnimetría, fluviometría y meteorología.
            </p>
        </div>
        <a href="https://snia.mop.gob.cl/dgasat/pages/dgasat_param/dgasat_param.jsp?param=1" target="_blank" class="dga-link">
            ACCEDER AL PORTAL ➜
        </a>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN EXECUTION ---

def main():
    render_header()
    
    if st.session_state.datos is None:
        st.markdown("""
        <div class="welcome-box">
            <h2 style="color:var(--accent);">SISTEMA EN ESPERA</h2>
            <p style="color:var(--text-secondary); margin-bottom:20px;">
                Conexión API Coordinador Eléctrico Nacional.<br>
                Presione <b>ACTUALIZAR DATOS</b> para iniciar.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.divider()
        render_dga_section()
        return

    st.markdown("### ⚡ GENERACIÓN")
    cols = st.columns(3)
    total_mw = 0
    
    for i, item in enumerate(st.session_state.datos):
        with cols[i]:
            render_kpi_card(item)
            if not item['datos'].get('error'):
                total_mw += item['datos']['gen_mw']
            
    st.markdown(f"""
    <div style="text-align:right; margin-bottom:20px; font-family:'JetBrains Mono'; color:var(--text-secondary);">
        TOTAL SISTEMA: <span style="color:var(--text-primary); font-weight:bold;">{total_mw:.1f} MW</span>
    </div>
    """, unsafe_allow_html=True)

    col_map, col_table = st.columns([1, 1])
    
    with col_map:
        st.markdown("### 🗺️ UBICACIÓN GEOGRÁFICA")
        render_map(st.session_state.datos)

    with col_table:
        st.markdown("### 📊 ÚLTIMOS REGISTROS")
        all_records = []
        for item in st.session_state.datos:
            res = item['datos']
            if res.get('error'): continue
            
            hist = res.get('full_history', [])
            for h in hist[:5]:
                fecha_hora = h.get('fecha_hora', '')
                hora = fecha_hora.split(' ')[1][:5] if ' ' in fecha_hora else fecha_hora
                all_records.append({
                    'Central': res['nombre'],
                    'Hora': hora,
                    'Gen (MW)': h.get('gen_real_mw', 0)
                })
        
        if all_records:
            df = pd.DataFrame(all_records)
            st.dataframe(
                df, 
                use_container_width=True, 
                height=500, 
                hide_index=True,
                column_config={
                    "Gen (MW)": st.column_config.NumberColumn(format="%.1f MW")
                }
            )
        else:
            st.info("Sin datos históricos recientes.")

    st.divider()
    render_dga_section()

if __name__ == "__main__":

    main()

