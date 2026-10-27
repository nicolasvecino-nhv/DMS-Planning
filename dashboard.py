import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone, date

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL DE GOOGLE APPS SCRIPT:
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbztFHXE-qQc48hk8HYwqzVxqKePMg60PozszgMgPnJgp7SWlNAtonyfJ6k_AMJjSOM/exec"

st.set_page_config(layout="wide", page_title="WMS Dashboard", page_icon="📦")

# 🔹 HOMOLOGACIÓN MAESTRA DE ESTADOS (Cubre masculino, femenino y tildes)
ESTADOS_PENDIENTES_CAJAS = [
    "PENDIENTE", 
    "LANZADA", 
    "EN PREPARACION", "EN PREPARACIÓN", 
    "CARENCIA", "CON CARENCIA"
]

ESTADOS_EN_PREP = [
    "LANZADA", 
    "EN PREPARACION", "EN PREPARACIÓN"
]

ESTADOS_PALLETS_LISTOS = [
    "PALLETS COMPLETOS", "PREPARADA", "PREPARADO", 
    "EN CONTROL", "CONTROLADA", "CONTROLADO", 
    "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"
]

ESTADOS_LISTA = [
    "PENDIENTE", "CARENCIA", "CON CARENCIA", "LANZADA", 
    "EN PREPARACION", "EN PREPARACIÓN", "PICKING COMPLETO", 
    "PALLETS COMPLETOS", "PREPARADA", "PREPARADO", 
    "EN CONTROL", "CONTROLADA", "CONTROLADO", 
    "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"
]
ESTADO_PESO = {e: i+1 for i, e in enumerate(ESTADOS_LISTA)}

