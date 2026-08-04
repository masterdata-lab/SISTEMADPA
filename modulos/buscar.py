import streamlit as st
import io
import urllib.parse
from googleapiclient.http import MediaIoBaseDownload

# --- FUNCIONES AUXILIARES ---

def obtener_hoja_y_datos(sheets_client, SHEET_ID):
    """Devuelve el objeto de la hoja (para poder editar) y los registros."""
    try:
        hoja = sheets_client.open_by_key(SHEET_ID).sheet1
        registros = hoja.get_all_records()
        return hoja, registros
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None, []

def mostrar_visor_pdf(file_id, height=750): 
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
    """Otorga permisos de lectura a cualquier persona que tenga el enlace."""
    try:
        permiso = {'type': 'anyone', 'role': 'reader'}
        drive_service.permissions().create(fileId=file_id, body=permiso).execute()
        return True
    except Exception as e:
        st.error(f"Error al cambiar permisos: {e}")
        return False

def enviar_documento_por_email(drive_service, file_id, email_destino, mensaje):
    """Comparte el archivo por Drive y envía un correo de notificación nativo."""
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
    st.header("🔍 Buscar y Editar Documento")
    st.divider()

    if "modo_edicion" not in st.session_state:
        st.session_state.modo_edicion = False

    with st.spinner("Cargando base de datos..."):
        hoja, registros_bd = obtener_hoja_y_datos(sheets_client, SHEET_ID)
        
    if hoja is None:
        return

    lista_patentes = sorted(list(set([str(reg.get('PATENTE', '')).strip().upper() for reg in registros_bd if reg.get('PATENTE')])))

    col_busqueda, col_vacia = st.columns([1, 2])
    with col_busqueda:
        patente_input = st.selectbox(
            "Seleccione o escriba la Patente a buscar:", 
            options=lista_patentes,
            index=None,
            placeholder="Ej. AG871VL",
            on_change=lambda: st.session_state.update(modo_edicion=False)
        )

    if patente_input:
        fila_indice = next((i for i, reg in enumerate(registros_bd) if str(reg.get('PATENTE', '')).strip().upper() == patente_input), None)
        
        if fila_indice is not None:
            registro_encontrado = registros_bd[fila_indice]
            fila_real_sheets = fila_indice + 2 
            
            st.success(f"✅ Documento cargado: **{patente_input}**")
            id_drive = registro_encontrado.get('ID_DRIVE')
            
            col_visor, col_datos = st.columns([4, 3])
            
            with col_visor:
                st.subheader("Vista Previa")
                if id_drive:
                    mostrar_visor_pdf(id_drive)
                else:
                    st.error("El registro no tiene un documento asociado para visualizar.")

            with col_datos:
                c_tit, c_btn = st.columns([2, 1])
                c_tit.subheader("Datos del Vehículo")
                
                if not st.session_state.modo_edicion:
                    if c_btn.button("✏️ Editar", use_container_width=True):
                        st.session_state.modo_edicion = True
                        st.rerun()

                if not st.session_state.modo_edicion:
                    with st.container(border=True):
                        st.markdown("**Identificación**")
                        st.text_input("Patente", value=registro_encontrado.get('PATENTE', ''), disabled=True)
                        st.text_input("Fecha Inscripción", value=registro_encontrado.get('FECHA_INSCRIPCION_INICIAL', ''), disabled=True)
                        
                        st.markdown("**Vehículo**")
                        st.text_input("Marca", value=registro_encontrado.get('MARCA', ''), disabled=True)
                        st.text_input("Modelo", value=registro_encontrado.get('MODELO', ''), disabled=True)
                        st.text_input("Tipo", value=registro_encontrado.get('TIPO', ''), disabled=True)
                        st.text_input("Chasis", value=registro_encontrado.get('NRO_CHASIS', ''), disabled=True)
                        st.text_input("Motor", value=registro_encontrado.get('NRO_MOTOR', ''), disabled=True)
                        
                        st.markdown("**Radicación y Titular**")
                        st.text_input("Titular", value=registro_encontrado.get('TITULAR', ''), disabled=True)
                        st.text_input("CUIT", value=registro_encontrado.get('CUIT', ''), disabled=True)
                        st.text_input("Lugar Radicación", value=registro_encontrado.get('LUGAR_RADICACION', ''), disabled=True)
                        st.text_input("Provincia", value=registro_encontrado.get('PROVINCIA_RADICACION', ''), disabled=True)
                
                else:
                    st.info("Modifique los campos necesarios y guarde los cambios.")
                    with st.form("form_edicion_datos"):
                        st.markdown("**Identificación**")
                        nuevo_patente = st.text_input("Patente", value=registro_encontrado.get('PATENTE', ''))
                        nuevo_fecha = st.text_input("Fecha Inscripción", value=registro_encontrado.get('FECHA_INSCRIPCION_INICIAL', ''))
                        
                        st.markdown("**Vehículo**")
                        nuevo_marca = st.text_input("Marca", value=registro_encontrado.get('MARCA', ''))
                        nuevo_modelo = st.text_input("Modelo", value=registro_encontrado.get('MODELO', ''))
                        nuevo_tipo = st.text_input("Tipo", value=registro_encontrado.get('TIPO', ''))
                        nuevo_chasis = st.text_input("Chasis", value=registro_encontrado.get('NRO_CHASIS', ''))
                        nuevo_motor = st.text_input("Motor", value=registro_encontrado.get('NRO_MOTOR', ''))
                        
                        st.markdown("**Radicación y Titular**")
                        nuevo_titular = st.text_input("Titular", value=registro_encontrado.get('TITULAR', ''))
                        nuevo_cuit = st.text_input("CUIT", value=registro_encontrado.get('CUIT', ''))
                        nuevo_radicacion = st.text_input("Lugar Radicación", value=registro_encontrado.get('LUGAR_RADICACION', ''))
                        nuevo_provincia = st.text_input("Provincia", value=registro_encontrado.get('PROVINCIA_RADICACION', ''))
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        col_save, col_cancel = st.columns(2)
                        btn_guardar = col_save.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
                        btn_cancelar = col_cancel.form_submit_button("❌ Cancelar", use_container_width=True)
                        
                        if btn_cancelar:
                            st.session_state.modo_edicion = False
                            st.rerun()
                            
                        if btn_guardar:
                            with st.spinner("Actualizando base de datos..."):
                                fila_original = hoja.row_values(fila_real_sheets)
                                while len(fila_original) < 15:
                                    fila_original.append("")
                                
                                fila_original[2] = str(nuevo_patente).upper().strip()
                                fila_original[3] = str(nuevo_marca).upper().strip()
                                fila_original[4] = str(nuevo_modelo).upper().strip()
                                fila_original[5] = str(nuevo_tipo).upper().strip()
                                fila_original[6] = str(nuevo_chasis).upper().strip()
                                fila_original[7] = str(nuevo_motor).upper().strip()
                                fila_original[8] = str(nuevo_titular).upper().strip()
                                fila_original[9] = str(nuevo_cuit).upper().strip()
                                fila_original[10] = str(nuevo_radicacion).upper().strip()
                                fila_original[11] = str(nuevo_provincia).upper().strip()
                                fila_original[12] = str(nuevo_fecha).upper().strip()
                                
                                hoja.update(values=[fila_original], range_name=f"A{fila_real_sheets}:O{fila_real_sheets}")
                                
                            st.session_state.modo_edicion = False
                            st.toast("✅ Datos actualizados correctamente")
                            st.rerun()
                
                # --- ACCIONES RÁPIDAS MODIFICADAS ---
                if not st.session_state.modo_edicion and id_drive:
                    st.divider()
                    st.subheader("Opciones de Compartir")
                    
                    pdf_bytes = descargar_pdf_bytes(drive_service, id_drive)
                    if pdf_bytes:
                        st.download_button(
                            label="📥 Descargar PDF Localmente",
                            data=pdf_bytes,
                            file_name=f"{patente_input} - TITULO.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_link, col_mail = st.columns(2)
                    with col_link:
                        st.markdown("**🔗 Generar Enlace Libre**")
                        st.info("Cualquier persona con el link podrá verlo.")
                        if st.button("🌐 Desbloquear Enlace", use_container_width=True):
                            with st.spinner("Modificando permisos..."):
                                if hacer_enlace_publico(drive_service, id_drive):
                                    st.success("¡Enlace activado!")
                                    st.code(f"https://drive.google.com/file/d/{id_drive}/view", language="text")

                    with col_mail:
                        st.markdown("**📧 Enviar por Correo**")
                        with st.form("form_mail_titulo"):
                            correo = st.text_input("Destinatario:")
                            msg = st.text_area("Mensaje:", value=f"Se adjunta el Título del vehículo {patente_input}.")
                            if st.form_submit_button("📤 Enviar", use_container_width=True, type="primary"):
                                if not correo:
                                    st.warning("Ingresa un correo.")
                                else:
                                    with st.spinner("Enviando..."):
                                        if enviar_documento_por_email(drive_service, id_drive, correo, msg):
                                            st.success("¡Enviado!")
        else:
            st.warning(f"Ocurrió un error al cargar los datos de: **{patente_input}**")
