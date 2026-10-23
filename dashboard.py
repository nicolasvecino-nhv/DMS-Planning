import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

# ⚠️ PEGA AQUÍ TU URL NUEVA:
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbzgzGx9-wP9tNjgeoJYuBpM7Fd--e1Q_J695qHNTI7JUik_SU_NZVdZWmh5iQ8c-7hv/exec"

st.set_page_config(layout="wide", page_title="WMS Dashboard", page_icon="📦")

ESTADOS_CAJAS = ["PICKING COMPLETO", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"]
ESTADOS_PALLETS = ["PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"]
ESTADOS_LISTA = ["PENDIENTE", "CARENCIA", "LANZADA", "EN PREPARACIÓN", "PICKING COMPLETO", "PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA"]
ESTADO_PESO = {e: i+1 for i, e in enumerate(ESTADOS_LISTA)}

@st.cache_data(ttl=15, show_spinner=False)
def obtener_datos():
    try:
        resp = requests.get(URL_GOOGLE_SCRIPT, timeout=15)
        if resp.status_code == 200 and len(resp.json()) > 0:
            df = pd.DataFrame(resp.json())
            for col in ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']:
                if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            for col in ['Ruta', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte']:
                if col in df.columns: df[col] = df[col].astype(str).str.strip().str.upper()
            return df
    except: pass
    return pd.DataFrame()

def unificar_fechas(fecha_val):
    try:
        if pd.isna(fecha_val) or str(fecha_val).strip() in ["", "SIN FECHA", "NAN", "NaT"]: return pd.NaT
        s = str(fecha_val).strip()
        if "/" in s and len(s) <= 12: return pd.to_datetime(f"{s}/{datetime.now().year}", format="%d/%m %H:%M/%Y", errors='coerce')
        return pd.to_datetime(s, utc=True).tz_convert(None) - pd.Timedelta(hours=3)
    except: return pd.NaT

def safe_time(val, base_dt):
    if pd.isna(val) or str(val).strip() == "": return pd.NaT
    try:
        s = str(val).strip()
        if len(s) <= 5 and ":" in s and pd.notna(base_dt): return pd.to_datetime(f"{base_dt.strftime('%Y-%m-%d')} {s}", errors='coerce')
        dt = pd.to_datetime(s, errors='coerce')
        if pd.notna(dt) and dt.year < 2000 and pd.notna(base_dt): return dt.replace(year=base_dt.year, month=base_dt.month, day=base_dt.day)
        return dt
    except: return pd.NaT

if 'perfil' not in st.session_state: st.session_state.perfil = None
def logout(): st.session_state.perfil = None; obtener_datos.clear()

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

# PROCESAMIENTO GENERAL
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

# TAB 1: OPERATIVA
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

# TAB 2: MONITOR Y FALLAS
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

# TAB 3: SUPERVISOR (CARGA)
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

# TAB 4: RESUMEN
with tab_res:
    st.markdown("## 📊 Flujo Continuo: Consumo de Cola Pendiente")
    if not df_full.empty and 'dt_real' in df_full.columns:
        n = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
        hr = n.hour
        sh = [{"n":"T.Mañana","eff":6.0},{"n":"T.Tarde","eff":6.0},{"n":"T.Noche","eff":6.0}]
        if 6<=hr<14: sh[0]['n']+=" (ACTUAL)"; sh[0]['eff']=max(0,(14-hr)*0.75)
        elif 14<=hr<22: sh[1]['n']+=" (ACTUAL)"; sh[1]['eff']=max(0,(22-hr)*0.75)
        else: sh[2]['n']+=" (ACTUAL)"; sh[2]['eff']=max(0,((30 if hr>=22 else 6)-hr)*0.75)
        
        c1, c2, c3 = st.columns(3)
        d1 = c1.number_input(f"🧑‍🤝‍🧑 {sh[0]['n']}", min_value=1, value=5)
        d2 = c2.number_input(f"🧑‍🤝‍🧑 {sh[1]['n']}", min_value=1, value=5)
        d3 = c3.number_input(f"🧑‍🤝‍🧑 {sh[2]['n']}", min_value=1, value=5)
        
        df_p = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        t_ph, avg_cj = 0, 0
        if not df_p.empty and 'Average_Picking' in df_p.columns:
            df_p['PHr'] = np.where(df_p['Average_Picking']>0, (df_p['Average_Picking']/10)*124, 124)
            df_p['HEst'] = np.where(df_p['Cajas_Picking']>0, df_p['Cajas_Picking']/df_p['PHr'], 0)
            t_ph, t_cj = df_p['HEst'].sum(), df_p['Cajas_Picking'].sum()
            if t_ph>0: avg_cj = t_cj/t_ph
            
        rem = t_ph; yv, ch, ct, uh, ut = [], [], [], [], []
        for s, dot in zip(sh, [d1,d2,d3]):
            yv.append(f"<b>{s['n']}</b><br>Disp: {s['eff']:.1f}hs")
            cap = s['eff']*dot
            ch.append(s['eff']); ct.append(f"{s['eff']:.1f}hs disp ({int(cap*avg_cj)} cjs)")
            if rem>=cap: uh.append(s['eff']); ut.append(f"{s['eff']:.1f}hs uso ➡️"); rem-=cap
            elif rem>0: uh.append(rem/dot); ut.append(f"{(rem/dot):.1f}hs uso 🏁"); rem=0
            else: uh.append(0); ut.append("Libre")
            
        fig = go.Figure()
        fig.add_trace(go.Bar(y=yv[::-1], x=ch[::-1], name='Capacidad (Disp.)', orientation='h', marker=dict(color='#2e7d32'), text=ct[::-1], textposition='inside'))
        fig.add_trace(go.Bar(y=yv[::-1], x=uh[::-1], name='Cola (Uso)', orientation='h', marker=dict(color='#f57f17'), text=ut[::-1], textposition='inside'))
        fig.update_layout(barmode='group', bargap=0.15, height=350, plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), legend=dict(orientation="h", yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### 📈 KPIs Tiempos")
        hy = n.date()
        tab = []
        for p in [{"n":"Ayer", "f":lambda d: d==(hy-timedelta(days=1))}, {"n":"Hoy", "f":lambda d: d==hy}]:
            d = df_full[df_full['dt_real'].apply(lambda x: p["f"](x.date()) if pd.notna(x) else False)]
            es = d['Estadia_Hs'].mean() if 'Estadia_Hs' in d.columns else np.nan
            ts = d['Desvio_Total_Hs'].mean() if 'Desvio_Total_Hs' in d.columns else np.nan
            tab.append({"Período":p["n"], "Rutas Total":d['Ruta'].nunique(), "Estadía Prom.":f"{es:.1f} hs" if pd.notna(es) else "-", "Carga Operativa Prom.":f"{ts:.1f} hs" if pd.notna(ts) and ts>0 else "-"})
        st.dataframe(pd.DataFrame(tab), use_container_width=True, hide_index=True)