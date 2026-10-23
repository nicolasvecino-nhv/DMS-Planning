import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL NUEVA:
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbzgzGx9-wP9tNjgeoJYuBpM7Fd--e1Q_J695qHNTI7JUik_SU_NZVdZWmh5iQ8c-7hv/exec"

st.set_page_config(layout="wide", page_title="WMS Dashboard", page_icon="📦")

ESTADOS_CAJAS = ["PICKING COMPLETO", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"]
ESTADOS_PALLETS = ["PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"]
ESTADOS_LISTA = ["PENDIENTE", "CARENCIA", "LANZADA", "EN PREPARACIÓN", "PICKING COMPLETO", "PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA"]
ESTADO_PESO = {e: i+1 for i, e in enumerate(ESTADOS_LISTA)}

# =====================================================================
# FUNCIONES Y DATOS
# =====================================================================
@st.cache_data(ttl=15, show_spinner=False)
def obtener_datos():
    try:
        resp = requests.get(URL_GOOGLE_SCRIPT, timeout=15)
        if resp.status_code == 200 and len(resp.json()) > 0:
            df = pd.DataFrame(resp.json())
            
            # ESCUDO ANTI-CRASH
            cols_num = ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']
            cols_txt = ['Ruta', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte', 'Fecha_Cita']
            
            for col in cols_num:
                if col not in df.columns: df[col] = 0
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                
            for col in cols_txt:
                if col not in df.columns: df[col] = ""
                df[col] = df[col].astype(str).str.strip().str.upper()
                
            return df
    except: pass
    return pd.DataFrame()

def unificar_fechas(fecha_val):
    try:
        if pd.isna(fecha_val) or str(fecha_val).strip() in ["", "SIN FECHA", "NAN", "NaT"]: return pd.NaT
        s = str(fecha_val).strip()
        if "/" in s and len(s) <= 12: return pd.to_datetime(f"{s}/{datetime.now().year}", format="%d/%m %H:%M/%Y", errors='coerce')
        
        # Corrección de zona horaria / epoch 1899
        dt = pd.to_datetime(s, utc=True).tz_localize(None)
        return dt - pd.Timedelta(hours=3)
    except: return pd.NaT

def safe_time(val, base_dt):
    if pd.isna(val) or str(val).strip() == "": return pd.NaT
    try:
        s = str(val).strip()
        if len(s) <= 5 and ":" in s and pd.notna(base_dt): 
            return pd.to_datetime(f"{base_dt.strftime('%Y-%m-%d')} {s}", errors='coerce')
        
        dt = pd.to_datetime(s, utc=True).tz_localize(None)
        dt = dt - pd.Timedelta(hours=3)
        
        if pd.notna(dt) and dt.year < 2000 and pd.notna(base_dt): 
            return dt.replace(year=base_dt.year, month=base_dt.month, day=base_dt.day)
        return dt
    except: return pd.NaT

if 'perfil' not in st.session_state: st.session_state.perfil = None
def logout(): st.session_state.perfil = None; obtener_datos.clear()

# =====================================================================
# INTERFAZ DE LOGIN Y ESTILOS
# =====================================================================
if st.session_state.perfil is None:
    st.markdown("<h2 style='text-align: center;'>👋 Bienvenido al WMS</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🧑‍🔧 Operación", use_container_width=True): st.session_state.perfil = "Operacion"; st.rerun()
    with c2: 
        if st.button("👁️ Visualizador", use_container_width=True): st.session_state.perfil = "Visualizador"; st.rerun()
    with c3: 
        if st.button("⚙️ Supervisor", use_container_width=True): st.session_state.perfil = "Supervisor"; st.rerun()
    st.stop()

st.sidebar.button("Cerrar Sesión", on_click=logout)
st.markdown("""<style>.kpi-box{background-color:#1E1E24;color:white;padding:12px 5px;border-radius:6px;border-top:4px solid #E55B3C;text-align:center;box-shadow:1px 1px 3px rgba(0,0,0,0.5);} .kpi-title{font-size:11px;text-transform:uppercase;opacity:0.8;} .kpi-value{font-size:20px;font-weight:bold;margin-top:4px;} .card-red{background-color:#b71c1c;border-left:8px solid #ff5252;padding:10px;margin-bottom:10px;} .card-yellow{background-color:#f57f17;border-left:8px solid #ffeb3b;padding:10px;margin-bottom:10px;} .card-green{background-color:#2e7d32;border-left:8px solid #69f0ae;padding:10px;margin-bottom:10px;}</style>""", unsafe_allow_html=True)
st.title("📦 Tablero de Seguimiento y Preparado")

# =====================================================================
# PROCESAMIENTO GENERAL
# =====================================================================
df_full = obtener_datos()
if not df_full.empty:
    if 'Fecha_Cita' in df_full.columns:
        df_full['dt_real'] = df_full['Fecha_Cita'].apply(unificar_fechas)
        df_full['Fecha_Cita_str'] = df_full['dt_real'].dt.strftime('%d/%m %H:%M').fillna("-")
    
    if 'Ingreso_Real' not in df_full.columns: df_full['Ingreso_Real'] = np.nan
    if 'Egreso_Real' not in df_full.columns: df_full['Egreso_Real'] = np.nan
    if 'Motivo_Demora' not in df_full.columns: df_full['Motivo_Demora'] = ""
    
    if 'dt_real' in df_full.columns:
        df_full['dt_In'] = df_full.apply(lambda r: safe_time(r.get('Ingreso_Real'), r.get('dt_real')), axis=1)
        df_full['dt_Out'] = df_full.apply(lambda r: safe_time(r.get('Egreso_Real'), r.get('dt_real')), axis=1)
        
        df_full['Estadia_Hs'] = (df_full['dt_Out'] - df_full['dt_In']).dt.total_seconds() / 3600
        
        df_full['Ingreso'] = df_full['dt_In'].dt.strftime('%H:%M').fillna('-')
        df_full['Egreso'] = df_full['dt_Out'].dt.strftime('%H:%M').fillna('-')
        df_full['Estadia (Hs)'] = df_full['Estadia_Hs'].apply(lambda x: f"{x:.1f}" if pd.notna(x) and x>0 else "-")
        
        df_full['Hora_Minima'] = df_full[['dt_real', 'dt_In']].min(axis=1)
        df_full['Desvio_Total_Hs'] = (df_full['dt_Out'] - df_full['Hora_Minima']).dt.total_seconds() / 3600

tab_op, tab_mon, tab_sup, tab_res = st.tabs(["📲 Vista Operativa", "📱 Monitor de Cargas", "⚙️ Supervisor (Carga)", "📊 Resumen Ejecutivo"])

# =====================================================================
# TAB 1: OPERATIVA
# =====================================================================
with tab_op:
    if not df_full.empty and 'Estado' in df_full.columns:
        df_act = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        if df_act.empty: st.success("Todo despachado.")
        else:
            cj_listas = df_act[df_act['Estado'].isin(ESTADOS_CAJAS)]['Cajas_Picking'].sum()
            df_pt = df_act[~df_act['Estado'].isin(ESTADOS_CAJAS)].copy()
            df_pt['PHr'] = np.where(df_pt['Average_Picking'] > 0, (df_pt['Average_Picking']/10)*124, 124)
            h_dec = np.where(df_pt['Cajas_Picking']>0, df_pt['Cajas_Picking']/df_pt['PHr'], 0).sum()
            
            k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
            k1.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Rutas</div><div class='kpi-value'>{df_act['Ruta'].nunique()}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-box'><div class='kpi-title'>Órdenes</div><div class='kpi-value'>{len(df_act)}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-box'><div class='kpi-title'>Pallets Ptes</div><div class='kpi-value'>{df_act['Pallets_Completos'].sum() - df_act[df_act['Estado'].isin(ESTADOS_PALLETS)]['Pallets_Completos'].sum()}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Ptes</div><div class='kpi-value'>{df_act['Cajas_Picking'].sum() - cj_listas}</div></div>", unsafe_allow_html=True)
            k5.markdown(f"<div class='kpi-box'><div class='kpi-title'>Horas Pick</div><div class='kpi-value'>{f'{int(h_dec*60)//60:02d}:{int(h_dec*60)%60:02d}'}</div></div>", unsafe_allow_html=True)
            k6.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Pista</div><div class='kpi-value'>{df_act[df_act['Estado'].isin(['LANZADA', 'EN PREPARACIÓN'])]['Cajas_Picking'].sum()}</div></div>", unsafe_allow_html=True)
            k7.markdown(f"<div class='kpi-box'><div class='kpi-title'>Top Salida</div><div class='kpi-value'>{len(df_act[df_act['Estado'] == 'TOP SALIDA'])}</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            _, cb, _ = st.columns([1,2,1])
            with cb:
                if st.button("🔄 Sincronizar Horarios (Seguridad)", use_container_width=True):
                    with st.spinner("Sincronizando..."):
                        requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "SINCRONIZAR_TIEMPOS"}))
                        obtener_datos.clear(); st.rerun()
            
            cols = ['Fecha_Cita_str', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Ingreso', 'Egreso', 'Estadia (Hs)', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking']
            st.dataframe(df_act[[c for c in cols if c in df_act.columns]].sort_values(by=['Fecha_Cita_str', 'Ruta']), use_container_width=True, hide_index=True)

