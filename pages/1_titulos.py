import streamlit as st
import io
import uuid
import hashlib
from googleapiclient.http import MediaIoBaseUpload
from conexion import conectar_google 

st.set_page_config(page_title="Títulos de Propiedad", page_icon="📄", layout="wide")

# --- CONSTANTES ---
CARPETA_DRIVE_ID = "1ps5FF0fkJ7utOpvbqPWfAs9IAOH6aoNU" 
SHEET_ID = "1_ncJgZrP5Jvks3nE-tBVrMmuSA7pbZiEmH9ExvHD_Uk"

st.title("📄 Gestión de Títulos de Propiedad")

# Conectamos a Google usando el archivo centralizado
drive_service, sheets_client = conectar_google()

# Solo mostramos la app si la conexión a Google fue exitosa
if drive_service and sheets_client:
    
    tab_carga, tab_procesar, tab_auditar = st.tabs(["1️⃣ Carga", "2️⃣ Procesar (IA)", "3️⃣ Auditar"])
    
    with tab_carga:
        st.header("Carga Masiva de Documentos")
        uploaded_files = st.file_uploader("Selecciona los archivos PDF (puedes elegir varios)", type=["pdf"], accept_multiple_files=True)
        
        if uploaded_files:
            st.info(f"Has seleccionado {len(uploaded_files)} archivo(s).")
            if st.button("Guardar en Google Drive"):
                with st.spinner("Subiendo a Drive..."):
                    
                    for uploaded_file in uploaded_files:
                        # Leemos los bytes del archivo
                        file_bytes = uploaded_file.getvalue()
                        
                        # 1. Generar ID único corto (primeros 8 caracteres)
                        id_unico = str(uuid.uuid4())[:8]
                        nuevo_nombre = f"{id_unico}_{uploaded_file.name}"
                        
                        # 2. Generar huella digital (Hash SHA-256)
                        huella_digital = hashlib.sha256(file_bytes).hexdigest()
                        
                        # Preparamos los metadatos para Google Drive
                        file_metadata = {
                            'name': nuevo_nombre,
                            'parents': [CARPETA_DRIVE_ID],
                            'appProperties': {
                                'hash_sha256': huella_digital # Guardamos la huella oculta
                            }
                        }
                        
                        # Subida en fragmentos para evitar el Broken Pipe
                        media = MediaIoBaseUpload(
                            io.BytesIO(file_bytes), 
                            mimetype='application/pdf',
                            chunksize=1024*1024,
                            resumable=True
                        )
                        
                        try:
                            drive_service.files().create(
                                body=file_metadata, 
                                media_body=media, 
                                fields='id',
                                supportsAllDrives=True 
                            ).execute()
                            
                            st.success(f"✅ Archivo guardado como '{nuevo_nombre}'")
                        except Exception as e:
                            st.error(f"Error al subir el archivo '{uploaded_file.name}': {e}")
    
    with tab_procesar:
        st.header("Procesamiento Inteligente")
        st.write("En la próxima fase conectaremos la Inteligencia Artificial aquí para que lea los PDFs de Drive.")
            
    with tab_auditar:
        st.header("Auditoría Humana")
        st.write("Revisa los datos extraídos y guárdalos en la base de datos (Google Sheets).")
        
        with st.form("formulario_auditoria"):
            patente = st.text_input("Dominio (Patente)", value="AB123CD")
            marca = st.text_input("Marca / Modelo", value="Ford Ranger")
            chasis = st.text_input("Nro. de Chasis", value="8AW339...")
            motor = st.text_input("Nro. de Motor", value="MTR991...")
            
            guardar = st.form_submit_button("✅ Aprobar y Guardar en Google Sheets")
            
            if guardar:
                with st.spinner("Guardando en la base de datos..."):
                    try:
                        hoja = sheets_client.open_by_key(SHEET_ID).sheet1
                        hoja.append_row([patente, marca, chasis, motor])
                        st.success(f"✅ El vehículo {patente} fue registrado en Google Sheets.")
                    except Exception as e:
                        st.error(f"Error al guardar en Sheets. Asegúrate de haberle dado acceso al robot. Error: {e}")
else:
    st.error("No se pudo conectar a Google. Revisa las credenciales en Streamlit.")