# =====================================================================
# FUNCIONES Y DATOS
# =====================================================================
@st.cache_data(ttl=15, show_spinner=False)
def obtener_datos():
    try:
        resp = requests.get(URL_GOOGLE_SCRIPT, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                
                # ESCUDO ANTI-CRASH
                cols_num = ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']
                cols_txt = ['Ruta', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte', 'Fecha_Cita']
                
                for col in cols_num:
                    if col not in df.columns: 
                        df[col] = 0
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                    
                for col in cols_txt:
                    if col not in df.columns: 
                        df[col] = ""
                    df[col] = df[col].astype(str).str.strip().str.upper()
                    
                return df
    except Exception:
        pass
    return pd.DataFrame()

def unificar_fechas(fecha_val):
    try:
        if pd.isna(fecha_val) or str(fecha_val).strip() in ["", "SIN FECHA", "NAN", "NaT", "NONE"]: 
            return pd.NaT
        s = str(fecha_val).strip()
        if "/" in s and len(s) <= 12: 
            return pd.to_datetime(f"{s}/{datetime.now().year}", format="%d/%m %H:%M/%Y", errors='coerce')
        
        dt = pd.to_datetime(s, errors='coerce')
        if pd.isna(dt): return pd.NaT
        
        if dt.tz is not None:
            return dt.tz_convert(None) - pd.Timedelta(hours=3)
        return dt
    except Exception: 
        return pd.NaT

def safe_time(val, base_dt):
    if pd.isna(val) or str(val).strip() in ["", "NAN", "NaT", "NONE"]: 
        return pd.NaT
    try:
        s = str(val).strip()
        if ("T" not in s) and (len(s) <= 8) and (":" in s) and pd.notna(base_dt):
            partes = s.split(":")
            return base_dt.replace(hour=int(partes[0]), minute=int(partes[1]), second=0, microsecond=0)
        
        dt = pd.to_datetime(s, errors='coerce')
        if pd.isna(dt): return pd.NaT
        
        if dt.tz is not None:
            dt = dt.tz_convert(None) - pd.Timedelta(hours=3)
            
        if pd.notna(dt) and dt.year < 2000 and pd.notna(base_dt): 
            return dt.replace(year=base_dt.year, month=base_dt.month, day=base_dt.day)
            
        return dt
    except Exception: 
        return pd.NaT

if 'perfil' not in st.session_state: 
    st.session_state.perfil = None

def logout(): 
    st.session_state.perfil = None
    obtener_datos.clear()

# =====================================================================
# INTERFAZ DE LOGIN Y ESTILOS
# =====================================================================
if st.session_state.perfil is None:
    st.markdown("<h2 style='text-align: center;'>👋 Bienvenido al WMS</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🧑‍🔧 Operación", use_container_width=True): 
            st.session_state.perfil = "Operacion"
            st.rerun()
    with c2: 
        if st.button("👁️ Visualizador", use_container_width=True): 
            st.session_state.perfil = "Visualizador"
            st.rerun()
    with c3: 
        if st.button("⚙️ Supervisor", use_container_width=True): 
            st.session_state.perfil = "Supervisor"
            st.rerun()
    st.stop()

st.sidebar.button("Cerrar Sesión", on_click=logout)
st.markdown("""<style>
.kpi-box{background-color:#1E1E24;color:white;padding:12px 5px;border-radius:6px;border-top:4px solid #E55B3C;text-align:center;box-shadow:1px 1px 3px rgba(0,0,0,0.5);} 
.kpi-title{font-size:11px;text-transform:uppercase;opacity:0.8;} 
.kpi-value{font-size:20px;font-weight:bold;margin-top:4px;} 
.card-red{background-color:#b71c1c;border-left:8px solid #ff5252;padding:10px;margin-bottom:10px;} 
.card-yellow{background-color:#f57f17;border-left:8px solid #ffeb3b;padding:10px;margin-bottom:10px;} 
.card-green{background-color:#2e7d32;border-left:8px solid #69f0ae;padding:10px;margin-bottom:10px;}
</style>""", unsafe_allow_html=True)
st.title("📦 Tablero de Seguimiento y Preparado")

# =====================================================================
# PROCESAMIENTO GENERAL
# =====================================================================
df_full = obtener_datos()
if not df_full.empty:
    if 'Fecha_Cita' in df_full.columns:
        df_full['dt_real'] = df_full['Fecha_Cita'].apply(unificar_fechas)
        df_full['Fecha_Cita_str'] = df_full['dt_real'].dt.strftime('%d/%m %H:%M').fillna("-")
    else:
        df_full['dt_real'] = pd.NaT
        df_full['Fecha_Cita_str'] = "-"
    
    if 'Ingreso_Real' not in df_full.columns: df_full['Ingreso_Real'] = np.nan
    if 'Egreso_Real' not in df_full.columns: df_full['Egreso_Real'] = np.nan
    if 'Motivo_Demora' not in df_full.columns: df_full['Motivo_Demora'] = ""
    
    df_full['dt_In'] = df_full.apply(lambda r: safe_time(r.get('Ingreso_Real'), r.get('dt_real')), axis=1)
    df_full['dt_Out'] = df_full.apply(lambda r: safe_time(r.get('Egreso_Real'), r.get('dt_real')), axis=1)
    
    df_full['Estadia_Hs'] = (df_full['dt_Out'] - df_full['dt_In']).dt.total_seconds() / 3600
    df_full['Ingreso'] = df_full['dt_In'].dt.strftime('%H:%M').fillna('-')
    df_full['Egreso'] = df_full['dt_Out'].dt.strftime('%H:%M').fillna('-')
    df_full['Estadia (Hs)'] = df_full['Estadia_Hs'].apply(lambda x: f"{x:.1f}" if pd.notna(x) and x > 0 else "-")
    
    # 📌 CÁLCULO DE SLA: Toma el MAYOR entre la Hora de Cita y la Hora de Llegada
    df_full['Hora_SLA_Base'] = df_full[['dt_real', 'dt_In']].max(axis=1)
    df_full['Desvio_Total_Hs'] = (df_full['dt_Out'] - df_full['Hora_SLA_Base']).dt.total_seconds() / 3600

tab_op, tab_mon, tab_sup, tab_res = st.tabs(["📲 Vista Operativa", "📱 Monitor de Cargas", "⚙️ Supervisor (Carga)", "📊 Resumen Ejecutivo"])

# =====================================================================
# TAB 1: OPERATIVA
# =====================================================================
with tab_op:
    if not df_full.empty and 'Estado' in df_full.columns:
        df_act = df_full[~df_full['Estado'].str.contains('DESPACHA', na=False, case=False)].copy()
        if df_act.empty: 
            st.success("Todo despachado.")
        else:
            cajas_pendientes_total = df_act[df_act['Estado'].isin(ESTADOS_PENDIENTES_CAJAS)]['Cajas_Picking'].sum()
            cajas_en_preparacion = df_act[df_act['Estado'].isin(ESTADOS_EN_PREP)]['Cajas_Picking'].sum()
            pallets_ptes = df_act[~df_act['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()
            
            df_pt = df_act[df_act['Estado'].isin(ESTADOS_PENDIENTES_CAJAS)].copy()
            df_pt['PHr'] = np.where(df_pt['Average_Picking'] > 0, (df_pt['Average_Picking'] / 10) * 124, 124)
            h_dec = np.where(df_pt['Cajas_Picking'] > 0, df_pt['Cajas_Picking'] / df_pt['PHr'], 0).sum()
            
            k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
            k1.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Rutas</div><div class='kpi-value'>{df_act['Ruta'].nunique()}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-box'><div class='kpi-title'>Órdenes</div><div class='kpi-value'>{len(df_act)}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-box'><div class='kpi-title'>Pallets Ptes</div><div class='kpi-value'>{pallets_ptes}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Ptes</div><div class='kpi-value'>{cajas_pendientes_total}</div></div>", unsafe_allow_html=True)
            k5.markdown(f"<div class='kpi-box'><div class='kpi-title'>Horas Pick</div><div class='kpi-value'>{f'{int(h_dec*60)//60:02d}:{int(h_dec*60)%60:02d}'}</div></div>", unsafe_allow_html=True)
            k6.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas en Prep.</div><div class='kpi-value'>{cajas_en_preparacion}</div></div>", unsafe_allow_html=True)
            k7.markdown(f"<div class='kpi-box'><div class='kpi-title'>Top Salida</div><div class='kpi-value'>{len(df_act[df_act['Estado'] == 'TOP SALIDA'])}</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            _, cb, _ = st.columns([1, 2, 1])
            with cb:
                if st.button("🔄 Sincronizar Horarios (Seguridad)", use_container_width=True):
                    with st.spinner("Sincronizando..."):
                        requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "SINCRONIZAR_TIEMPOS"}))
                        obtener_datos.clear()
                        st.rerun()
            
            cols = ['Fecha_Cita_str', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Ingreso', 'Egreso', 'Estadia (Hs)', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking']
            st.dataframe(df_act[[c for c in cols if c in df_act.columns]].sort_values(by=['Fecha_Cita_str', 'Ruta']), use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos para mostrar en Vista Operativa.")

# =====================================================================
# TAB 2: MONITOR Y FALLAS (AGRUPADO POR RUTA Y CLIENTE)
# =====================================================================
with tab_mon:
    col_izq, col_der = st.columns([2, 1])
    with col_izq:
        st.subheader("🎯 Monitor de Citas")
        if not df_full.empty and 'dt_real' in df_full.columns:
            df_m = df_full[~df_full['Estado'].str.contains('DESPACHA', na=False, case=False)].dropna(subset=['dt_real']).copy()
            ahora = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
            for f_str, grp in df_m.groupby(df_m['dt_real'].dt.strftime('%d/%m %H:%M')):
                min_d = (ahora - grp['dt_real'].iloc[0]).total_seconds() / 60
                pes = grp['Estado'].map(ESTADO_PESO).min() if 'Estado' in grp.columns else 12
                c_col, t = ("card-red", "🚨 Cita cumplida (Falta control)") if min_d >= 0 and pes < 8 else (("card-yellow", "🟡 Ventana 3hs") if 0 <= min_d <= 180 else (("card-red", "🚨 Vencido") if min_d > 180 else ("card-green", f"🟢 Faltan {int(abs(min_d))}m")))
                st.markdown(f"<div class='{c_col}'><b>Cita: {f_str}</b> | {t} | Órdenes: {len(grp)}</div>", unsafe_allow_html=True)
                
    with col_der:
        st.subheader("⚠️ Desvíos SLA (>3Hs)")
        if not df_full.empty and 'Desvio_Total_Hs' in df_full.columns:
            df_fallas = df_full[(df_full['Desvio_Total_Hs'] > 3) & (df_full['Motivo_Demora'].astype(str).str.strip() == "")].copy()
            if df_fallas.empty: 
                st.success("Sin desvíos pendientes de justificar.")
            else:
                rutas_fallas = df_fallas['Ruta'].unique()
                st.warning(f"{len(rutas_fallas)} Rutas requieren justificación (total {len(df_fallas)} órdenes).")
                
                # Agrupar por Ruta para cargar todo junto
                fallas_dict = {}
                for ruta in rutas_fallas:
                    df_ruta = df_fallas[df_fallas['Ruta'] == ruta]
                    clientes = " | ".join(df_ruta['Cliente'].unique())
                    desvio_max = df_ruta['Desvio_Total_Hs'].max()
                    ids_entrega = df_ruta['Id_Entrega'].tolist()
                    
                    label = f"Ruta: {ruta} - Cliente: {clientes} - Desvío: {desvio_max:.1f}hs"
                    fallas_dict[label] = ids_entrega
                
                f_sel = st.selectbox("Seleccione Ruta a Justificar:", list(fallas_dict.keys()))
                mot = st.text_input("Motivo de Falla (Justificación):")
                
                if st.button("Guardar Motivo (Aplica a toda la ruta)", use_container_width=True) and mot:
                    with st.spinner("Guardando..."):
                        ids_to_update = fallas_dict[f_sel]
                        for id_ent in ids_to_update:
                            requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "CARGAR_MOTIVO", "Id_Entrega": str(id_ent), "Motivo": mot}))
                    obtener_datos.clear()
                    st.rerun()

