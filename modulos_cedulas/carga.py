import streamlit as st
import io
import uuid
import hashlib
from PIL import Image
from googleapiclient.http import MediaIoBaseUpload

def modulo_carga(drive_service, TIPO_DOC):
    st.header(f"Carga Masiva de {TIPO_DOC}")
    
    # Variables de estado específicas para este tipo de documento
    key_uploader = f"uploader_key_{TIPO_DOC}"
    key_exitosa = f"carga_exitosa_{TIPO_DOC}"
    key_cantidad = f"cantidad_subida_{TIPO_DOC}"
    
    if key_uploader not in st.session_state:
        st.session_state[key_uploader] = 0
    if key_exitosa not in st.session_state:
        st.session_state[key_exitosa] = False
    if key_cantidad not in st.session_state:
        st.session_state[key_cantidad] = 0

    if st.session_state[key_exitosa]:
        mensaje = f"¡{st.session_state[key_cantidad]} archivos guardados en la bandeja '1_Pendientes' de {TIPO_DOC}!"
        st.success(f"✅ {mensaje}")
        st.toast(f"✅ {mensaje}", icon="🎉")
        st.session_state[key_exitosa] = False 
    
    uploaded_files = st.file_uploader(
        f"Selecciona los archivos (PDF, JPG, PNG, BMP)", 
        type=["pdf", "jpg", "jpeg", "png", "bmp"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state[key_uploader]}"
    )
    
    contenedor_info = st.empty()
    contenedor_progreso = st.empty()
    contenedor_texto_estado = st.empty()
    
    if uploaded_files:
        contenedor_info.info(f"Seleccionaste {len(uploaded_files)} archivo(s). Destino: 1_Pendientes ({TIPO_DOC}).")
        
        if st.button("Guardar en Google Drive", key=f"btn_guardar_{TIPO_DOC}"):
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
            
            st.session_state[key_exitosa] = True
            st.session_state[key_cantidad] = total_archivos
            st.session_state[key_uploader] += 1
            st.rerun()
