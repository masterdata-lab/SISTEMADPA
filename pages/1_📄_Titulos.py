import streamlit as st
from conexion import conectar_google, obtener_o_crear_carpeta

# Importamos nuestros módulos separados
from modulos.carga import modulo_carga
from modulos.procesar import modulo_procesar
from modulos.auditar import modulo_auditar

# --- CONFIGURACIÓN DEL MÓDULO ---
TIPO_DOC = "Títulos"
icono = "📄"
CARPETA_RAIZ_ID = "1ps5FF0fkJ7utOpvbqPWfAs9IAOH6aoNU" 
SHEET_ID = "1_ncJgZrP5Jvks3nE-tBVrMmuSA7pbZiEmH9ExvHD_Uk"

st.set_page_config(page_title=f"Gestión de {TIPO_DOC}", page_icon=icono, layout="wide")

st.title(f"{icono} Gestión Integral de {TIPO_DOC}")

drive_service, sheets_client = conectar_google()

if drive_service and sheets_client:
    
    # --- CONFIGURACIÓN DINÁMICA DE CARPETAS ---
    clave_config = f"carpetas_configuradas_{TIPO_DOC}"
    
    if not st.session_state.get(clave_config, False):
        with st.spinner(f"Verificando árbol de carpetas para {TIPO_DOC} en Drive..."):
            id_tipo = obtener_o_crear_carpeta(drive_service, TIPO_DOC, CARPETA_RAIZ_ID)
            st.session_state[f"id_pendientes_{TIPO_DOC}"] = obtener_o_crear_carpeta(drive_service, "1_Pendientes", id_tipo)
            st.session_state[f"id_auditar_{TIPO_DOC}"] = obtener_o_crear_carpeta(drive_service, "2_Para_Auditar", id_tipo)
            st.session_state[f"id_aprobados_{TIPO_DOC}"] = obtener_o_crear_carpeta(drive_service, "3_Aprobados", id_tipo)
            st.session_state[clave_config] = True

    # --- CREACIÓN DE LAS 3 PESTAÑAS ---
    tab_carga, tab_procesar, tab_auditar = st.tabs(["1️⃣ Carga", "2️⃣ Procesar (IA)", "3️⃣ Auditar"])
    
    with tab_carga:
        modulo_carga(drive_service, TIPO_DOC)
        
    with tab_procesar:
        modulo_procesar(drive_service, TIPO_DOC)
        
    with tab_auditar:
        modulo_auditar(drive_service, sheets_client, TIPO_DOC, SHEET_ID)

else:
    st.error("No se pudo conectar a los servicios de Google. Revisa tus credenciales.")
