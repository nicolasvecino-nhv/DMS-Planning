import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import urllib.parse

# =====================================================================
# CONFIGURACIÓN DE CONEXIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL REAL DE GOOGLE APPS SCRIPT:
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbx1iNrn2O-EhHt5uT8mxSGuAar9gJ6haGik5MnI3rFff_giusAohqw8m_X6PR130iae/exec"

st.set_page_config(layout="wide", page_title="Tracking de Pedidos", page_icon="📦")

# =====================================================================
# SISTEMA DE MEMORIA Y LECTURA
# =====================================================================
@st.cache_data(ttl=15, show_spinner=False)
def obtener_datos(url):
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return []

@st.cache_data(ttl=30, show_spinner=False)
def obtener_tiempos_despachos():
    try:
        meses = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}
        tz_arg = timezone(timedelta(hours=-3))
        mes_actual = meses[datetime.now(tz_arg).month]
        sheet_id = "1V8lkm7RmxJMqzb4pQMHrxQX5bSW2K8tF_bO7A8cJpHM"
        
        sheet_name_encoded = urllib.parse.quote(f"Despachos {mes_actual}")
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name_encoded}"
        
        df_tiempos = pd.read_csv(url_csv, dtype=str) 
        
        # Extraemos: A=0, L=11, M=12
        if len(df_tiempos.columns) >= 13:
            df_t = df_tiempos.iloc[:, [0, 11, 12]].copy()
            df_t.columns = ['Ruta', 'Ingreso_Str', 'Egreso_Str']
            df_t = df_t.dropna(subset=['Ruta'])
            # Forzamos la ruta a mayúsculas por seguridad
            df_t['Ruta'] = df_t['Ruta'].astype(str).str.strip().str.replace('.0', '', regex=False).str.upper()
            return df_t
    except Exception as e:
        pass
    return pd.DataFrame()

if 'perfil' not in st.session_state:
    st.session_state.perfil = None

def logout():
    st.session_state.perfil = None
    obtener_datos.clear()
    obtener_tiempos_despachos.clear()

if st.session_state.perfil is None:
    st.markdown("<h2 style='text-align: center;'>👋 Bienvenido al Sistema WMS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 30px;'>Por favor, selecciona tu perfil de ingreso:</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🧑‍🔧 Operación (Solo Visualización)", use_container_width=True):
            st.session_state.perfil = "Operacion"
            st.rerun()
    with col2:
        if st.button("👁️ Visualizador (Solo Monitor)", use_container_width=True):
            st.session_state.perfil = "Visualizador"
            st.rerun()
    with col3:
        if st.button("⚙️ Supervisor (Carga de Datos)", use_container_width=True):
            st.session_state.perfil = "Supervisor"
            st.rerun()
    st.stop() 

st.sidebar.markdown(f"**🟢 Conectado como:**<br>{st.session_state.perfil}", unsafe_allow_html=True)
st.sidebar.button("Cerrar Sesión / Cambiar Rol", on_click=logout)

# =====================================================================
# CSS PARA KPIs Y TARJETAS 
# =====================================================================
st.markdown("""
    <style>
    .kpi-box { background-color: var(--secondary-background-color); color: var(--text-color); padding: 12px 5px; border-radius: 6px; border-top: 4px solid #E55B3C; text-align: center; box-shadow: 1px 1px 3px rgba(0,0,0,0.2);}
    .kpi-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.8;}
    .kpi-value { font-size: 20px; font-weight: bold; margin-top: 4px;}
    .monitor-card { padding: 15px; border-radius: 10px; margin-bottom: 15px; color: white; font-family: sans-serif; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }
    .card-red { background-color: #b71c1c; border-left: 8px solid #ff5252; }
    .card-yellow { background-color: #f57f17; border-left: 8px solid #ffeb3b; }
    .card-green { background-color: #2e7d32; border-left: 8px solid #69f0ae; }
    .card-title { font-size: 22px; font-weight: bold; margin-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px;}
    .card-foco { font-size: 18px; font-weight: bold; margin-top: 10px; text-transform: uppercase; }
    .card-text { font-size: 14px; margin: 2px 0; }
    </style>
""", unsafe_allow_html=True)

