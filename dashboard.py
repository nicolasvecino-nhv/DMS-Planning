import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

# =====================================================================
# CONFIGURACIÓN DE CONEXIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL REAL DE GOOGLE APPS SCRIPT:
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbx1iNrn2O-EhHt5uT8mxSGuAar9gJ6haGik5MnI3rFff_giusAohqw8m_X6PR130iae/exec"

st.set_page_config(layout="wide", page_title="Tracking de Pedidos", page_icon="📦")

# =====================================================================
# SISTEMA DE MEMORIA Y CACHÉ
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

if 'demoras_pendientes' not in st.session_state:
    st.session_state.demoras_pendientes = {}

if 'perfil' not in st.session_state:
    st.session_state.perfil = None

def logout():
    st.session_state.perfil = None
    obtener_datos.clear()

if st.session_state.perfil is None:
    st.markdown("<h2 style='text-align: center;'>👋 Bienvenido al Sistema WMS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 30px;'>Por favor, selecciona tu perfil de ingreso:</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🧑‍🔧 Operación (Armado en Pista)", use_container_width=True):
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

# =====================================================================
# LÓGICA DE ESTADOS Y CÁLCULOS
# =====================================================================
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

def get_shift_info(dt):
    """Calcula el turno de 8hs y la fecha operativa correspondiente."""
    if pd.isna(dt): return None, None
    hour = dt.hour
    if 6 <= hour < 14:
        return "Mañana (06 a 14)", dt.date()
    elif 14 <= hour < 22:
        return "Tarde (14 a 22)", dt.date()
    else: # 22 a 06
        if hour >= 22:
            return "Noche (22 a 06)", dt.date()
        else:
            return "Noche (22 a 06)", (dt - timedelta(days=1)).date()

# =====================================================================
# LECTURA ÚNICA DE BASE DE DATOS
# =====================================================================
df_full = pd.DataFrame()
if URL_GOOGLE_SCRIPT != "TU_NUEVA_URL_AQUI":
    datos_crudos = obtener_datos(URL_GOOGLE_SCRIPT)
    if datos_crudos:
        df_full = pd.DataFrame(datos_crudos)
        for col in ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']:
            if col in df_full.columns:
                df_full[col] = pd.to_numeric(df_full[col], errors='coerce').fillna(0).astype(int)
        for col in ['Ruta', 'Id_Entrega', 'Estado']:
            if col in df_full.columns:
                df_full[col] = df_full[col].astype(str).str.strip()
        if 'Fecha_Cita' in df_full.columns:
            df_full['dt_real'] = df_full['Fecha_Cita'].apply(unificar_fechas)
            df_full['Fecha_Cita_str'] = df_full['dt_real'].dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
        if 'Fecha_Despacho' in df_full.columns:
            df_full['dt_despacho'] = pd.to_datetime(df_full['Fecha_Despacho'], errors='coerce', utc=True).dt.tz_convert(None) - pd.Timedelta(hours=3)
        else:
            df_full['dt_despacho'] = pd.NaT

tab_operarios, tab_monitor, tab_supervisor, tab_resumen = st.tabs([
    "📲 Vista Operativa", "📱 Monitor de Cargas", "⚙️ Carga de Reportes", "📊 Resumen Ejecutivo"
])

