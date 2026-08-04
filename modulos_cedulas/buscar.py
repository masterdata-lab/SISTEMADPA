import streamlit as st
import io
import urllib.parse
from googleapiclient.http import MediaIoBaseDownload

# --- FUNCIONES AUXILIARES ---

def obtener_hoja_y_datos_cedulas(sheets_client, SHEET_ID):
    try:
        hoja = sheets_client.open_by_key(SHEET_ID).worksheet("Cedulas")
        registros = hoja.get_all_records()
        return hoja, registros
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None, []

def mostrar_visor_pdf(file_id, height=500):
    url_preview = f"https://drive.google.com/file/d/{file_id}/preview"
    st.markdown(
        f'<iframe src="{url_preview}" width="100%" height="{height}px" style="border: none; border-radius: 8px;"></iframe>', 
        unsafe_allow_html=True
    )

def descargar_pdf_bytes(drive_service, file_id):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        return fh.getvalue()
    except Exception as e:
        st.error(f"Error al descargar archivo desde Drive: {e}")
        return None

def hacer_enlace_publico(drive_service, file_id):
    try:
        permiso = {'type': 'anyone', 'role': 'reader'}
        drive_service.permissions().create(fileId=file_id, body=permiso).execute()
        return True
    except Exception as e:
        st.error(f"Error al cambiar permisos: {e}")
        return False

def enviar_documento_por_email(drive_service, file_id, email_destino, mensaje):
    try:
        permiso = {'type': 'user', 'role': 'reader', 'emailAddress': email_destino}
        drive_service.permissions().create(
            fileId=file_id,
            body=permiso,
            emailMessage=mensaje,
            sendNotificationEmail=True
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error al enviar el correo: {e}")
        return False

# --- MÓDULO PRINCIPAL ---

def modulo_buscar(drive_service, sheets_client, SHEET_ID):
    st.header("🔍 Buscar y Visualizar Cédulas")
    st.divider()

    with st.spinner("Cargando base de datos..."):
        hoja, registros_bd = obtener_hoja_y_datos_cedulas(sheets_client, SHEET_ID)
        
    if hoja is None:
        return

    lista_patentes = sorted(list(set([
        str(reg.get('PATENTE', '')).strip().upper() 
        for reg in registros_bd 
        if reg.get('PATENTE') and str(reg.get('PATENTE')).strip().upper() != "SIN PATENTE"
    ])))

    col_busqueda, col_vacia = st.columns([1, 2])
    with col_busqueda:
        patente_input = st.selectbox(
            "Seleccione o escriba la Patente a buscar:", 
            options=lista_patentes,
            index=None,
            placeholder="Ej. AG871VL"
        )

    if patente_input:
        registros_encontrados = [reg for reg in registros_bd if str(reg.get('PATENTE', '')).strip().upper() == patente_input]
        
        st.success(f"✅ Se encontraron **{len(registros_encontrados)}** registro(s) para la patente: **{patente_input}**")
        
        for idx, registro in enumerate(registros_encontrados):
            tipo_cara = registro.get('TIPO_CARA', 'DESCONOCIDO')
            
            with st.expander(f"📄 Documento {idx + 1} - Cara: {tipo_cara}", expanded=True):
                id_drive = registro.get('ID_DRIVE')
                
                col_visor, col_datos = st.columns([4, 3])
                
                with col_visor:
                    if id_drive:
                        mostrar_visor_pdf(id_drive)
                    else:
                        st.error("El registro no tiene un documento asociado para visualizar.")

                with col_datos:
                    with st.container(border=True):
                        st.markdown("**Datos del Registro**")
                        st.text_input("Patente", value=registro.get('PATENTE', ''), disabled=True, key=f"pat_{idx}")
                        st.text_input("Tipo de Cara", value=tipo_cara, disabled=True, key=f"cara_{idx}")
                        st.text_input("Estado", value=registro.get('ESTADO', ''), disabled=True, key=f"est_{idx}")
                        st.text_input("Fecha de Auditoría", value=registro.get('FECHA_AUDITORIA', ''), disabled=True, key=f"fec_{idx}")
                        
                    if id_drive:
                        st.divider()
                        pdf_bytes = descargar_pdf_bytes(drive_service, id_drive)
                        if pdf_bytes:
                            st.download_button(
                                label=f"📥 Descargar {tipo_cara}",
                                data=pdf_bytes,
                                file_name=f"{patente_input} - CEDULA {tipo_cara}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"btn_dl_{idx}"
                            )
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("**Opciones de Compartir**")
                        c_link, c_mail = st.columns(2)
                        
                        with c_link:
                            if st.button("🌐 Enlace Público", use_container_width=True, key=f"btn_link_{idx}"):
                                with st.spinner("Desbloqueando..."):
                                    if hacer_enlace_publico(drive_service, id_drive):
                                        st.success("¡Activado!")
                                        st.code(f"https://drive.google.com/file/d/{id_drive}/view", language="text")
                                        
                        with c_mail:
                            with st.form(f"form_mail_ced_{idx}"):
                                correo = st.text_input("Destinatario:", key=f"email_input_{idx}")
                                msg = st.text_area("Mensaje:", value=f"Cédula {tipo_cara} - Patente {patente_input}", key=f"msg_input_{idx}")
                                if st.form_submit_button("📤 Enviar", use_container_width=True, type="primary"):
                                    if not correo:
                                        st.warning("Ingresa un correo.")
                                    else:
                                        with st.spinner("Enviando..."):
                                            if enviar_documento_por_email(drive_service, id_drive, correo, msg):
                                                st.success("¡Enviado!")
