import streamlit as st
import pandas as pd
import base64
import io
from datetime import datetime
from googleapiclient.http import MediaIoBaseDownload

# --- FUNCIONES AUXILIARES ---

def obtener_datos_sheets(sheets_client, SHEET_ID):
    """Obtiene todos los registros de la hoja para buscar duplicados."""
    try:
        hoja = sheets_client.open_by_key(SHEET_ID).sheet1
        registros = hoja.get_all_records()
        return hoja, registros
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None, []

def mostrar_visor_pdf(drive_service, file_id, height=600):
    """Descarga el PDF en memoria y lo muestra en un iFrame nativo."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        
        base64_pdf = base64.b64encode(fh.getvalue()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="{height}" type="application/pdf"></iframe>'
        st.components.v1.html(pdf_display, height=height)
    except Exception as e:
        st.error(f"Error al cargar PDF: {e}")

def mover_archivo_aprobados(drive_service, file_id, id_origen, id_destino):
    drive_service.files().update(
        fileId=file_id,
        addParents=id_destino,
        removeParents=id_origen,
        fields='id, parents'
    ).execute(num_retries=3)

def enviar_a_papelera(drive_service, file_id):
    drive_service.files().update(fileId=file_id, body={'trashed': True}).execute(num_retries=3)

def preparar_fila_excel(id_drive, nombre, datos, estado="Aprobado"):
    """Ordena los datos exactos según las columnas solicitadas para Sheets."""
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return [
        id_drive,
        nombre,
        datos.get('patente', '').upper(),
        datos.get('marca', '').upper(),
        datos.get('modelo', '').upper(),
        datos.get('tipo', '').upper(),
        datos.get('nro_chasis', '').upper(),
        datos.get('nro_motor', '').upper(),
        datos.get('titular', '').upper(),
        datos.get('cuit', ''),
        datos.get('lugar_radicacion', '').upper(),
        datos.get('provincia_radicacion', '').upper(),
        datos.get('fecha_inscripcion_inicial', ''),
        estado,
        fecha_hoy
    ]

# --- MÓDULO PRINCIPAL ---

def modulo_auditar(drive_service, sheets_client, TIPO_DOC, SHEET_ID):
    st.header(f"Auditoría de {TIPO_DOC}")
    
    id_origen = st.session_state.get(f"id_auditar_{TIPO_DOC}")
    id_destino = st.session_state.get(f"id_aprobados_{TIPO_DOC}")
    
    if not id_origen or not id_destino:
        st.error("Error con las carpetas de Drive. Por favor, recarga la página.")
        return

    hoja, registros_bd = obtener_datos_sheets(sheets_client, SHEET_ID)
    if hoja is None:
        return

    # Diccionario rápido para buscar patentes existentes y saber en qué fila están
    patentes_existentes = {str(reg.get('PATENTE', '')).upper(): (i + 2, reg) for i, reg in enumerate(registros_bd) if reg.get('PATENTE')}

    with st.spinner("Escaneando documentos pendientes y cruzando datos..."):
        query = f"'{id_origen}' in parents and trashed=false"
        resultados = drive_service.files().list(q=query, fields="files(id, name, appProperties)").execute(num_retries=3)
        archivos_pendientes = resultados.get('files', [])

    if not archivos_pendientes:
        st.success("🎉 No hay documentos pendientes de auditar.")
        return

    # Clasificamos entre Nuevos y Duplicados
    lista_nuevos = []
    lista_duplicados = []
    
    for arch in archivos_pendientes:
        props = arch.get('appProperties', {})
        patente = props.get('patente', '').upper()
        
        # Estructura para la tabla
        fila_ui = {
            "Seleccionar": False,
            "ID_Drive": arch['id'],
            "Archivo": arch['name'],
            "Patente": patente,
            "Titular": props.get('titular', ''),
            "Chasis": props.get('nro_chasis', ''),
            "Data_Raw": props # Guardamos los datos completos ocultos para usarlos luego
        }
        
        if patente in patentes_existentes:
            lista_duplicados.append(fila_ui)
        else:
            lista_nuevos.append(fila_ui)

    # --- INTERFAZ CON PESTAÑAS ---
    tab_nuevos, tab_duplicados = st.tabs([f"🟢 Nuevos ({len(lista_nuevos)})", f"🟠 Duplicados ({len(lista_duplicados)})"])

    # ==========================================
    # PESTAÑA 1: NUEVOS (Flujo Rápido)
    # ==========================================
    with tab_nuevos:
        if not lista_nuevos:
            st.info("No hay documentos nuevos.")
        else:
            df_nuevos = pd.DataFrame(lista_nuevos)
            
            col_lista, col_visor, col_datos = st.columns([1.5, 2, 1.5])
            
            with col_lista:
                st.subheader("Lista de Documentos")
                # Data Editor permite tildar casillas
                df_editado = st.data_editor(
                    df_nuevos,
                    column_config={"Seleccionar": st.column_config.CheckboxColumn(required=True), "Data_Raw": None}, # Ocultamos la raw data
                    disabled=["Archivo", "Patente", "Titular", "Chasis", "ID_Drive"],
                    hide_index=True,
                    key="editor_nuevos",
                    use_container_width=True
                )
                
                seleccionados = df_editado[df_editado["Seleccionar"] == True]

            # Si seleccionó EXACTAMENTE UNO: Mostramos Visor y Formulario
            if len(seleccionados) == 1:
                doc_actual = seleccionados.iloc[0]
                datos_ia = doc_actual["Data_Raw"]
                
                with col_visor:
                    st.subheader(f"📄 {doc_actual['Archivo']}")
                    mostrar_visor_pdf(drive_service, doc_actual["ID_Drive"])
                
                with col_datos:
                    st.subheader("Datos para Auditar")
                    with st.form("form_auditoria_individual"):
                        pat = st.text_input("Patente", value=datos_ia.get('patente', ''))
                        mar = st.text_input("Marca", value=datos_ia.get('marca', ''))
                        mod = st.text_input("Modelo", value=datos_ia.get('modelo', ''))
                        cha = st.text_input("Chasis", value=datos_ia.get('nro_chasis', ''))
                        mot = st.text_input("Motor", value=datos_ia.get('nro_motor', ''))
                        tit = st.text_input("Titular", value=datos_ia.get('titular', ''))
                        
                        btn_aprobar = st.form_submit_button("✅ Aprobar Documento", type="primary", use_container_width=True)
                        btn_rechazar = st.form_submit_button("🗑️ Descartar (Papelera)", use_container_width=True)
                        
                        if btn_aprobar:
                            datos_corregidos = datos_ia.copy()
                            datos_corregidos.update({'patente': pat, 'marca': mar, 'modelo': mod, 'nro_chasis': cha, 'nro_motor': mot, 'titular': tit})
                            
                            fila = preparar_fila_excel(doc_actual["ID_Drive"], doc_actual["Archivo"], datos_corregidos)
                            hoja.append_row(fila)
                            mover_archivo_aprobados(drive_service, doc_actual["ID_Drive"], id_origen, id_destino)
                            st.success("Aprobado exitosamente.")
                            st.rerun()
                            
                        if btn_rechazar:
                            enviar_a_papelera(drive_service, doc_actual["ID_Drive"])
                            st.warning("Documento enviado a la papelera.")
                            st.rerun()

            # Si seleccionó VARIOS: Mostramos botón masivo
            elif len(seleccionados) > 1:
                with col_visor:
                    st.info(f"Seleccionaste {len(seleccionados)} documentos para aprobación masiva.")
                    if st.button("🚀 Aprobar Lote Seleccionado", type="primary", use_container_width=True):
                        barra = st.progress(0)
                        for i, (_, doc) in enumerate(seleccionados.iterrows()):
                            fila = preparar_fila_excel(doc["ID_Drive"], doc["Archivo"], doc["Data_Raw"])
                            hoja.append_row(fila)
                            mover_archivo_aprobados(drive_service, doc["ID_Drive"], id_origen, id_destino)
                            barra.progress((i + 1) / len(seleccionados))
                        st.success("Lote aprobado exitosamente.")
                        st.rerun()
            else:
                with col_visor:
                    st.write("👈 Selecciona un documento de la lista para auditarlo.")

    # ==========================================
    # PESTAÑA 2: DUPLICADOS (Resolución de Conflictos)
    # ==========================================
    with tab_duplicados:
        if not lista_duplicados:
            st.info("No se detectaron conflictos de patentes.")
        else:
            df_duplicados = pd.DataFrame(lista_duplicados)
            st.write("Estos documentos tienen patentes que ya existen en la base de datos.")
            
            df_edit_dup = st.data_editor(
                df_duplicados,
                column_config={"Seleccionar": st.column_config.CheckboxColumn(required=True), "Data_Raw": None},
                disabled=["Archivo", "Patente", "Titular", "Chasis", "ID_Drive"],
                hide_index=True,
                key="editor_duplicados"
            )
            
            seleccionados_dup = df_edit_dup[df_edit_dup["Seleccionar"] == True]
            
            if len(seleccionados_dup) > 1:
                st.warning("⚠️ Por favor, selecciona solo un duplicado a la vez para resolver el conflicto.")
            elif len(seleccionados_dup) == 1:
                doc_nuevo = seleccionados_dup.iloc[0]
                patente_conflicto = doc_nuevo["Patente"]
                
                # Rescatamos datos viejos del diccionario armado al principio
                fila_excel_vieja, datos_excel_viejos = patentes_existentes[patente_conflicto]
                id_drive_viejo = datos_excel_viejos.get('ID_DRIVE')
                
                st.markdown("---")
                st.subheader(f"⚖️ Resolución de Conflicto: Dominio {patente_conflicto}")
                
                # LAS 4 COLUMNAS DE COMPARACIÓN
                c_pdf_viejo, c_data_vieja, c_data_nueva, c_pdf_nuevo = st.columns(4)
                
                with c_pdf_viejo:
                    st.caption("📄 PDF Aprobado Anteriormente")
                    if id_drive_viejo:
                        mostrar_visor_pdf(drive_service, id_drive_viejo, height=450)
                    else:
                        st.error("No se encontró el ID del archivo anterior.")
                
                with c_data_vieja:
                    st.caption("🗄️ Datos en Google Sheets")
                    st.info(f"""
                    **Titular:** {datos_excel_viejos.get('TITULAR', '')}  
                    **Chasis:** {datos_excel_viejos.get('NRO_CHASIS', '')}  
                    **Motor:** {datos_excel_viejos.get('NRO_MOTOR', '')}  
                    **Fecha Aud.:** {datos_excel_viejos.get('FECHA_AUDITORIA', '')}
                    """)
                    
                with c_data_nueva:
                    st.caption("🆕 Datos Documento Nuevo")
                    datos_ia = doc_nuevo["Data_Raw"]
                    st.success(f"""
                    **Titular:** {datos_ia.get('titular', '')}  
                    **Chasis:** {datos_ia.get('nro_chasis', '')}  
                    **Motor:** {datos_ia.get('nro_motor', '')}  
                    **Archivo:** {doc_nuevo['Archivo']}
                    """)
                    
                with c_pdf_nuevo:
                    st.caption("📄 PDF Nuevo (Pendiente)")
                    mostrar_visor_pdf(drive_service, doc_nuevo["ID_Drive"], height=450)
                
                st.markdown("<br>", unsafe_allow_html=True)
                col_btn1, col_btn2, col_blank = st.columns([2, 2, 4])
                
                with col_btn1:
                    if st.button("🔄 Reemplazar Documento Anterior", type="primary", use_container_width=True):
                        with st.spinner("Ejecutando reemplazo..."):
                            # 1. Borrar viejo de drive
                            if id_drive_viejo:
                                try:
                                    enviar_a_papelera(drive_service, id_drive_viejo)
                                except:
                                    pass # Si ya no existe, ignoramos
                            
                            # 2. Actualizar fila en Excel (Sobrescribimos)
                            fila_nueva = preparar_fila_excel(doc_nuevo["ID_Drive"], doc_nuevo["Archivo"], datos_ia, "Reemplazado")
                            # gspread actualiza el rango exacto de la fila
                            rango = f"A{fila_excel_vieja}:O{fila_excel_vieja}"
                            hoja.update(values=[fila_nueva], range_name=rango)
                            
                            # 3. Mover el nuevo archivo a aprobados
                            mover_archivo_aprobados(drive_service, doc_nuevo["ID_Drive"], id_origen, id_destino)
                            
                        st.success("Reemplazo exitoso.")
                        st.rerun()
                        
                with col_btn2:
                    if st.button("🗑️ Descartar Documento Nuevo", use_container_width=True):
                        enviar_a_papelera(drive_service, doc_nuevo["ID_Drive"])
                        st.warning("Documento nuevo descartado.")
                        st.rerun()