# ---------------------------------------------------------------------
# PESTAÑA 1: VISTA OPERATIVA (PISTA)
# ---------------------------------------------------------------------
with tab_operarios:
    st.subheader("Tablero de Estados de Armado")
    tz_arg = timezone(timedelta(hours=-3))
    ahora_local = datetime.now(tz_arg).replace(tzinfo=None)
    
    if st.session_state.demoras_pendientes:
        st.error("🚨 ATENCIÓN: Tienes camiones marcados como DESPACHADA que superaron las 3 horas de demora.")
        motivos = {}
        for id_ent, datos in st.session_state.demoras_pendientes.items():
            motivos[id_ent] = st.text_input(f"⚠️ Motivo para Orden {id_ent} (Demora: {datos['horas']:.1f} hs):", key=f"motivo_{id_ent}")
            
        if st.button("Confirmar Despachos Retrasados", type="primary"):
            with st.spinner("Guardando..."):
                lista_cambios = [{"Id_Entrega": str(id_ent), "Estado": "DESPACHADA", "Motivo_Demora": motivos[id_ent] if motivos[id_ent] else "Sin justificación"} for id_ent in motivos]
                requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "ACTUALIZAR_ESTADO_MASIVO", "cambios": lista_cambios}))
                st.session_state.demoras_pendientes = {} 
                obtener_datos.clear() 
                st.success("✅ Justificaciones guardadas.")
                st.rerun()
        st.stop() 

    if df_full.empty:
        st.info("👆 Pega tu enlace de Google Script en la línea 12 o espera que haya datos.")
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
            
            if st.session_state.perfil == "Operacion":
                with st.expander("🔄 Panel de Actualización Masiva / Múltiple", expanded=False):
                    with st.form("form_masivo", clear_on_submit=True):
                        col1, col2, col3, col4, col5 = st.columns([2, 3, 2, 2, 2])
                        with col1: rutas_sel = st.multiselect("1. Ruta(s)", sorted(list(df_activa['Ruta'].dropna().unique())), placeholder="Elige rutas...")
                        with col2: ids_sel = st.multiselect("1B. O ID(s)", sorted(list(df_activa['Id_Entrega'].dropna().unique())), placeholder="Busca IDs sueltos...")
                        with col3: estado_sel = st.selectbox("2. Nuevo Estado", ["--"] + ESTADOS_LISTA)
                        with col4: motivo_sel = st.text_input("3. Motivo", placeholder="Si supera 3hs...")
                        with col5:
                            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                            submit_masivo = st.form_submit_button("🔄 Aplicar Cambios", use_container_width=True)
                            
                        if submit_masivo:
                            if (len(rutas_sel) > 0 or len(ids_sel) > 0) and estado_sel != "--":
                                with st.spinner("Guardando en Google Sheets..."):
                                    ids_a_cambiar = set(ids_sel)
                                    if len(rutas_sel) > 0:
                                        ids_a_cambiar.update(df_activa[df_activa['Ruta'].isin(rutas_sel)]['Id_Entrega'].tolist())
                                    
                                    bloqueado = False
                                    for id_ent in ids_a_cambiar:
                                        if estado_sel == "DESPACHADA":
                                            f_cita = df_activa[df_activa['Id_Entrega'] == id_ent]['dt_real'].values[0]
                                            if pd.notna(f_cita):
                                                dif_hs = (ahora_local - pd.to_datetime(f_cita)).total_seconds() / 3600
                                                if dif_hs > 3 and not motivo_sel: bloqueado = True
                                    
                                    if bloqueado:
                                        st.error("🚨 Tienes despachos atrasados en la selección. Escribe el Motivo (Paso 3) antes de continuar.")
                                    else:
                                        lista_cambios = [{"Id_Entrega": str(id_ent), "Estado": estado_sel, "Motivo_Demora": motivo_sel} for id_ent in ids_a_cambiar]
                                        requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "ACTUALIZAR_ESTADO_MASIVO", "cambios": lista_cambios}))
                                        obtener_datos.clear() 
                                        st.success("✅ Actualizado masivamente.")
                                        st.rerun()

            st.write("---")
            df_activa = df_activa.sort_values(by=['dt_real', 'Ruta', 'Orden_Carga'])
            df_activa['Fecha_Cita'] = df_activa['Fecha_Cita_str']
            columnas_ver = ['Fecha_Cita', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'dt_real']
            df_mostrar = df_activa[[c for c in columnas_ver if c in df_activa.columns]].copy()
            rutas_unicas = list(df_mostrar['Ruta'].unique())
            def resaltar_rutas(row): return [f"background-color: {'rgba(128, 128, 128, 0.2)' if rutas_unicas.index(row['Ruta']) % 2 == 0 else 'transparent'}"] * len(row)
            df_estilizado = df_mostrar.style.apply(resaltar_rutas, axis=1)
            columnas_deshabilitadas = ['Fecha_Cita', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'dt_real']
            
            if st.session_state.perfil == "Operacion":
                df_editado = st.data_editor(
                    df_estilizado,
                    column_config={"Estado": st.column_config.SelectboxColumn("Estado Actual", options=ESTADOS_LISTA, required=True), "dt_real": None}, 
                    disabled=columnas_deshabilitadas,
                    use_container_width=True, hide_index=True
                )
                if st.button("💾 Guardar Cambios Individuales (Lote)"):
                    with st.spinner("Empaquetando..."):
                        cambios = df_editado.compare(df_mostrar) 
                        if not cambios.empty:
                            lista_cambios_indiv = []
                            for index in cambios.index:
                                nuevo_est = str(df_editado.loc[index, 'Estado'])
                                id_ent = str(df_editado.loc[index, 'Id_Entrega'])
                                if nuevo_est == "DESPACHADA" and 'dt_real' in df_mostrar.columns:
                                    f_cita = df_mostrar.loc[index, 'dt_real']
                                    if pd.notna(f_cita):
                                        dif_hs = (ahora_local - pd.to_datetime(f_cita)).total_seconds() / 3600
                                        if dif_hs > 3:
                                            st.session_state.demoras_pendientes[id_ent] = {'horas': dif_hs}
                                            continue 
                                lista_cambios_indiv.append({"Id_Entrega": id_ent, "Estado": nuevo_est, "Motivo_Demora": ""})
                            if lista_cambios_indiv:
                                requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "ACTUALIZAR_ESTADO_MASIVO", "cambios": lista_cambios_indiv}))
                                obtener_datos.clear()
                                if not st.session_state.demoras_pendientes: st.success("✅ Actualizado."); st.rerun()
                            elif not st.session_state.demoras_pendientes: st.rerun()
            else:
                st.dataframe(df_mostrar.drop(columns=['dt_real']).style.apply(resaltar_rutas, axis=1), use_container_width=True, hide_index=True)

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
# PESTAÑA 4: RESUMEN EJECUTIVO (KPIs Analíticos + Gráfico)
# ---------------------------------------------------------------------
with tab_resumen:
    st.markdown("<h2 style='text-align: left;'>📊 Resumen Ejecutivo y Productividad</h2>", unsafe_allow_html=True)
    if not df_full.empty and 'dt_real' in df_full.columns:
        tz_arg = timezone(timedelta(hours=-3))
        hoy_dt = datetime.now(tz_arg)
        hoy = hoy_dt.date()
        df_res = df_full.copy()
        
        # Mapeamos turno y fecha a cada fila
        df_res['Shift_Name'] = df_res['dt_real'].apply(lambda x: get_shift_info(x)[0])
        df_res['Shift_Date'] = df_res['dt_real'].apply(lambda x: get_shift_info(x)[1])
        df_res['Tiempo_Carga_Hs'] = (df_res['dt_despacho'] - df_res['dt_real']).dt.total_seconds() / 3600 if 'dt_despacho' in df_res.columns else np.nan
            
        # Snapshot Diario
        df_hoy = df_res[df_res['dt_real'].apply(lambda x: x.date() == hoy if pd.notna(x) else False)].copy()
        
        c1, c2, c3 = st.columns(3)
        if not df_hoy.empty:
            c1.metric("Cajas Pickeadas (Hoy)", f"{df_hoy[df_hoy['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()} / {df_hoy['Cajas_Picking'].sum()}")
            c2.metric("Pallets Preps (Hoy)", f"{df_hoy[df_hoy['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()} / {df_hoy['Pallets_Completos'].sum()}")
            c3.metric("Rutas Despachadas (Hoy)", f"{df_hoy[df_hoy['Estado'] == 'DESPACHADA']['Ruta'].nunique()} / {df_hoy['Ruta'].nunique()}")
        
        st.write("---")
        
        # === GRÁFICO DINÁMICO: PROYECCIÓN 3 TURNOS ===
        st.markdown("### ⏱️ Proyección de Carga (Próximos 3 Turnos)")
        st.markdown("<small>Asigna la dotación para ver si el turno logrará sacar las cajas dentro de sus <b>6 horas de trabajo neto</b> (sobre las 8hs reloj).</small>", unsafe_allow_html=True)
        
        # Generar los próximos 3 turnos desde el momento actual
        target_shifts = []
        temp_dt = hoy_dt
        for _ in range(3):
            s_name, s_date = get_shift_info(temp_dt)
            if s_date == hoy: day_label = "Hoy"
            elif s_date == hoy + timedelta(days=1): day_label = "Mañana"
            elif s_date == hoy - timedelta(days=1): day_label = "Ayer"
            else: day_label = s_date.strftime('%d/%m')
            
            label = f"<b>{s_name}</b><br>{day_label}"
            target_shifts.append({"name": s_name, "date": s_date, "label": label})
            temp_dt += timedelta(hours=8)
        
        col_t1, col_t2, col_t3 = st.columns(3)
        cols_input = [col_t1, col_t2, col_t3]
        dotaciones = []
        for i, ts in enumerate(target_shifts):
            val = cols_input[i].number_input(f"🧑‍🤝‍🧑 Dotación: {ts['name']} ({ts['label'].split('<br>')[1]})", min_value=1, value=5, key=f"dot_{i}")
            dotaciones.append(val)
        
        y_vals, solic_hs, solic_txt = [], [], []
        proy_hs, proy_txt = [], []
        real_hs, real_txt = [], []

        for ts, dot in zip(target_shifts, dotaciones):
            df_t = df_res[(df_res['Shift_Name'] == ts['name']) & (df_res['Shift_Date'] == ts['date'])].copy()
            y_vals.append(ts['label'])
            
            if df_t.empty:
                solic_hs.append(0); proy_hs.append(0); real_hs.append(0)
                solic_txt.append(""); proy_txt.append(""); real_txt.append("")
                continue
            
            df_t['Prod_Hr'] = np.where(df_t['Average_Picking'] > 0, (df_t['Average_Picking'] / 10.0) * 124.0, 124.0)
            
            # PLAN (Capacidad Solicitada)
            hs_plan_shift = (df_t['Cajas_Picking'] / df_t['Prod_Hr']).sum() / dot
            cajas_plan = df_t['Cajas_Picking'].sum()
            cjs_h_plan = int(cajas_plan / hs_plan_shift) if hs_plan_shift > 0 else 0
            
            # REAL (Avance)
            df_ok = df_t[df_t['Estado'].isin(ESTADOS_CAJAS_LISTAS)]
            hs_real_shift = (df_ok['Cajas_Picking'] / df_ok['Prod_Hr']).sum() / dot if not df_ok.empty else 0
            cajas_ok = df_ok['Cajas_Picking'].sum() if not df_ok.empty else 0
            
            # PENDIENTE (Proyectado)
            df_pend = df_t[~df_t['Estado'].isin(ESTADOS_CAJAS_LISTAS)]
            hs_pend_shift = (df_pend['Cajas_Picking'] / df_pend['Prod_Hr']).sum() / dot if not df_pend.empty else 0
            cajas_pend = df_pend['Cajas_Picking'].sum() if not df_pend.empty else 0
            cjs_h_pend = int(cajas_pend / hs_pend_shift) if hs_pend_shift > 0 else 0
            
            solic_hs.append(hs_plan_shift)
            solic_txt.append(f"{hs_plan_shift:.1f}h | {int(cajas_plan)} cjs ({cjs_h_plan} c/h)" if hs_plan_shift > 0 else "")
            
            proy_hs.append(hs_pend_shift)
            proy_txt.append(f"{hs_pend_shift:.1f}h | {int(cajas_pend)} cjs ptes ({cjs_h_pend} c/h)" if hs_pend_shift > 0 else "")
            
            real_hs.append(hs_real_shift)
            real_txt.append(f"{hs_real_shift:.1f}h | {int(cajas_ok)} cjs listas" if hs_real_shift > 0 else "")

        # Invertimos las listas para que el turno actual quede arriba de todo en el gráfico
        y_vals.reverse(); solic_hs.reverse(); solic_txt.reverse()
        proy_hs.reverse(); proy_txt.reverse(); real_hs.reverse(); real_txt.reverse()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=y_vals, x=solic_hs, name='Planificado (Total Solicitado)', orientation='h',
            marker=dict(color='#f57f17'), text=solic_txt, textposition='inside', insidetextanchor='start'
        ))
        fig.add_trace(go.Bar(
            y=y_vals, x=proy_hs, name='Proyectado (Pendiente)', orientation='h',
            marker=dict(color='#2e7d32'), text=proy_txt, textposition='inside', insidetextanchor='start'
        ))
        fig.add_trace(go.Bar(
            y=y_vals, x=real_hs, name='Avance Real', orientation='h',
            marker=dict(color='#E55B3C'), text=real_txt, textposition='inside', insidetextanchor='start'
        ))

        fig.update_layout(
            barmode='group', height=450, margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        # LÍNEA ROJA EN LAS 6 HORAS DE TRABAJO NETO
        fig.add_vline(x=6, line_width=2, line_dash="dash", line_color="red")
        fig.add_annotation(x=6.1, y=2.5, text="Límite Trabajo Neto (6hs)", showarrow=False, font=dict(color="red", size=12), xanchor="left")
        
        st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        # =====================================================================

        st.markdown("### 📈 Histórico y Cumplimiento")
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
            t_prom = df_p[df_p['Estado'] == 'DESPACHADA']['Tiempo_Carga_Hs'].mean()
            datos_tabla.append({"Período": p["nombre"], "Rutas Ok": rut_o, "Rutas Plan": rut_p, "% Rutas": int(rut_o/rut_p*100) if rut_p>0 else 0, "Cajas Ok": int(caj_o), "Cajas Plan": int(caj_p), "% Cajas": int(caj_o/caj_p*100) if caj_p>0 else 0, "Pallets Ok": int(pal_o), "Pallets Plan": int(pal_p), "% Pallets": int(pal_o/pal_p*100) if pal_p>0 else 0, "Demora Promedio": f"{t_prom:.1f} hs" if pd.notna(t_prom) else "-"})
            
        st.dataframe(pd.DataFrame(datos_tabla), column_config={"Período": st.column_config.TextColumn("📅 Período"), "% Rutas": st.column_config.ProgressColumn("🚛 Avance Rutas", max_value=100, format="%d%%"), "% Cajas": st.column_config.ProgressColumn("📦 Avance Cajas", max_value=100, format="%d%%"), "% Pallets": st.column_config.ProgressColumn("🧱 Avance Pallets", max_value=100, format="%d%%")}, use_container_width=True, hide_index=True)
    else: st.info("Recolectando datos...")
