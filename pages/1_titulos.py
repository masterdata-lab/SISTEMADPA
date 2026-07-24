import streamlit as st
import io
import uuid
import hashlib
from PIL import Image
from googleapiclient.http import MediaIoBaseUpload
# IMPORTANTE: Ahora importamos la nueva función de carpetas
from conexion import conectar_google, obtener_o_crear_carpeta

st.set_page_config(page_title="Títulos de Propiedad", page_icon="📄", layout="wide")

# --- INICIALIZAR VARIABLES DE ESTADO ---
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "carga_exitosa" not in st.session_state:
    st.session_state.carga_exitosa = False
if "cantidad_subida" not in st.session_state:
    st.session_state.cantidad_subida = 0
if "carpetas_configuradas" not in st.session_state:
    st.session_state.carpetas_configuradas = False

# --- CONSTANTES ---
CARPETA_RAIZ_ID = "1ps5FF0fkJ7utOpvbqPWfAs9IAOH6aoNU" 
SHEET_ID = "1_ncJgZrP5Jvks3nE-tBVrMmuSA7pbZiEmH9ExvHD_Uk"

st.title("📄 Gestión de Títulos de Propiedad")

# Conectamos a Google
drive_service, sheets_client = conectar_google()

if drive_service and sheets_client:
    
    # --- CONFIGURACIÓN AUTOMÁTICA DE CARPETAS ---
    # Esto asegura que el árbol de carpetas exista sin que tengas que crearlo a mano
    if not st.session_state.carpetas_configuradas:
        with st.spinner("Verificando estructura de carpetas en Google Drive..."):
            id_titulos = obtener_o_crear_carpeta(drive_service, "Títulos", CARPETA_RAIZ_ID)
            
            # Guardamos los IDs de las 3 bandejas en sesión para usarlos en cualquier pestaña
            st.session_state.id_pendientes = obtener_o_crear_carpeta(drive_service, "1_Pendientes", id_titulos)
            st.session_state.id_auditar = obtener_o_crear_carpeta(drive_service, "2_Para_Auditar", id_titulos)
            st.session_state.id_aprobados = obtener_o_crear_carpeta(drive_service, "3_Aprobados", id_titulos)
            
            st.session_state.carpetas_configuradas = True
    
    tab_carga, tab_procesar, tab_auditar = st.tabs(["1️⃣ Carga", "2️⃣ Procesar (IA)", "3️⃣ Auditar"])
    
    with tab_carga:
        st.header("Carga Masiva de Documentos")
        
        if st.session_state.carga_exitosa:
            mensaje = f"¡{st.session_state.cantidad_subida} archivos guardados en la bandeja '1_Pendientes'!"
            st.success(f"✅ {mensaje}")
            st.toast(f"✅ {mensaje}", icon="🎉")
            st.session_state.carga_exitosa = False 
        
        uploaded_files = st.file_uploader(
            "Selecciona los archivos (PDF, JPG, PNG, BMP)", 
            type=["pdf", "jpg", "jpeg", "png", "bmp"], 
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}"
        )
        
        contenedor_info = st.empty()
        contenedor_progreso = st.empty()
        contenedor_texto_estado = st.empty()
        
        if uploaded_files:
            contenedor_info.info(f"Has seleccionado {len(uploaded_files)} archivo(s). Destino: Bandeja de Pendientes.")
            
            if st.button("Guardar en Google Drive"):
                total_archivos = len(uploaded_files)
                barra = contenedor_progreso.progress(0)
                
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
                        'parents': [st.session_state.id_pendientes],  # <--- SE GUARDAN DIRECTAMENTE EN 1_PENDIENTES
                        'appProperties': {
                            'hash_sha256': huella_digital 
                        }
                    }
                    
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
                    except Exception as e:
                        st.error(f"Error al subir '{uploaded_file.name}': {e}")
                    
                    barra.progress((i + 1) / total_archivos)
                
                st.session_state.carga_exitosa = True
                st.session_state.cantidad_subida = total_archivos
                st.session_state.uploader_key += 1
                
                st.rerun()
                
    with tab_procesar:
        st.header("Procesamiento Inteligente")
        st.write("Aquí la IA leerá los archivos de la carpeta '1_Pendientes' y los pasará a '2_Para_Auditar'.")
            
    with tab_auditar:
        st.header("Auditoría Humana")
        st.write("Revisa los datos extraídos. Al aprobar, los archivos se moverán a '3_Aprobados' y se guardarán en Sheets.")
        
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
                        st.error(f"Error al guardar en Sheets: {e}")
else:
    st.error("No se pudo conectar a Google. Revisa las credenciales en Streamlit.")