st.title("📦 Tablero de Seguimiento y Preparado de Pedidos")

ESTADOS_LISTA = ["PENDIENTE", "CARENCIA", "LANZADA", "EN PREPARACIÓN", "PICKING COMPLETO", "PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA"]
ESTADO_PESO = {estado: i+1 for i, estado in enumerate(ESTADOS_LISTA)}
ESTADOS_CAJAS_LISTAS = ["PICKING COMPLETO", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA"]
ESTADOS_PALLETS_LISTOS = ["PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA"]

def unificar_fechas(fecha_val):
    try:
        if pd.isna(fecha_val) or fecha_val == "Sin Fecha": return pd.NaT
        s = str(fecha_val).strip()
        if "/" in s and len(s) <= 12: 
            año = datetime.now().year
            return pd.to_datetime(f"{s}/{año}", format="%d/%m %H:%M/%Y")
        else:
            return pd.to_datetime(s, utc=True).tz_convert(None) - pd.Timedelta(hours=3)
    except:
        return pd.NaT

def safe_parse_time(val, base_date_series):
    if pd.isna(val) or str(val).strip() == "": return pd.NaT
    try:
        dt = pd.to_datetime(str(val), errors='coerce')
        if pd.notna(dt) and dt.year < 2000 and pd.notna(base_date_series):
            return dt.replace(year=base_date_series.year, month=base_date_series.month, day=base_date_series.day)
        return dt
    except:
        return pd.NaT

def get_current_shift_info(now):
    hour = now.hour
    if 6 <= hour < 14:
        shift_name = "Turno Mañana (06:00 - 14:00)"
        end_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
        n1, n2 = "Turno Tarde (14:00 - 22:00)", "Turno Noche (22:00 - 06:00)"
    elif 14 <= hour < 22:
        shift_name = "Turno Tarde (14:00 - 22:00)"
        end_time = now.replace(hour=22, minute=0, second=0, microsecond=0)
        n1, n2 = "Turno Noche (22:00 - 06:00)", "Turno Mañana (06:00 - 14:00)"
    else:
        shift_name = "Turno Noche (22:00 - 06:00)"
        if hour >= 22: end_time = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        else: end_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
        n1, n2 = "Turno Mañana (06:00 - 14:00)", "Turno Tarde (14:00 - 22:00)"
        
    rem_clock_hs = (end_time - now).total_seconds() / 3600.0
    eff_hs = rem_clock_hs * 0.75  
    if eff_hs < 0: eff_hs = 0
    return [{"name": shift_name + " (ACTUAL)", "eff_hs": eff_hs}, {"name": n1, "eff_hs": 6.0}, {"name": n2, "eff_hs": 6.0}]

# =====================================================================
# LECTURA ÚNICA DE BASE DE DATOS Y CRUCE
# =====================================================================
df_full = pd.DataFrame()
if URL_GOOGLE_SCRIPT != "TU_NUEVA_URL_AQUI":
    datos_crudos = obtener_datos(URL_GOOGLE_SCRIPT)
    if datos_crudos:
        df_full = pd.DataFrame(datos_crudos)
        
        for col in ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']:
            if col in df_full.columns:
                df_full[col] = pd.to_numeric(df_full[col], errors='coerce').fillna(0).astype(int)
        
        # ⚠️ SOLUCIÓN A LOS ESTADOS: Convertimos todo a texto, borramos espacios y FORZAMOS A MAYÚSCULAS
        for col in ['Ruta', 'Id_Entrega', 'Estado']:
            if col in df_full.columns:
                df_full[col] = df_full[col].astype(str).str.strip().str.upper()
        
        if 'Fecha_Cita' in df_full.columns:
            df_full['dt_real'] = df_full['Fecha_Cita'].apply(unificar_fechas)
            df_full['Fecha_Cita_str'] = df_full['dt_real'].dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
            
        if 'Ruta' in df_full.columns:
            df_tiempos = obtener_tiempos_despachos()
            if not df_tiempos.empty:
                df_full = pd.merge(df_full, df_tiempos, on='Ruta', how='left')
                df_full['dt_Ingreso'] = df_full.apply(lambda r: safe_parse_time(r.get('Ingreso_Str'), r.get('dt_real')), axis=1)
                df_full['dt_Egreso'] = df_full.apply(lambda r: safe_parse_time(r.get('Egreso_Str'), r.get('dt_real')), axis=1)
                
                df_full['Inicio_Carga'] = df_full[['dt_real', 'dt_Ingreso']].max(axis=1)
                df_full['Tiempo_Carga_Hs'] = (df_full['dt_Egreso'] - df_full['Inicio_Carga']).dt.total_seconds() / 3600
                df_full['Tiempo_Carga_Hs'] = df_full['Tiempo_Carga_Hs'].apply(lambda x: x if x > 0 else np.nan)
            else:
                df_full['Tiempo_Carga_Hs'] = np.nan

tab_operarios, tab_monitor, tab_supervisor, tab_resumen = st.tabs(["📲 Vista Operativa", "📱 Monitor de Cargas", "⚙️ Carga de Reportes", "📊 Resumen Ejecutivo"])

# ---------------------------------------------------------------------
# PESTAÑA 1: VISTA OPERATIVA (MODO LECTURA)
# ---------------------------------------------------------------------
with tab_operarios:
    st.subheader("Tablero de Estados de Armado (Lectura Automática)")
    tz_arg = timezone(timedelta(hours=-3))
    ahora_local = datetime.now(tz_arg).replace(tzinfo=None)

    if df_full.empty:
        st.info("👆 Pega tu enlace de Google Script en la línea 14 o espera que haya datos.")
    else:
        df_activa = df_full[df_full['Estado'] != 'DESPACHADA'].copy()
        
        if df_activa.empty:
            st.success("🎉 Todas las órdenes activas han sido despachadas.")
        else:
            total_pedidos = len(df_activa)
            total_rutas = df_activa['Ruta'].nunique()
            cajas_ya_listas = df_activa[df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()
            cajas_pendientes = df_activa['Cajas_Picking'].sum() - cajas_ya_listas
            pallets_ya_listos = df_activa[df_activa['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()
            pallets_pendientes = df_activa['Pallets_Completos'].sum() - pallets_ya_listos
            cajas_lanzadas = df_activa[df_activa['Estado'].isin(['LANZADA', 'EN PREPARACIÓN'])]['Cajas_Picking'].sum()
            pedidos_listos = len(df_activa[df_activa['Estado'] == 'TOP SALIDA'])
            
            df_pendientes_cajas = df_activa[~df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)].copy()
            df_pendientes_cajas['Productividad_Hr'] = np.where(df_pendientes_cajas['Average_Picking'] > 0, (df_pendientes_cajas['Average_Picking'] / 10.0) * 124.0, 124.0)
            df_pendientes_cajas['Horas_Estimadas'] = np.where(df_pendientes_cajas['Cajas_Picking'] > 0, df_pendientes_cajas['Cajas_Picking'] / df_pendientes_cajas['Productividad_Hr'], 0)
            horas_picking_decimal = df_pendientes_cajas['Horas_Estimadas'].sum()
            minutos_totales = int(horas_picking_decimal * 60)
            horas_picking_str = f"{minutos_totales // 60:02d}:{minutos_totales % 60:02d}"
            
            k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
            with k1: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Rutas</div><div class='kpi-value'>{total_rutas}</div></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Órdenes Activas</div><div class='kpi-value'>{total_pedidos}</div></div>", unsafe_allow_html=True)
            with k3: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Pallets Ptes</div><div class='kpi-value'>{pallets_pendientes}</div></div>", unsafe_allow_html=True)
            with k4: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Ptes</div><div class='kpi-value'>{cajas_pendientes}</div></div>", unsafe_allow_html=True)
            with k5: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Horas Pick</div><div class='kpi-value'>{horas_picking_str}</div></div>", unsafe_allow_html=True)
            with k6: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Pista</div><div class='kpi-value'>{cajas_lanzadas}</div></div>", unsafe_allow_html=True)
            with k7: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Top Salida</div><div class='kpi-value'>{pedidos_listos}</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            
            col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
            with col_b2:
                if st.button("🔄 Sincronizar con SharePoint y GSheets", use_container_width=True):
                    obtener_datos.clear()
                    obtener_tiempos_despachos.clear()
                    st.rerun()
            st.write("")

            df_activa = df_activa.sort_values(by=['dt_real', 'Ruta', 'Orden_Carga'])
            df_activa['Fecha_Cita'] = df_activa['Fecha_Cita_str']
            columnas_ver = ['Fecha_Cita', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking']
            df_mostrar = df_activa[[c for c in columnas_ver if c in df_activa.columns]].copy()
            
            rutas_unicas = list(df_mostrar['Ruta'].unique())
            def resaltar_rutas(row): return [f"background-color: {'rgba(128, 128, 128, 0.2)' if rutas_unicas.index(row['Ruta']) % 2 == 0 else 'transparent'}"] * len(row)
            
            st.dataframe(df_mostrar.style.apply(resaltar_rutas, axis=1), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------
# PESTAÑA 2: MONITOR DE CARGAS
# ---------------------------------------------------------------------
with tab_monitor:
    st.subheader("🎯 Estado General por Horario de Cita")
    if not df_full.empty:
        df_mon = df_full[df_full['Estado'] != 'DESPACHADA'].copy()
        if df_mon.empty: st.success("Todo despachado.")
        else:
            ahora = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
            df_mon['Fecha_Cita_dt'] = df_mon['dt_real']
            df_mon = df_mon.dropna(subset=['Fecha_Cita_dt'])
            df_mon['Fecha_Cita'] = df_mon['Fecha_Cita_str']
            grupos = df_mon.groupby('Fecha_Cita')
            for _, row_hora in df_mon[['Fecha_Cita', 'Fecha_Cita_dt']].drop_duplicates().sort_values('Fecha_Cita_dt').iterrows():
                fecha_str, fecha_dt = row_hora['Fecha_Cita'], row_hora['Fecha_Cita_dt']
                grupo = grupos.get_group(fecha_str)
                min_dif = (ahora - fecha_dt).total_seconds() / 60
                peor_peso = grupo['Estado'].map(ESTADO_PESO).min()
                foco = "🚀 FOCO: LANZAMIENTO" if peor_peso <= 3 else "📦 FOCO: PREPARACIÓN" if peor_peso <= 6 else "🔎 FOCO: CONTROL" if peor_peso <= 8 else "🚛 FOCO: CARGA"
                if min_dif >= 0: 
                    if peor_peso < 8: clase_col, est_txt = "card-red", "🚨 ROJO: Cita cumplida y faltan controlar"
                    elif peor_peso < 11: clase_col, est_txt = ("card-yellow", "🟡 AMARILLO: En ventana de 3hs") if min_dif <= 180 else ("card-red", "🚨 ROJO: Vencieron las 3hs")
                    else: clase_col, est_txt = "card-green", "🟢 VERDE: Lista para despachar"
                else: clase_col, est_txt = "card-green", f"🟢 VERDE: Faltan {int(abs(min_dif))} min. para la cita"
                st.markdown(f"""<div class="monitor-card {clase_col}"><div class="card-title">⏰ Cita: {fecha_str}</div><div class="card-text">{est_txt}</div><div class="card-text"><b>{len(grupo)}</b> Órdenes en este bloque.</div><div class="card-foco">{foco}</div></div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# PESTAÑA 3: CARGA SUPERVISOR
# ---------------------------------------------------------------------
with tab_supervisor:
    st.subheader("Subir Planificación del Día")
    if st.session_state.perfil != "Supervisor": st.warning("⚠️ Solo el perfil 'Supervisor' tiene permisos.")
    else:
        col1, col2 = st.columns(2)
        file_plan = col1.file_uploader("1. Reporte 'Planificación Dana' (Excel)", type=["xlsx", "xls"])
        file_maestro = col2.file_uploader("2. 'Maestro Materiales' (Excel)", type=["xlsx", "xls"])
        if st.button("Procesar y Cargar al Sistema") and file_plan and file_maestro:
            try:
                df_plan = pd.read_excel(file_plan).rename(columns={"FechaHoraDespacho": 'Fecha_Cita', "IdRuta": 'Ruta', "Número de orden de ventas de origen": 'Orden_Entrega', "IdEntrega": 'Id_Entrega', "Nombre de organización": 'Cliente', "IdTransportista": 'Transporte', "Artículo": 'Codigo', "Cantidad solicitada secundaria": 'Cantidad_Cajas', "OrdenCarga": 'Orden_Descarga'})
                df_maestro = pd.read_excel(file_maestro).rename(columns={"Artículo - Nombre": 'Codigo', "LPK - Cajas por Pallet": 'LPK'})
                df_plan['Codigo'], df_maestro['Codigo'] = df_plan['Codigo'].astype(str).str.strip(), df_maestro['Codigo'].astype(str).str.strip()
                df_completo = pd.merge(df_plan, df_maestro[['Codigo', 'LPK']], on='Codigo', how='left')
                df_completo['Cantidad_Cajas'], df_completo['LPK'] = pd.to_numeric(df_completo['Cantidad_Cajas'], errors='coerce').fillna(0), pd.to_numeric(df_completo['LPK'], errors='coerce').fillna(1) 
                fechas_excel = pd.to_datetime(df_completo['Fecha_Cita'], errors='coerce')
                if fechas_excel.dt.tz is not None: fechas_excel = fechas_excel.dt.tz_convert(None)
                df_completo['Fecha_Cita'] = (fechas_excel - pd.Timedelta(hours=3)).dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
                df_completo['Pallets_Completos'] = (df_completo['Cantidad_Cajas'] // df_completo['LPK']).astype(int)
                df_completo['Cajas_Picking'] = (df_completo['Cantidad_Cajas'] % df_completo['LPK']).astype(int)
                df_completo['Lineas_Picking'] = np.where(df_completo['Cajas_Picking'] > 0, 1, 0)
                df_agrupado = df_completo.groupby(['Fecha_Cita', 'Ruta', 'Orden_Entrega', 'Id_Entrega', 'Cliente', 'Transporte']).agg({'Cajas_Picking': 'sum', 'Pallets_Completos': 'sum', 'Lineas_Picking': 'sum', 'Orden_Descarga': 'min'}).reset_index()
                df_agrupado['Average_Picking'] = np.where(df_agrupado['Lineas_Picking'] > 0, np.ceil(df_agrupado['Cajas_Picking'] / df_agrupado['Lineas_Picking']), 0).astype(int)
                df_agrupado['Orden_Carga'] = df_agrupado.groupby('Ruta')['Orden_Descarga'].rank(ascending=False, method='min').fillna(1).astype(int) if 'Orden_Descarga' in df_agrupado.columns else 1
                if not df_full.empty: df_agrupado = df_agrupado[~df_agrupado['Id_Entrega'].astype(str).isin(df_full['Id_Entrega'].astype(str).tolist())]
                if df_agrupado.empty: st.warning("⚠️ Órdenes ya cargadas.")
                else:
                    with st.spinner("Enviando pedidos..."):
                        for _, row in df_agrupado.sort_values(by=['Fecha_Cita', 'Ruta', 'Orden_Carga']).iterrows():
                            payload = {"accion": "CARGAR_PLAN", "Fecha_Cita": str(row['Fecha_Cita']), "Ruta": str(row['Ruta']), "Orden_Entrega": str(row['Orden_Entrega']), "Id_Entrega": str(row['Id_Entrega']), "Cliente": str(row['Cliente']), "Transporte": str(row['Transporte']), "Cajas_Picking": int(row['Cajas_Picking']), "Pallets_Completos": int(row['Pallets_Completos']), "Average_Picking": int(row['Average_Picking']), "Orden_Carga": int(row['Orden_Carga'])}
                            requests.post(URL_GOOGLE_SCRIPT, data=json.dumps(payload))
                        obtener_datos.clear() 
                        st.success("🚀 ¡Datos enviados! Refresca la página.")
            except Exception as e: st.error(f"❌ Error leyendo Excel: {e}")

# ---------------------------------------------------------------------
# PESTAÑA 4: RESUMEN EJECUTIVO (KPIs Analíticos + Gráfico Continuo)
# ---------------------------------------------------------------------
with tab_resumen:
    st.markdown("<h2 style='text-align: left;'>📊 Resumen Ejecutivo y Productividad</h2>", unsafe_allow_html=True)
    if not df_full.empty and 'dt_real' in df_full.columns:
        tz_arg = timezone(timedelta(hours=-3))
        hoy_dt = datetime.now(tz_arg).replace(tzinfo=None)
        hoy = hoy_dt.date()
        df_res = df_full.copy()
        
        df_hoy = df_res[df_res['dt_real'].apply(lambda x: x.date() == hoy if pd.notna(x) else False)].copy()
        
        c1, c2, c3 = st.columns(3)
        if not df_hoy.empty:
            c1.metric("Cajas Pickeadas (Hoy)", f"{df_hoy[df_hoy['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()} / {df_hoy['Cajas_Picking'].sum()}")
            c2.metric("Pallets Preps (Hoy)", f"{df_hoy[df_hoy['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()} / {df_hoy['Pallets_Completos'].sum()}")
            c3.metric("Rutas Despachadas (Hoy)", f"{df_hoy[df_hoy['Estado'] == 'DESPACHADA']['Ruta'].nunique()} / {df_hoy['Ruta'].nunique()}")
        
        st.write("---")
        
        st.markdown("### 🌊 Flujo Continuo: Consumo de la Cola Pendiente")
        
        shifts = get_current_shift_info(hoy_dt)
        col_t1, col_t2, col_t3 = st.columns(3)
        dot_t1 = col_t1.number_input(f"🧑‍🤝‍🧑 Dotación: {shifts[0]['name']}", min_value=1, value=5)
        dot_t2 = col_t2.number_input(f"🧑‍🤝‍🧑 Dotación: {shifts[1]['name']}", min_value=1, value=5)
        dot_t3 = col_t3.number_input(f"🧑‍🤝‍🧑 Dotación: {shifts[2]['name']}", min_value=1, value=5)
        
        dotaciones = [dot_t1, dot_t2, dot_t3]
        
        df_pendientes = df_full[~df_full['Estado'].isin(ESTADOS_CAJAS_LISTAS)].copy()
        if not df_pendientes.empty:
            df_pendientes['Prod_Hr'] = np.where(df_pendientes['Average_Picking'] > 0, (df_pendientes['Average_Picking'] / 10.0) * 124.0, 124.0)
            df_pendientes['Horas_Estimadas'] = np.where(df_pendientes['Cajas_Picking'] > 0, df_pendientes['Cajas_Picking'] / df_pendientes['Prod_Hr'], 0)
            total_ph = df_pendientes['Horas_Estimadas'].sum()
            total_cjs = df_pendientes['Cajas_Picking'].sum()
            avg_cjs_ph = total_cjs / total_ph if total_ph > 0 else 0
        else:
            total_ph, total_cjs, avg_cjs_ph = 0, 0, 0

        w_rem = total_ph
        y_vals, cap_hs, cap_txt, uso_hs, uso_txt = [], [], [], [], []
        
        for s, dot in zip(shifts, dotaciones):
            y_vals.append(f"<b>{s['name']}</b><br>T. Disponible: {s['eff_hs']:.1f}hs netas")
            c_i = s['eff_hs']
            v_i = c_i * dot 
            cajas_cap = int(v_i * avg_cjs_ph)
            
            cap_hs.append(c_i)
            cap_txt.append(f"{c_i:.1f} hs disp. (Cubre {cajas_cap} cjs)")
            
            if w_rem >= v_i:
                uso_hs.append(c_i)
                uso_txt.append(f"{c_i:.1f} hs uso ({cajas_cap} cjs) ➡️ Sigue")
                w_rem -= v_i
            elif w_rem > 0:
                d_i = w_rem / dot
                cajas_uso = int(w_rem * avg_cjs_ph)
                uso_hs.append(d_i)
                uso_txt.append(f"{d_i:.1f} hs uso ({cajas_uso} cjs ptes) 🏁 FIN")
                w_rem = 0
            else:
                uso_hs.append(0)
                uso_txt.append("Libre (0 cjs)")

        y_vals.reverse(); cap_hs.reverse(); cap_txt.reverse(); uso_hs.reverse(); uso_txt.reverse()

        fig = go.Figure()
        fig.add_trace(go.Bar(y=y_vals, x=cap_hs, name='Capacidad Instalada (Disp.)', orientation='h', marker=dict(color='#2e7d32'), text=cap_txt, textposition='inside', insidetextanchor='start'))
        fig.add_trace(go.Bar(y=y_vals, x=uso_hs, name='Cola Pendiente (Consumo)', orientation='h', marker=dict(color='#f57f17'), text=uso_txt, textposition='inside', insidetextanchor='start'))
        fig.update_layout(barmode='group', bargap=0.15, height=450, margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        
        st.markdown("### 📈 Histórico de KPI y Tiempos Logísticos")
        periodos = [
            {"nombre": "Mes Pasado", "filtro": lambda d: (hoy.replace(day=1) - timedelta(days=1)).replace(day=1) <= d <= (hoy.replace(day=1) - timedelta(days=1))},
            {"nombre": "Acum. Este Mes", "filtro": lambda d: hoy.replace(day=1) <= d <= hoy},
            {"nombre": "Ayer", "filtro": lambda d: d == (hoy - timedelta(days=1))},
            {"nombre": "Hoy", "filtro": lambda d: d == hoy},
            {"nombre": "Mañana en Adelante", "filtro": lambda d: d >= (hoy + timedelta(days=1))},
        ]
        
        datos_tabla = []
        for p in periodos:
            df_p = df_res[df_res['dt_real'].apply(lambda x: p["filtro"](x.date()) if pd.notna(x) else False)]
            rut_p, rut_o = df_p['Ruta'].nunique(), df_p[df_p['Estado'] == 'DESPACHADA']['Ruta'].nunique()
            caj_p, caj_o = df_p['Cajas_Picking'].sum(), df_p[df_p['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()
            pal_p, pal_o = df_p['Pallets_Completos'].sum(), df_p[df_p['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()
            
            t_prom = df_p['Tiempo_Carga_Hs'].mean() if 'Tiempo_Carga_Hs' in df_p.columns else np.nan
            
            datos_tabla.append({"Período": p["nombre"], "Rutas Ok": rut_o, "Rutas Plan": rut_p, "% Rutas": int(rut_o/rut_p*100) if rut_p>0 else 0, "Cajas Ok": int(caj_o), "Cajas Plan": int(caj_p), "% Cajas": int(caj_o/caj_p*100) if caj_p>0 else 0, "Pallets Ok": int(pal_o), "Pallets Plan": int(pal_p), "% Pallets": int(pal_o/pal_p*100) if pal_p>0 else 0, "Demora Prom.": f"{t_prom:.1f} hs" if pd.notna(t_prom) else "-"})
            
        st.dataframe(pd.DataFrame(datos_tabla), column_config={"Período": st.column_config.TextColumn("📅 Período"), "% Rutas": st.column_config.ProgressColumn("🚛 Avance Rutas", max_value=100, format="%d%%"), "% Cajas": st.column_config.ProgressColumn("📦 Avance Cajas", max_value=100, format="%d%%"), "% Pallets": st.column_config.ProgressColumn("🧱 Avance Pallets", max_value=100, format="%d%%")}, use_container_width=True, hide_index=True)
    else: st.info("Recolectando datos...")
