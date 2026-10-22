import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
import urllib.parse
from datetime import datetime, timedelta, timezone

# =====================================================================
# 1. CONFIGURACIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL REAL DE GOOGLE APPS SCRIPT:
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbx1iNrn2O-EhHt5uT8mxSGuAar9gJ6haGik5MnI3rFff_giusAohqw8m_X6PR130iae/exec"

st.set_page_config(layout="wide", page_title="Tracking de Pedidos", page_icon="📦")

ESTADOS_CAJAS_LISTAS = ["PICKING COMPLETO", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA"]
ESTADOS_PALLETS_LISTOS = ["PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA"]

# =====================================================================
# 2. MOTOR DE DATOS (LECTURA PURA Y CACHÉ DE 30 SEGS)
# =====================================================================
@st.cache_data(ttl=30, show_spinner=False)
def obtener_datos_maestros():
    df_full = pd.DataFrame()
    try:
        resp = requests.get(URL_GOOGLE_SCRIPT, timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            df_full = pd.DataFrame(resp.json())
            
            # Limpieza y Normalización
            for col in ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']:
                if col in df_full.columns:
                    df_full[col] = pd.to_numeric(df_full[col], errors='coerce').fillna(0).astype(int)
            for col in ['Ruta', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte']:
                if col in df_full.columns:
                    df_full[col] = df_full[col].astype(str).str.strip().str.upper()
            
            if 'Fecha_Cita' in df_full.columns:
                def parse_date(x):
                    try:
                        if pd.isna(x) or str(x).strip() in ["", "SIN FECHA", "NAN"]: return pd.NaT
                        s = str(x).strip()
                        if "/" in s and len(s) <= 12: return pd.to_datetime(f"{s}/{datetime.now().year}", format="%d/%m %H:%M/%Y", errors='coerce')
                        return pd.to_datetime(s, utc=True).tz_convert(None) - pd.Timedelta(hours=3)
                    except: return pd.NaT
                
                df_full['dt_real'] = df_full['Fecha_Cita'].apply(parse_date)
                df_full['Fecha_Cita_str'] = df_full['dt_real'].dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
    except:
        pass
    return df_full

@st.cache_data(ttl=30, show_spinner=False)
def obtener_tiempos_despachos():
    try:
        meses = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}
        mes_actual = meses[datetime.now(timezone(timedelta(hours=-3))).month]
        sheet_id = "1V8lkm7RmxJMqzb4pQMHrxQX5bSW2K8tF_bO7A8cJpHM"
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(f'Despachos {mes_actual}')}"
        
        df_t = pd.read_csv(url_csv, dtype=str) 
        if len(df_t.columns) >= 13:
            df_t = df_t.iloc[:, [0, 11, 12]].copy()
            df_t.columns = ['Ruta', 'Ingreso_Str', 'Egreso_Str']
            df_t = df_t.dropna(subset=['Ruta'])
            df_t['Ruta'] = df_t['Ruta'].astype(str).str.strip().str.replace('.0', '', regex=False).str.upper()
            return df_t
    except: pass
    return pd.DataFrame()

# =====================================================================
# 3. INTERFAZ Y CSS
# =====================================================================
st.markdown("""
    <style>
    .kpi-box { background-color: #1E1E24; color: #FFFFFF; padding: 12px 5px; border-radius: 6px; border-top: 4px solid #E55B3C; text-align: center; box-shadow: 1px 1px 3px rgba(0,0,0,0.5);}
    .kpi-title { font-size: 11px; text-transform: uppercase; opacity: 0.8;}
    .kpi-value { font-size: 20px; font-weight: bold; margin-top: 4px;}
    </style>
""", unsafe_allow_html=True)

st.title("📦 Tablero de Seguimiento y Preparado de Pedidos")

# =====================================================================
# 4. PROCESAMIENTO PRINCIPAL
# =====================================================================
df_full = obtener_datos_maestros()
if not df_full.empty and 'Ruta' in df_full.columns:
    df_tiempos = obtener_tiempos_despachos()
    if not df_tiempos.empty:
        df_full = pd.merge(df_full, df_tiempos, on='Ruta', how='left')
        
        def safe_time(val, base_dt):
            try:
                dt = pd.to_datetime(str(val), errors='coerce')
                if pd.notna(dt) and dt.year < 2000 and pd.notna(base_dt): return dt.replace(year=base_dt.year, month=base_dt.month, day=base_dt.day)
                return dt
            except: return pd.NaT

        df_full['dt_Ingreso'] = df_full.apply(lambda r: safe_time(r.get('Ingreso_Str'), r.get('dt_real')), axis=1)
        df_full['dt_Egreso'] = df_full.apply(lambda r: safe_time(r.get('Egreso_Str'), r.get('dt_real')), axis=1)
        df_full['Inicio_Carga'] = df_full[['dt_real', 'dt_Ingreso']].max(axis=1)
        df_full['Tiempo_Carga_Hs'] = (df_full['dt_Egreso'] - df_full['Inicio_Carga']).dt.total_seconds() / 3600
        df_full['Tiempo_Carga_Hs'] = df_full['Tiempo_Carga_Hs'].apply(lambda x: x if x > 0 else np.nan)

tab_operarios, tab_monitor, tab_resumen = st.tabs(["📲 Vista Operativa", "📱 Monitor de Cargas", "📊 Resumen Ejecutivo"])

# ---------------------------------------------------------------------
# PESTAÑA 1: VISTA OPERATIVA (SOLO LECTURA)
# ---------------------------------------------------------------------
with tab_operarios:
    st.subheader("Tablero de Estados de Armado (Lectura Automática)")
    
    if df_full.empty or 'Estado' not in df_full.columns:
        st.info("Aguardando datos de la base...")
    else:
        # ⚠️ FILTRO ANTI-ERRORES: Excluye cualquier cosa que contenga "DESPACHAD" (O/A)
        df_activa = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        
        if df_activa.empty:
            st.success("🎉 Todas las órdenes han sido despachadas.")
        else:
            # Cálculos KPI Rápidos
            tot_rutas = df_activa['Ruta'].nunique()
            tot_ordenes = len(df_activa)
            
            cajas_listas = df_activa[df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()
            cajas_ptes = df_activa['Cajas_Picking'].sum() - cajas_listas
            
            pallets_listos = df_activa[df_activa['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()
            pallets_ptes = df_activa['Pallets_Completos'].sum() - pallets_listos
            
            cajas_pista = df_activa[df_activa['Estado'].isin(['LANZADA', 'EN PREPARACIÓN'])]['Cajas_Picking'].sum()
            top_salida = len(df_activa[df_activa['Estado'] == 'TOP SALIDA'])
            
            # Cálculo de Horas Pick (Solo pendientes)
            df_ptes = df_activa[~df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)].copy()
            df_ptes['Prod_Hr'] = np.where(df_ptes['Average_Picking'] > 0, (df_ptes['Average_Picking'] / 10.0) * 124.0, 124.0)
            horas_dec = np.where(df_ptes['Cajas_Picking'] > 0, df_ptes['Cajas_Picking'] / df_ptes['Prod_Hr'], 0).sum()
            h_str = f"{int(horas_dec * 60) // 60:02d}:{int(horas_dec * 60) % 60:02d}"
            
            k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
            k1.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Rutas</div><div class='kpi-value'>{tot_rutas}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-box'><div class='kpi-title'>Órdenes Activas</div><div class='kpi-value'>{tot_ordenes}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-box'><div class='kpi-title'>Pallets Ptes</div><div class='kpi-value'>{pallets_ptes}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Ptes</div><div class='kpi-value'>{cajas_ptes}</div></div>", unsafe_allow_html=True)
            k5.markdown(f"<div class='kpi-box'><div class='kpi-title'>Horas Pick</div><div class='kpi-value'>{h_str}</div></div>", unsafe_allow_html=True)
            k6.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Pista</div><div class='kpi-value'>{cajas_pista}</div></div>", unsafe_allow_html=True)
            k7.markdown(f"<div class='kpi-box'><div class='kpi-title'>Top Salida</div><div class='kpi-value'>{top_salida}</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            
            # Visualización Limpia
            cols_to_sort = [c for c in ['dt_real', 'Ruta', 'Orden_Carga'] if c in df_activa.columns]
            if cols_to_sort: df_activa = df_activa.sort_values(by=cols_to_sort)
            if 'Fecha_Cita_str' in df_activa.columns: df_activa['Fecha_Cita'] = df_activa['Fecha_Cita_str']
            
            columnas_ver = ['Fecha_Cita', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking']
            df_mostrar = df_activa[[c for c in columnas_ver if c in df_activa.columns]].copy()
            
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------
# PESTAÑA 2: MONITOR DE CARGAS
# ---------------------------------------------------------------------
with tab_monitor:
    st.subheader("🎯 Monitor por Horario de Cita")
    if not df_full.empty and 'Estado' in df_full.columns:
        df_mon = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        if df_mon.empty: 
            st.success("Todo despachado.")
        elif 'dt_real' in df_mon.columns:
            ahora = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
            df_mon = df_mon.dropna(subset=['dt_real'])
            df_mon['Fecha_Cita'] = df_mon['dt_real'].dt.strftime('%d/%m %H:%M')
            
            for fecha_str, grupo in df_mon.groupby('Fecha_Cita'):
                fecha_dt = grupo['dt_real'].iloc[0]
                min_dif = (ahora - fecha_dt).total_seconds() / 60
                
                est_txt = "🟢 Faltan " + str(int(abs(min_dif))) + " min. para la cita" if min_dif < 0 else ("🚨 Cita cumplida (Atraso)" if min_dif > 180 else "🟡 En ventana de 3hs")
                st.markdown(f"**Cita: {fecha_str}** | {est_txt} | Órdenes: {len(grupo)}")

# ---------------------------------------------------------------------
# PESTAÑA 3: RESUMEN EJECUTIVO (KPIs Analíticos + Gráfico Continuo)
# ---------------------------------------------------------------------
with tab_resumen:
    st.markdown("<h2 style='text-align: left;'>📊 Resumen Ejecutivo y Tiempos</h2>", unsafe_allow_html=True)
    
    if not df_full.empty and 'dt_real' in df_full.columns and 'Estado' in df_full.columns:
        hoy = datetime.now(timezone(timedelta(hours=-3))).date()
        df_hoy = df_full[df_full['dt_real'].dt.date == hoy].copy()
        
        c1, c2, c3 = st.columns(3)
        if not df_hoy.empty:
            cajas_tot = df_hoy['Cajas_Picking'].sum()
            cajas_ok = df_hoy[df_hoy['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()
            rutas_tot = df_hoy['Ruta'].nunique()
            rutas_ok = df_hoy[df_hoy['Estado'].str.contains('DESPACHAD', na=False, case=False)]['Ruta'].nunique()
            
            c1.metric("Cajas Pickeadas (Hoy)", f"{cajas_ok} / {cajas_tot}")
            c3.metric("Rutas Despachadas (Hoy)", f"{rutas_ok} / {rutas_tot}")
            
        st.write("---")
        
        # Tabla Histórica Simple
        periodos = [
            {"nombre": "Ayer", "filtro": lambda d: d == (hoy - timedelta(days=1))},
            {"nombre": "Hoy", "filtro": lambda d: d == hoy},
        ]
        
        datos_tabla = []
        for p in periodos:
            df_p = df_full[df_full['dt_real'].apply(lambda x: p["filtro"](x.date()) if pd.notna(x) else False)]
            rut_p = df_p['Ruta'].nunique()
            rut_o = df_p[df_p['Estado'].str.contains('DESPACHAD', na=False, case=False)]['Ruta'].nunique()
            caj_p = df_p['Cajas_Picking'].sum()
            caj_o = df_p[df_p['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()
            t_prom = df_p['Tiempo_Carga_Hs'].mean() if 'Tiempo_Carga_Hs' in df_p.columns else np.nan
            
            datos_tabla.append({
                "Período": p["nombre"], "Rutas Plan": rut_p, "Rutas Ok": rut_o, 
                "Cajas Plan": int(caj_p), "Cajas Ok": int(caj_o), 
                "Demora Carga Prom.": f"{t_prom:.1f} hs" if pd.notna(t_prom) else "-"
            })
            
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True)
    else: 
        st.info("Recolectando datos históricos...")
