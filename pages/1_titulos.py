import streamlit as st
import io
import uuid
import hashlib
from googleapiclient.http import MediaIoBaseUpload
from conexion import conectar_google 

st.set_page_config(page_title="Títulos de Propiedad", page_icon="📄", layout="wide")

# --- INICIALIZAR VARIABLES DE ESTADO ---
# Esto nos permite reiniciar el uploader y mostrar la notificación al finalizar
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "mostrar_toast" not in st.session_state:
    st.session_state.mostrar_toast = False
if "cantidad_subida" not in st.session_state:
    st.session_state.cantidad_subida = 0

# Disparar el mensaje "pushup" (toast) si acabamos de terminar una carga
if st.session_state.mostrar_toast:
    st.toast(f"✅ ¡{st.session_state.cantidad_subida} archivos guardados con éxito!", icon="🎉")
    # Reseteamos las variables para que no se muestre de nuevo al cambiar de pestaña
    st.session_state.mostrar_toast = False
    st.session_state.cantidad_subida = 0

# --- CONSTANTES ---
CARPETA_DRIVE_ID = "1ps5FF0fkJ7utOpvbqPWfAs9IAOH6aoNU" 
SHEET_ID = "1_ncJgZrP5Jvks3nE-tBVrMmuSA7pbZiEmH9ExvHD_Uk"

st.title("📄 Gestión de Títulos de Propiedad")

# Conectamos a Google usando el archivo centralizado
drive_service, sheets_client = conectar_google()

if drive_service and sheets_client:
    
    tab_carga, tab_procesar, tab_auditar = st.tabs(["1️⃣ Carga", "2️⃣ Procesar (IA)", "3️⃣ Auditar"])
    
    with tab_carga:
        st.header("Carga Masiva de Documentos")
        
        # El uploader ahora usa una 'key' dinámica. Al cambiar la key, se limpia la caja automáticamente.
        uploaded_files = st.file_uploader(
            "Selecciona los archivos PDF (puedes elegir varios)", 
            type=["pdf"], 
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}"
        )
        
        # Creamos contenedores vacíos para inyectar elementos visuales que luego podamos borrar
        contenedor_info = st.empty()
        contenedor_progreso = st.empty()
        contenedor_texto_estado = st.empty()
        
        if uploaded_files:
            # Mostramos la cantidad seleccionada
            contenedor_info.info(f"Has seleccionado {len(uploaded_files)} archivo(s).")
            
            if st.button("Guardar en Google Drive"):
                total_archivos = len(uploaded_files)
                
                # Inicializamos la barra de progreso en 0
                barra = contenedor_progreso.progress(0)
                
                for i, uploaded_file in enumerate(uploaded_files):
                    # Actualizamos el texto en pantalla (un solo renglón que va cambiando)
                    contenedor_texto_estado.write(f"🔄 Procesando {i+1} de {total_archivos}: `{uploaded_file.name}`...")
                    
                    file_bytes = uploaded_file.getvalue()
                    
                    # Generar ID y Huella Digital
                    id_unico = str(uuid.uuid4())[:8]
                    nuevo_nombre = f"{id_unico}_{uploaded_file.name}"
                    huella_digital = hashlib.sha256(file_bytes).hexdigest()
                    
                    file_metadata = {
                        'name': nuevo_nombre,
                        'parents': [CARPETA_DRIVE_ID],
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
                    
                    # Avanzamos la barra de progreso
                    barra.progress((i + 1) / total_archivos)
                
                # --- AL FINALIZAR EL BUCLE ---
                # Borramos la info de la pantalla
                contenedor_info.empty()
                contenedor_progreso.empty()
                contenedor_texto_estado.empty()
                
                # Preparamos las variables para el "toast" y cambiamos la key del uploader
                st.session_state.mostrar_toast = True
                st.session_state.cantidad_subida = total_archivos
                st.session_state.uploader_key += 1
                
                # Forzamos una recarga silenciosa de la página para aplicar el borrado
                st.rerun()
                
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
                        st.error(f"Error al guardar en Sheets: {e}")
else:
    st.error("No se pudo conectar a Google. Revisa las credenciales en Streamlit.")