# =====================================================================
# TAB 3: SUPERVISOR (CARGA)
# =====================================================================
with tab_sup:
    st.subheader("Carga de Planificación")
    f_p = st.file_uploader("1. Reporte Excel", type=["xlsx", "xls"])
    f_m = st.file_uploader("2. Maestro LPK", type=["xlsx", "xls"])
    if st.button("Procesar Planificación") and f_p and f_m:
        try:
            df_p = pd.read_excel(f_p).rename(columns={"FechaHoraDespacho":'Fecha_Cita',"IdRuta":'Ruta',"Número de orden de ventas de origen":'Orden_Entrega',"IdEntrega":'Id_Entrega',"Nombre de organización":'Cliente',"IdTransportista":'Transporte',"Artículo":'Codigo',"Cantidad solicitada secundaria":'Cantidad_Cajas',"OrdenCarga":'Orden_Descarga'})
            df_m = pd.read_excel(f_m).rename(columns={"Artículo - Nombre":'Codigo', "LPK - Cajas por Pallet":'LPK'})
            df_c = pd.merge(df_p.assign(Codigo=df_p['Codigo'].astype(str)), df_m.assign(Codigo=df_m['Codigo'].astype(str))[['Codigo', 'LPK']], on='Codigo', how='left')
            df_c['Cantidad_Cajas'], df_c['LPK'] = pd.to_numeric(df_c['Cantidad_Cajas'], errors='coerce').fillna(0), pd.to_numeric(df_c['LPK'], errors='coerce').fillna(1)
            fechas = pd.to_datetime(df_c['Fecha_Cita'], errors='coerce')
            if fechas.dt.tz is not None: 
                fechas = fechas.dt.tz_convert(None)
            df_c['Fecha_Cita'] = (fechas - pd.Timedelta(hours=3)).dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
            df_c['Pallets_Completos'] = (df_c['Cantidad_Cajas'] // df_c['LPK']).astype(int)
            df_c['Cajas_Picking'] = (df_c['Cantidad_Cajas'] % df_c['LPK']).astype(int)
            df_c['Lineas_Picking'] = np.where(df_c['Cajas_Picking'] > 0, 1, 0)
            df_g = df_c.groupby(['Fecha_Cita','Ruta','Orden_Entrega','Id_Entrega','Cliente','Transporte']).agg({'Cajas_Picking':'sum','Pallets_Completos':'sum','Lineas_Picking':'sum','Orden_Descarga':'min'}).reset_index()
            df_g['Average_Picking'] = np.where(df_g['Lineas_Picking'] > 0, np.ceil(df_g['Cajas_Picking'] / df_g['Lineas_Picking']), 0).astype(int)
            df_g['Orden_Carga'] = df_g.groupby('Ruta')['Orden_Descarga'].rank(ascending=False, method='min').fillna(1).astype(int) if 'Orden_Descarga' in df_g.columns else 1
            if not df_full.empty: 
                df_g = df_g[~df_g['Id_Entrega'].astype(str).isin(df_full['Id_Entrega'].astype(str).tolist())]
            
            if df_g.empty: 
                st.warning("Órdenes ya cargadas.")
            else:
                with st.spinner("Enviando..."):
                    for _, r in df_g.iterrows():
                        requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion":"CARGAR_PLAN", "Fecha_Cita":str(r['Fecha_Cita']), "Ruta":str(r['Ruta']), "Orden_Entrega":str(r['Orden_Entrega']), "Id_Entrega":str(r['Id_Entrega']), "Cliente":str(r['Cliente']), "Transporte":str(r['Transporte']), "Cajas_Picking":int(r['Cajas_Picking']), "Pallets_Completos":int(r['Pallets_Completos']), "Average_Picking":int(r['Average_Picking']), "Orden_Carga":int(r['Orden_Carga'])}))
                    obtener_datos.clear()
                    st.success("Cargado!")
        except Exception as e: 
            st.error(f"Error Excel: {e}")

# =====================================================================
# TAB 4: RESUMEN EJECUTIVO Y MOTOR DE SIMULACIÓN DE COLAS
# =====================================================================
with tab_res:
    st.markdown("<h2 style='text-align: left;'>📊 Resumen Ejecutivo y Productividad</h2>", unsafe_allow_html=True)
    if not df_full.empty and 'dt_real' in df_full.columns:
        now_dt = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
        hoy = now_dt.date()
        df_res = df_full.copy()
            
        st.markdown("### 📌 Snapshot Operativo: HOY")
        df_hoy = df_res[df_res['dt_real'].apply(lambda x: isinstance(x, (datetime, date)) and x.date() == hoy if pd.notna(x) else False)]
        if df_hoy.empty: 
            st.info("No hay planificación registrada para hoy.")
        else:
            c1, c2, c3 = st.columns(3)
            caj_plan_hoy = df_hoy['Cajas_Picking'].sum()
            caj_pte_hoy = df_hoy[df_hoy['Estado'].isin(ESTADOS_PENDIENTES_CAJAS)]['Cajas_Picking'].sum()
            caj_ok_hoy = max(0, caj_plan_hoy - caj_pte_hoy)
            
            pal_plan_hoy = df_hoy['Pallets_Completos'].sum()
            pal_ok_hoy = df_hoy[df_hoy['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()
            
            rut_plan_hoy = df_hoy['Ruta'].nunique()
            rut_ok_hoy = df_hoy[df_hoy['Estado'].str.contains('DESPACHA', na=False, case=False)]['Ruta'].nunique()

            c1.metric("Cajas Pickeadas (Hoy)", f"{caj_ok_hoy} / {caj_plan_hoy}")
            c2.metric("Pallets Preps (Hoy)", f"{pal_ok_hoy} / {pal_plan_hoy}")
            c3.metric("Rutas Despachadas (Hoy)", f"{rut_ok_hoy} / {rut_plan_hoy}")
        
        st.write("---")
        st.markdown("### 📈 Histórico y Proyección Diaria")
        
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
        primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
        
        periodos = [
            {"nombre": "Mes Pasado", "filtro": lambda d: primer_dia_mes_pasado <= d <= ultimo_dia_mes_pasado},
            {"nombre": "Acum. Este Mes", "filtro": lambda d: primer_dia_mes_actual <= d <= hoy},
            {"nombre": "Ayer", "filtro": lambda d: d == (hoy - timedelta(days=1))},
            {"nombre": "Hoy", "filtro": lambda d: d == hoy},
        ]
        
        fechas_futuras = []
        for val in df_res['dt_real'].dropna():
            if hasattr(val, 'date'):
                d_val = val.date()
                if isinstance(d_val, date) and d_val > hoy and d_val not in fechas_futuras:
                    fechas_futuras.append(d_val)
        
        fechas_futuras.sort()
        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        
        for f in fechas_futuras:
            nom_f = f"{f.strftime('%d/%m')} ({dias_semana[f.weekday()]})"
            periodos.append({
                "nombre": nom_f, 
                "filtro": lambda d, target_date=f: d == target_date
            })
        
        datos_tabla = []
        for p in periodos:
            df_p = df_res[df_res['dt_real'].apply(lambda x: p["filtro"](x.date()) if pd.notna(x) and hasattr(x, 'date') else False)]
            rut_p = df_p['Ruta'].nunique()
            rut_o = df_p[df_p['Estado'].str.contains('DESPACHA', na=False, case=False)]['Ruta'].nunique()
            caj_p = df_p['Cajas_Picking'].sum()
            caj_pte = df_p[df_p['Estado'].isin(ESTADOS_PENDIENTES_CAJAS)]['Cajas_Picking'].sum()
            caj_o = max(0, caj_p - caj_pte)
            pal_p = df_p['Pallets_Completos'].sum()
            pal_ok = df_p[df_p['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()
            
            t_prom = df_p[df_p['Estado'].str.contains('DESPACHA', na=False, case=False)]['Estadia_Hs'].mean() if 'Estadia_Hs' in df_p.columns else np.nan
            
            datos_tabla.append({
                "Período": p["nombre"], 
                "🚚 Rutas": f"{rut_o} / {rut_p}", 
                "% Rutas": int(rut_o / rut_p * 100) if rut_p > 0 else 0, 
                "📦 Cajas": f"{int(caj_o)} / {int(caj_p)}", 
                "% Cajas": int(caj_o / caj_p * 100) if caj_p > 0 else 0, 
                "🧱 Pallets": f"{int(pal_ok)} / {int(pal_p)}", 
                "% Pallets": int(pal_ok / pal_p * 100) if pal_p > 0 else 0, 
                "⏱️ Demora": f"{t_prom:.1f} hs" if pd.notna(t_prom) else "-"
            })
            
        st.dataframe(
            pd.DataFrame(datos_tabla), 
            column_config={
                "Período": st.column_config.TextColumn("📅 Período"), 
                "% Rutas": st.column_config.ProgressColumn("Avance Rutas", max_value=100, format="%d%%"), 
                "% Cajas": st.column_config.ProgressColumn("Avance Cajas", max_value=100, format="%d%%"), 
                "% Pallets": st.column_config.ProgressColumn("Avance Pallets", max_value=100, format="%d%%")
            }, 
            use_container_width=True, 
            hide_index=True
        )

        # =====================================================================
        # 🚀 MOTOR DE SIMULACIÓN DE COLAS (FÍSICA DINÁMICA DE TIEMPOS)
        # =====================================================================
        st.write("---")
        st.markdown("### ⚙️ Flujo Continuo: Simulación de SLA y Línea de Tiempo (Próximos 6 Turnos)")
        st.caption("Asigne dotación. El gráfico evalúa el esfuerzo real de cada orden en base a su *Average Picking*, mostrando a qué hora del turno finaliza, se atrasa o queda personal libre.")
        
        hr_exact = now_dt.hour + (now_dt.minute / 60)
        
        if 6 <= hr_exact < 14:
            idx_actual = 0
            end_actual = now_dt.replace(hour=14, minute=0, second=0, microsecond=0)
        elif 14 <= hr_exact < 22:
            idx_actual = 1
            end_actual = now_dt.replace(hour=22, minute=0, second=0, microsecond=0)
        else:
            idx_actual = 2
            if hr_exact >= 22:
                end_actual = (now_dt + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
            else:
                end_actual = now_dt.replace(hour=6, minute=0, second=0, microsecond=0)

        nombres_turnos = ["T.Mañana (06-14)", "T.Tarde (14-22)", "T.Noche (22-06)"]
        turnos_sim = []
        curr_start = now_dt
        
        for i in range(6):
            t_idx = (idx_actual + i) % 3
            t_name = nombres_turnos[t_idx]
            
            if i == 0:
                t_name = f"{nombres_turnos[t_idx][:8]} (ACTUAL)"
                t_end = end_actual
                t_dur = (t_end - curr_start).total_seconds() / 3600.0
            else:
                t_name = f"{nombres_turnos[t_idx][:8]} ({curr_start.strftime('%d/%m')})"
                t_end = curr_start + timedelta(hours=8)
                t_dur = 8.0
                
            turnos_sim.append({
                "nombre": t_name,
                "start": curr_start,
                "end": t_end,
                "duracion": max(0.1, t_dur), 
                "dot": 0
            })
            curr_start = t_end

        cols_turnos = st.columns(6)
        for i, (col, t) in enumerate(zip(cols_turnos, turnos_sim)):
            lbl = t['nombre'].replace(" (ACTUAL)", "\n(ACTUAL)")
            def_val = 5 if i < 3 else 0
            t['dot'] = col.number_input(f"Turno {i+1}:\n{lbl} ({t['duracion']:.1f}h)", min_value=0, value=def_val, key=f"dot_{i}")

        df_p = df_full[~df_full['Estado'].str.contains('DESPACHA', na=False, case=False)].copy()
        df_p = df_p[df_p['Estado'].isin(ESTADOS_PENDIENTES_CAJAS)]
        df_p = df_p[df_p['Cajas_Picking'] > 0]
        
        df_p = df_p.sort_values(by='dt_real', na_position='last')
        cola_pedidos = df_p[['Id_Entrega', 'Cajas_Picking', 'dt_real', 'Average_Picking']].to_dict('records')

        reloj_simulado = now_dt
        y_labels, ok_vals, late_vals, free_vals = [], [], [], []
        ok_texts, late_texts, free_texts = [], [], []
        cajas_procesadas_list = []

        for t in turnos_sim:
            horas_disp = t['duracion']
            horas_ok = 0.0
            horas_atraso = 0.0
            cajas_procesadas_turno = 0
            
            reloj_inicio_turno = reloj_simulado

            if t['dot'] > 0:
                while horas_disp > 0 and len(cola_pedidos) > 0:
                    orden = cola_pedidos[0]
                    
                    av_pick = orden.get('Average_Picking', 10.0)
                    if pd.isna(av_pick) or av_pick <= 0:
                        av_pick = 10.0 
                        
                    velocidad_persona = (av_pick / 10.0) * 124.0
                    velocidad_turno = t['dot'] * velocidad_persona
                    
                    cap_cajas_restante = horas_disp * velocidad_turno
                    cajas_a_picar = min(cap_cajas_restante, orden['Cajas_Picking'])
                    
                    horas_tomadas = cajas_a_picar / velocidad_turno
                    reloj_simulado += timedelta(hours=horas_tomadas)
                    
                    if pd.isna(orden['dt_real']) or reloj_simulado <= orden['dt_real']:
                        horas_ok += horas_tomadas
                    else:
                        horas_atraso += horas_tomadas
                        
                    horas_disp -= horas_tomadas
                    orden['Cajas_Picking'] -= cajas_a_picar
                    cajas_procesadas_turno += cajas_a_picar
                    
                    if orden['Cajas_Picking'] <= 0:
                        cola_pedidos.pop(0)

            horas_libres = horas_disp
            reloj_simulado = t['end']

            y_labels.append(f"<b>T{turnos_sim.index(t)+1}: {t['nombre']}</b><br>{t['start'].strftime('%H:%M')} a {t['end'].strftime('%H:%M')} ({t['dot']}p)")
            
            ok_vals.append(horas_ok)
            late_vals.append(horas_atraso)
            free_vals.append(horas_libres)
            cajas_procesadas_list.append(cajas_procesadas_turno)
            
            h_fin_ok = reloj_inicio_turno + timedelta(hours=horas_ok)
            h_fin_atraso = h_fin_ok + timedelta(hours=horas_atraso)
            
            ok_texts.append(f"🟢 Hasta {h_fin_ok.strftime('%H:%M')}" if horas_ok > 0.05 else "")
            late_texts.append(f"🔴 Hasta {h_fin_atraso.strftime('%H:%M')}" if horas_atraso > 0.05 else "")
            free_texts.append(f"⚪ Libre desde {h_fin_atraso.strftime('%H:%M')}" if horas_libres > 0.05 else "")

        fig = go.Figure()
        fig.add_trace(go.Bar(y=y_labels[::-1], x=ok_vals[::-1], name='A Tiempo', orientation='h', marker=dict(color='#2e7d32'), text=ok_texts[::-1], textposition='inside'))
        fig.add_trace(go.Bar(y=y_labels[::-1], x=late_vals[::-1], name='Atraso (SLA Vencido)', orientation='h', marker=dict(color='#d32f2f'), text=late_texts[::-1], textposition='inside'))
        fig.add_trace(go.Bar(y=y_labels[::-1], x=free_vals[::-1], name='Capacidad Ociosa (Libre)', orientation='h', marker=dict(color='#555555'), text=free_texts[::-1], textposition='inside'))

        for i, y_lbl in enumerate(y_labels[::-1]):
            total_cajas = cajas_procesadas_list[::-1][i]
            duracion_turno = turnos_sim[::-1][i]['duracion']
            if total_cajas > 0:
                fig.add_annotation(
                    x=duracion_turno + 0.1, 
                    y=y_lbl,
                    text=f"<b>📦 {int(total_cajas)} cjs</b>",
                    showarrow=False,
                    font=dict(color="white", size=13),
                    xanchor="left"
                )

        fig.update_layout(
            barmode='stack', bargap=0.15, height=500, plot_bgcolor='rgba(0,0,0,0)', 
            font=dict(color='white'), legend=dict(orientation="h", yanchor="bottom"),
            xaxis=dict(title='Horas Consumidas del Turno', gridcolor='rgba(255,255,255,0.1)', ticksuffix="h", range=[0, 9.5])
        )
        st.plotly_chart(fig, use_container_width=True)
        
        cajas_sobrantes = sum([o['Cajas_Picking'] for o in cola_pedidos])
        if cajas_sobrantes > 0:
            st.warning(f"⚠️ Atención: Después del 6º turno aún quedarán **{int(cajas_sobrantes)} cajas** pendientes en la cola. Necesitarás aumentar la dotación o agregar más turnos operativos.")
            
    else:
        st.info("Recolectando datos...")
