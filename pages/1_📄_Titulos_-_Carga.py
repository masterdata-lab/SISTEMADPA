import streamlit as st
import io
import uuid
import hashlib
from PIL import Image
from googleapiclient.http import MediaIoBaseUpload
from conexion import conectar_google, obtener_o_crear_carpeta

# 1. DEFINIMOS EL MÓDULO ACTUAL (Al cambiar esto, cambia toda la lógica de Drive)
TIPO_DOC = "Títulos"
icono = "📄"

st.set_page_config(page_title=f"Carga de {TIPO_DOC}", page_icon=icono, layout="wide")

# --- VARIABLES DE ESTADO GLOBALES ---
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "carga_exitosa" not in st.session_state:
    st.session_state.carga_exitosa = False
if "cantidad_subida" not in st.session_state:
    st.session_state.cantidad_subida = 0

CARPETA_RAIZ_ID = "1ps5FF0fkJ7utOpvbqPWfAs9IAOH6aoNU" 

drive_service, sheets_client = conectar_google()

if drive_service:
    # --- CONFIGURACIÓN DINÁMICA DE CARPETAS ---
    # Usamos el nombre del documento en la clave de sesión para que no choquen si abres "Cédulas"
    clave_config = f"carpetas_configuradas_{TIPO_DOC}"
    
    if not st.session_state.get(clave_config, False):
        with st.spinner(f"Configurando carpetas para {TIPO_DOC} en Drive..."):
            # Crea la carpeta principal (Ej: "Títulos")
            id_tipo = obtener_o_crear_carpeta(drive_service, TIPO_DOC, CARPETA_RAIZ_ID)
            
            # Crea las 3 subcarpetas adentro de la carpeta principal
            st.session_state[f"id_pendientes_{TIPO_DOC}"] = obtener_o_crear_carpeta(drive_service, "1_Pendientes", id_tipo)
            st.session_state[f"id_auditar_{TIPO_DOC}"] = obtener_o_crear_carpeta(drive_service, "2_Para_Auditar", id_tipo)
            st.session_state[f"id_aprobados_{TIPO_DOC}"] = obtener_o_crear_carpeta(drive_service, "3_Aprobados", id_tipo)
            
            st.session_state[clave_config] = True

    st.title(f"{icono} Carga Masiva de {TIPO_DOC}")
    
    if st.session_state.carga_exitosa:
        mensaje = f"¡{st.session_state.cantidad_subida} archivos guardados en la bandeja '1_Pendientes' de {TIPO_DOC}!"
        st.success(f"✅ {mensaje}")
        st.toast(f"✅ {mensaje}", icon="🎉")
        st.session_state.carga_exitosa = False 
    
    uploaded_files = st.file_uploader(
        f"Selecciona los {TIPO_DOC} (PDF, JPG, PNG, BMP)", 
        type=["pdf", "jpg", "jpeg", "png", "bmp"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )
    
    contenedor_info = st.empty()
    contenedor_progreso = st.empty()
    contenedor_texto_estado = st.empty()
    
    if uploaded_files:
        contenedor_info.info(f"Has seleccionado {len(uploaded_files)} archivo(s). Destino: Bandeja de Pendientes ({TIPO_DOC}).")
        
        if st.button("Guardar en Google Drive"):
            total_archivos = len(uploaded_files)
            barra = contenedor_progreso.progress(0)
            id_destino = st.session_state[f"id_pendientes_{TIPO_DOC}"]
            
            for i, uploaded_file in enumerate(uploaded_files):
                contenedor_texto_estado.write(f"🔄 Procesando {i+1} de {total_archivos}: `{uploaded_file.name}`...")
                
                extension = uploaded_file.name.split('.')[-1].lower()
                
                if extension in ['jpg', 'jpeg', 'png', 'bmp']:
                    imagen = Image.open(uploaded_file)
                    if imagen.mode in ("RGBA", "P"):
                        imagen = imagen.convert("RGB")
                    pdf_bytes_io = io.BytesIO()
                    imagen.save(pdf_bytes_io, format="PDF")
                    file_bytes = pdf_bytes_io.getvalue()
                    nombre_base = uploaded_file.name.rsplit('.', 1)[0]
                    nombre_final = f"{nombre_base}.pdf"
                else:
                    file_bytes = uploaded_file.getvalue()
                    nombre_final = uploaded_file.name
                
                id_unico = str(uuid.uuid4())[:8]
                nuevo_nombre = f"{id_unico}_{nombre_final}"
                huella_digital = hashlib.sha256(file_bytes).hexdigest()
                
                file_metadata = {
                    'name': nuevo_nombre,
                    'parents': [id_destino], 
                    'appProperties': {'hash_sha256': huella_digital}
                }
                
                media = MediaIoBaseUpload(
                    io.BytesIO(file_bytes), mimetype='application/pdf', chunksize=1024*1024, resumable=True
                )
                
                try:
                    drive_service.files().create(
                        body=file_metadata, media_body=media, fields='id', supportsAllDrives=True 
                    ).execute()
                except Exception as e:
                    st.error(f"Error al subir '{uploaded_file.name}': {e}")
                
                barra.progress((i + 1) / total_archivos)
            
            st.session_state.carga_exitosa = True
            st.session_state.cantidad_subida = total_archivos
            st.session_state.uploader_key += 1
            st.rerun()
else:
    st.error("No se pudo conectar a Google Drive.")
