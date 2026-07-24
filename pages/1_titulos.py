import streamlit as st
import io
import uuid
import hashlib
from googleapiclient.http import MediaIoBaseUpload
from conexion import conectar_google 

# ... [código de configuración y conexión igual que antes] ...

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
                        
                        media = MediaIoBaseUpload(
                            io.BytesIO(file_bytes), 
                            mimetype='application/pdf',
                            chunksize=1024*1024,
                            resumable=True
                        )
                        
                        drive_service.files().create(
                            body=file_metadata, 
                            media_body=media, 
                            fields='id',
                            supportsAllDrives=True 
                        ).execute()
                        
                        st.success(f"✅ Archivo guardado como '{nuevo_nombre}'")