# =====================================================================
# TAB 2: MONITOR Y FALLAS
# =====================================================================
with tab_mon:
    col_izq, col_der = st.columns([2, 1])
    with col_izq:
        st.subheader("🎯 Monitor de Citas")
        if not df_full.empty and 'dt_real' in df_full.columns:
            df_m = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].dropna(subset=['dt_real']).copy()
            ahora = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
            for f_str, grp in df_m.groupby(df_m['dt_real'].dt.strftime('%d/%m %H:%M')):
                min_d = (ahora - grp['dt_real'].iloc[0]).total_seconds()/60
                pes = grp['Estado'].map(ESTADO_PESO).min() if 'Estado' in grp.columns else 12
                c_col, t = ("card-red", "🚨 Cita cumplida (Falta control)") if min_d>=0 and pes<8 else (("card-yellow", "🟡 Ventana 3hs") if 0<=min_d<=180 else (("card-red", "🚨 Vencido") if min_d>180 else ("card-green", f"🟢 Faltan {int(abs(min_d))}m")))
                st.markdown(f"<div class='{c_col}'><b>Cita: {f_str}</b> | {t} | Órdenes: {len(grp)}</div>", unsafe_allow_html=True)
                
    with col_der:
        st.subheader("⚠️ Desvíos SLA (>3Hs)")
        if not df_full.empty and 'Desvio_Total_Hs' in df_full.columns:
            df_fallas = df_full[(df_full['Desvio_Total_Hs'] > 3) & (df_full['Motivo_Demora'].astype(str).str.strip() == "")].copy()
            if df_fallas.empty: st.success("Sin desvíos pendientes de justificar.")
            else:
                st.warning(f"{len(df_fallas)} órdenes requieren justificación.")
                fallas_dict = {f"Entrega: {r['Id_Entrega']} (Ruta {r['Ruta']}) - Desvío: {r['Desvio_Total_Hs']:.1f}hs": r['Id_Entrega'] for _, r in df_fallas.iterrows()}
                f_sel = st.selectbox("Seleccione Orden:", list(fallas_dict.keys()))
                mot = st.text_input("Motivo de Falla (Justificación):")
                if st.button("Guardar Motivo", use_container_width=True) and mot:
                    requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "CARGAR_MOTIVO", "Id_Entrega": fallas_dict[f_sel], "Motivo": mot}))
                    obtener_datos.clear(); st.rerun()

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
            if fechas.dt.tz is not None: fechas = fechas.dt.tz_convert(None)
            df_c['Fecha_Cita'] = (fechas - pd.Timedelta(hours=3)).dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
            df_c['Pallets_Completos'] = (df_c['Cantidad_Cajas'] // df_c['LPK']).astype(int)
            df_c['Cajas_Picking'] = (df_c['Cantidad_Cajas'] % df_c['LPK']).astype(int)
            df_c['Lineas_Picking'] = np.where(df_c['Cajas_Picking']>0, 1, 0)
            df_g = df_c.groupby(['Fecha_Cita','Ruta','Orden_Entrega','Id_Entrega','Cliente','Transporte']).agg({'Cajas_Picking':'sum','Pallets_Completos':'sum','Lineas_Picking':'sum','Orden_Descarga':'min'}).reset_index()
            df_g['Average_Picking'] = np.where(df_g['Lineas_Picking']>0, np.ceil(df_g['Cajas_Picking']/df_g['Lineas_Picking']), 0).astype(int)
            df_g['Orden_Carga'] = df_g.groupby('Ruta')['Orden_Descarga'].rank(ascending=False, method='min').fillna(1).astype(int) if 'Orden_Descarga' in df_g.columns else 1
            if not df_full.empty: df_g = df_g[~df_g['Id_Entrega'].astype(str).isin(df_full['Id_Entrega'].astype(str).tolist())]
            
            if df_g.empty: st.warning("Órdenes ya cargadas.")
            else:
                with st.spinner("Enviando..."):
                    for _, r in df_g.iterrows():
                        requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion":"CARGAR_PLAN", "Fecha_Cita":str(r['Fecha_Cita']), "Ruta":str(r['Ruta']), "Orden_Entrega":str(r['Orden_Entrega']), "Id_Entrega":str(r['Id_Entrega']), "Cliente":str(r['Cliente']), "Transporte":str(r['Transporte']), "Cajas_Picking":int(r['Cajas_Picking']), "Pallets_Completos":int(r['Pallets_Completos']), "Average_Picking":int(r['Average_Picking']), "Orden_Carga":int(r['Orden_Carga'])}))
                    obtener_datos.clear(); st.success("Cargado!")
        except Exception as e: st.error(f"Error Excel: {e}")

# =====================================================================
# TAB 4: RESUMEN EJECUTIVO (DINÁMICO DÍA A DÍA)
# =====================================================================
with tab_res:
    st.markdown("<h2 style='text-align: left;'>📊 Resumen Ejecutivo y Productividad</h2>", unsafe_allow_html=True)
    if not df_full.empty and 'dt_real' in df_full.columns:
        now_dt = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
        hoy = now_dt.date()
        df_res = df_full.copy()
        df_res['Tiempo_Carga_Hs'] = (df_res['dt_Out'] - df_res['dt_real']).dt.total_seconds() / 3600 if 'dt_Out' in df_res.columns else np.nan
            
        st.markdown("### 📌 Snapshot Operativo: HOY")
        df_hoy = df_res[df_res['dt_real'].apply(lambda x: x.date() == hoy if pd.notna(x) else False)]
        if df_hoy.empty: 
            st.info("No hay planificación registrada para hoy.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Cajas Pickeadas (Hoy)", f"{df_hoy[df_hoy['Estado'].isin(ESTADOS_CAJAS)]['Cajas_Picking'].sum()} / {df_hoy['Cajas_Picking'].sum()}")
            c2.metric("Pallets Preps (Hoy)", f"{df_hoy[df_hoy['Estado'].isin(ESTADOS_PALLETS)]['Pallets_Completos'].sum()} / {df_hoy['Pallets_Completos'].sum()}")
            c3.metric("Rutas Despachadas (Hoy)", f"{df_hoy[df_hoy['Estado'].str.contains('DESPACHAD', na=False, case=False)]['Ruta'].nunique()} / {df_hoy['Ruta'].nunique()}")
        
        st.write("---")
        st.markdown("### 📈 Histórico y Proyección Diaria")
        
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
        primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
        
        # Períodos base fijos
        periodos = [
            {"nombre": "Mes Pasado", "filtro": lambda d: primer_dia_mes_pasado <= d <= ultimo_dia_mes_pasado},
            {"nombre": "Acum. Este Mes", "filtro": lambda d: primer_dia_mes_actual <= d <= hoy},
            {"nombre": "Ayer", "filtro": lambda d: d == (hoy - timedelta(days=1))},
            {"nombre": "Hoy", "filtro": lambda d: d == hoy},
        ]
        
        # 🔥 GENERACIÓN DINÁMICA DE FECHAS FUTURAS DIA POR DIA
        df_valid_dates = df_res.dropna(subset=['dt_real']).copy()
        fechas_futuras = sorted([d for d in df_valid_dates['dt_real'].dt.date.unique() if d > hoy])
        
        for f in fechas_futuras:
            # Formato claro: "24/10 (Sáb)"
            dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            nom_f = f"{f.strftime('%d/%m')} ({dias_semana[f.weekday()]})"
            # Creamos la regla de filtrado binding
            periodos.append({
                "nombre": nom_f, 
                "filtro": lambda d, target_date=f: d == target_date
            })
        
        datos_tabla = []
        for p in periodos:
            df_p = df_res[df_res['dt_real'].apply(lambda x: p["filtro"](x.date()) if pd.notna(x) else False)]
            
            rut_p = df_p['Ruta'].nunique()
            rut_o = df_p[df_p['Estado'].str.contains('DESPACHAD', na=False, case=False)]['Ruta'].nunique()
            
            caj_p = df_p['Cajas_Picking'].sum()
            caj_o = df_p[df_p['Estado'].isin(ESTADOS_CAJAS)]['Cajas_Picking'].sum()
            
            pal_p = df_p['Pallets_Completos'].sum()
            pal_o = df_p[df_p['Estado'].isin(ESTADOS_PALLETS)]['Pallets_Completos'].sum()
            
            t_prom = df_p[df_p['Estado'].str.contains('DESPACHAD', na=False, case=False)]['Tiempo_Carga_Hs'].mean() if 'Tiempo_Carga_Hs' in df_p.columns else np.nan
            
            datos_tabla.append({
                "Período": p["nombre"], 
                "🚚 Rutas": f"{rut_o} / {rut_p}", 
                "% Rutas": int(rut_o/rut_p*100) if rut_p>0 else 0, 
                "📦 Cajas": f"{int(caj_o)} / {int(caj_p)}", 
                "% Cajas": int(caj_o/caj_p*100) if caj_p>0 else 0, 
                "🧱 Pallets": f"{int(pal_o)} / {int(pal_p)}", 
                "% Pallets": int(pal_o/pal_p*100) if pal_p>0 else 0, 
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
        # ⚙️ FLUJO CONTINUO (EVALÚA COLA PENDIENTE DE HOY)
        # =====================================================================
        st.write("---")
        st.markdown("### ⚙️ Flujo Continuo: Capacidad Instalada Real vs. Cola Pendiente (HOY)")
        
        hr_exact = now_dt.hour + (now_dt.minute / 60)
        sh = [{"n":"T.Mañana","eff":8.0},{"n":"T.Tarde","eff":8.0},{"n":"T.Noche","eff":8.0}]
        
        if 6 <= hr_exact < 14:
            sh[0]['n'] += " (ACTUAL)"
            sh[0]['eff'] = max(0, 14 - hr_exact)
        elif 14 <= hr_exact < 22:
            sh[1]['n'] += " (ACTUAL)"
            sh[1]['eff'] = max(0, 22 - hr_exact)
            sh[0]['eff'] = 0 
        else:
            sh[2]['n'] += " (ACTUAL)"
            sh[2]['eff'] = max(0, (30 - hr_exact) if hr_exact >= 22 else (6 - hr_exact))
            sh[0]['eff'] = 0
            sh[1]['eff'] = 0

        # Filtro estricto: solo evalúa la cola pendiente con cita para HOY o anterior
        df_p = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        if 'dt_real' in df_p.columns:
            df_p = df_p[df_p['dt_real'].dt.date <= hoy]
        df_p = df_p[df_p['Cajas_Picking'] > 0]
        
        avg_cj_hr = 124 
        t_cj = 0
        if not df_p.empty and 'Average_Picking' in df_p.columns:
            df_p['PHr_ruta'] = np.where(df_p['Average_Picking'] > 0, (df_p['Average_Picking'] / 10.0) * 124.0, 124.0)
            df_p['HEst_ruta'] = df_p['Cajas_Picking'] / df_p['PHr_ruta']
            
            t_ph = df_p['HEst_ruta'].sum()
            t_cj = df_p['Cajas_Picking'].sum()
            
            if t_ph > 0: avg_cj_hr = t_cj / t_ph
            
        c1, c2, c3 = st.columns(3)
        d1 = c1.number_input(f"🧑‍🤝‍🧑 {sh[0]['n']} ({sh[0]['eff']:.1f} hs disp)", min_value=0, value=5 if sh[0]['eff']>0 else 0)
        d2 = c2.number_input(f"🧑‍🤝‍🧑 {sh[1]['n']} ({sh[1]['eff']:.1f} hs disp)", min_value=0, value=5 if sh[1]['eff']>0 else 0)
        d3 = c3.number_input(f"🧑‍🤝‍🧑 {sh[2]['n']} ({sh[2]['eff']:.1f} hs disp)", min_value=0, value=5 if sh[2]['eff']>0 else 0)
        
        rem = t_cj
        yv, ch, ct, uh, ut = [], [], [], [], []
        
        for s, dot in zip(sh, [d1, d2, d3]):
            hs_disp = s['eff']
            yv.append(f"<b>{s['n']}</b><br>{hs_disp:.1f} hs x {dot} pers")
            
            cap_cajas = hs_disp * dot * avg_cj_hr
            ch.append(cap_cajas)
            ct.append(f"Cap: {int(cap_cajas)} cjs")
            
            if rem >= cap_cajas:
                uh.append(cap_cajas)
                ut.append(f"Uso 100% ➡️")
                rem -= cap_cajas
            elif rem > 0:
                uh.append(rem)
                ut.append(f"Uso {int(rem)} cjs 🏁")
                rem = 0
            else:
                uh.append(0)
                ut.append("Libre")
                
        fig = go.Figure()
        fig.add_trace(go.Bar(y=yv[::-1], x=ch[::-1], name='Capacidad Total Instalada (Cajas)', orientation='h', marker=dict(color='#2e7d32'), text=ct[::-1], textposition='inside'))
        fig.add_trace(go.Bar(y=yv[::-1], x=uh[::-1], name='Uso por Cola Pendiente (Hoy)', orientation='h', marker=dict(color='#f57f17'), text=ut[::-1], textposition='inside'))
        fig.update_layout(
            barmode='group', bargap=0.15, height=350, plot_bgcolor='rgba(0,0,0,0)', 
            font=dict(color='white'), legend=dict(orientation="h", yanchor="bottom"),
            xaxis=dict(title='Cantidad de Cajas (Capacidad vs Demanda de Hoy)', gridcolor='rgba(255,255,255,0.1)')
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Recolectando datos...")