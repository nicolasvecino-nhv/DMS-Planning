import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURACIÓN VISUAL DE LA WEB EN PYTHON ---
st.set_page_config(layout="wide", page_title="Tracking de Pedidos", page_icon="📦")

# Diseño CSS para imitar tu plantilla original (colores oscuros y botones naranjas)
st.markdown("""
    <style>
    .kpi-box {
        background-color: #333333; color: white; padding: 20px; 
        border-radius: 8px; border-top: 5px solid #E55B3C; text-align: center;
    }
    .kpi-title { font-size: 14px; color: #aaaaaa; }
    .kpi-value { font-size: 24px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN SILENCIOSA A FIREBASE (ALMACENAMIENTO) ---
@st.cache_resource
def conectar_bd():
    if not firebase_admin._apps:
        # En la web pública, las credenciales se manejan como "Secretos" (te explico abajo)
        cred = credentials.Certificate(st.secrets["firebase_key"])
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = conectar_bd()

# --- INTERFAZ DE USUARIO (PYTHON) ---
st.title("📦 Seguimiento y Preparado de Pedidos")

# Pestañas para separar la vista del Supervisor (que sube Excel) y el Operario (que arma)
tab_operarios, tab_supervisor = st.tabs(["📲 Vista de Preparado (Operarios)", "⚙️ Carga de Reportes (Supervisor)"])

with tab_supervisor:
    st.subheader("Subir Planificación (Python procesa, Firebase guarda)")
    col1, col2 = st.columns(2)
    with col1: file_plan = st.file_uploader("Reporte Planificación", type=["xlsx"])
    with col2: file_maestro = st.file_uploader("Maestro Materiales", type=["xlsx"])
    
    if st.button("Procesar y Guardar en Base de Datos"):
        if file_plan and file_maestro:
            # Python hace la lógica
            df_plan = pd.read_excel(file_plan)
            df_maestro = pd.read_excel(file_maestro)
            df_completo = pd.merge(df_plan, df_maestro[['Codigo', 'LPK']], on='Codigo', how='left')
            df_completo['LPK'] = df_completo['LPK'].fillna(1)
            df_completo['Pallets_Completos'] = (df_completo['Cantidad_Cajas'] // df_completo['LPK']).astype(int)
            df_completo['Cajas_Picking'] = (df_completo['Cantidad_Cajas'] % df_completo['LPK']).astype(int)
            df_completo['Cajas_Armadas'] = 0
            df_completo['Estado'] = 'Pendiente'
            
            # Python envía a Firebase solo para almacenar
            for _, row in df_completo.iterrows():
                doc_id = f"{row['Orden_Entrega']}_{row['Codigo']}"
                db.collection('pedidos').document(doc_id).set(row.to_dict())
            st.success("Reporte procesado y almacenado correctamente.")

with tab_operarios:
    st.subheader("Tablero de Picking y Armado")
    
    # Python pide los datos a Firebase para dibujar la web
    pedidos_ref = db.collection('pedidos').stream()
    datos = [doc.to_dict() | {"ID": doc.id} for doc in pedidos_ref]
    
    if datos:
        df_mostrar = pd.DataFrame(datos)
        
        # Diseño de KPIs (Cajas armadas vs Pendientes)
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Órdenes</div><div class='kpi-value'>{len(df_mostrar['Orden_Entrega'].unique())}</div></div>", unsafe_allow_html=True)
        with kpi2: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas a Picking</div><div class='kpi-value'>{df_mostrar['Cajas_Picking'].sum()}</div></div>", unsafe_allow_html=True)
        with kpi3: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Armadas</div><div class='kpi-value'>{df_mostrar['Cajas_Armadas'].sum()}</div></div>", unsafe_allow_html=True)
        
        st.write("---")
        
        # Interacción del usuario: Editar datos
        st.write("Doble clic en **Cajas_Armadas** o **Estado** para actualizar.")
        df_editado = st.data_editor(
            df_mostrar[['Orden_Entrega', 'Codigo', 'Pallets_Completos', 'Cajas_Picking', 'Cajas_Armadas', 'Estado', 'ID']],
            disabled=['Orden_Entrega', 'Codigo', 'Pallets_Completos', 'Cajas_Picking', 'ID'],
            use_container_width=True, hide_index=True
        )
        
        if st.button("Confirmar Avance"):
            # Lógica para detectar qué editó el usuario y guardarlo en Firebase
            cambios = df_editado.compare(df_mostrar[['Orden_Entrega', 'Codigo', 'Pallets_Completos', 'Cajas_Picking', 'Cajas_Armadas', 'Estado', 'ID']])
            if not cambios.empty:
                for index in cambios.index:
                    doc_id = df_editado.loc[index, 'ID']
                    db.collection('pedidos').document(doc_id).update({
                        'Cajas_Armadas': int(df_editado.loc[index, 'Cajas_Armadas']),
                        'Estado': df_editado.loc[index, 'Estado']
                    })
                st.success("Avance registrado. Refrescando datos...")
                st.rerun() # Python recarga la web automáticamente
    else:
        st.info("No hay pedidos activos. El supervisor debe subir el reporte.")