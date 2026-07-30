import streamlit as st
import pandas as pd
from datetime import datetime

# --- FUNCIONES AUXILIARES ---

def obtener_datos_sheets(sheets_client, SHEET_ID):
    try:
        hoja = sheets_client.open_by_key(SHEET_ID).sheet1
        registros = hoja.get_all_records()
        return hoja, registros
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None, []

def mostrar_visor_pdf(file_id, height=600):
    """Muestra el PDF utilizando el visor nativo de Google Drive mediante iframe."""
    url_preview = f"https://drive.google.com/file/d/{file_id}/preview"
    st.markdown(
        f'<iframe src="{url_preview}" width="100%" height="{height}px" style="border: none; border-radius: 8px;"></iframe>', 
        unsafe_allow_html=True
    )

def mover_archivo_aprobados(drive_service, file_id, id_origen, id_destino):
    drive_service.files().update(
        fileId=file_id, addParents=id_destino, removeParents=id_origen, fields='id, parents'
    ).execute(num_retries=3)

def enviar_a_papelera(drive_service, file_id):
    drive_service.files().update(fileId=file_id, body={'trashed': True}).execute(num_retries=3)

def preparar_fila_excel(id_drive, nombre, datos, estado="Aprobado"):
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    def limpiar(texto):
        return str(texto).upper().strip() if texto else ""

    return [
        id_drive, nombre, limpiar(datos.get('patente')), limpiar(datos.get('marca')),
        limpiar(datos.get('modelo')), limpiar(datos.get('tipo')), limpiar(datos.get('nro_chasis')),
        limpiar(datos.get('nro_motor')), limpiar(datos.get('titular')), limpiar(datos.get('cuit')),
        limpiar(datos.get('lugar_radicacion')), limpiar(datos.get('provincia_radicacion')),
        limpiar(datos.get('fecha_inscripcion_inicial')), estado, fecha_hoy
    ]

# --- MÓDULO PRINCIPAL ---

def modulo_auditar(drive_service, sheets_client, TIPO_DOC, SHEET_ID):
    st.header(f"Auditoría de {TIPO_DOC}")
    
    id_origen = st.session_state.get(f"id_auditar_{TIPO_DOC}")
    id_destino = st.session_state.get(f"id_aprobados_{TIPO_DOC}")
    
    if not id_origen or not id_destino:
        st.error("Error con las carpetas de Drive. Por favor, recarga la página.")
        return

    # Inicializar estados de selección si no existen
    if "indice_seleccionado" not in st.session_state:
        st.session_state.indice_seleccionado = None
    if "indice_dup_seleccionado" not in st.session_state:
        st.session_state.indice_dup_seleccionado = None

    hoja, registros_bd = obtener_datos_sheets(sheets_client, SHEET_ID)
    if hoja is None:
        return

    patentes_existentes = {str(reg.get('PATENTE', '')).upper(): (i + 2, reg) for i, reg in enumerate(registros_bd) if reg.get('PATENTE')}

    with st.spinner("Escaneando documentos pendientes..."):
        query = f"'{id_origen}' in parents and trashed=false"
        resultados = drive_service.files().list(q=query, fields="files(id, name, appProperties)").execute(num_retries=3)
        archivos_pendientes = resultados.get('files', [])

    if not archivos_pendientes:
        st.success("🎉 No hay documentos pendientes de auditar.")
        return

    lista_nuevos = []
    lista_duplicados = []
    
    for arch in archivos_pendientes:
        props = arch.get('appProperties', {})
        patente = props.get('patente', '').upper() if props.get('patente') else "SIN PATENTE"
        
        diccionario_datos = {
            "ID_Drive": arch['id'],
            "Archivo": arch['name'],
            "Patente": patente,
            "Titular": props.get('titular', ''),
            "Data_Raw": props
        }
        
        if patente in patentes_existentes and patente != "SIN PATENTE":
            lista_duplicados.append(diccionario_datos)
        else:
            lista_nuevos.append(diccionario_datos)

    tab_nuevos, tab_duplicados = st.tabs([f"🟢 Nuevos ({len(lista_nuevos)})", f"🟠 Duplicados ({len(lista_duplicados)})"])

    # ==========================================
    # PESTAÑA 1: NUEVOS
    # ==========================================
    with tab_nuevos:
        if not lista_nuevos:
            st.info("No hay documentos nuevos.")
        else:
            col_lista, col_visor, col_datos = st.columns([2, 2, 1.5])
            
            with col_lista:
                st.subheader("Lista de Documentos")
                st.info("💡 Haz clic sobre cualquier fila para auditar el documento.")
                
                with st.container(height=550):
                    cabecera = st.columns([1, 2, 2])
                    cabecera[0].markdown("**Patente**")
                    cabecera[1].markdown("**Archivo**")
                    cabecera[2].markdown("**Titular**")
                    st.divider()
                    
                    for idx, doc in enumerate(lista_nuevos):
                        texto_fila = f"🔑 {doc['Patente']}  |  📄 {doc['Archivo'][:20]}...  |  👤 {doc['Titular'][:15]}"
                        tipo_boton = "primary" if st.session_state.indice_seleccionado == idx else "secondary"
                        
                        if st.button(texto_fila, key=f"btn_doc_{idx}", use_container_width=True, type=tipo_boton):
                            st.session_state.indice_seleccionado = idx
                            st.rerun()

            # --- VALIDAR SI HAY UNA FILA SELECCIONADA ---
            if st.session_state.indice_seleccionado is not None and st.session_state.indice_seleccionado < len(lista_nuevos):
                doc_actual = lista_nuevos[st.session_state.indice_seleccionado]
                datos_ia = doc_actual["Data_Raw"] 
                
                with col_visor:
                    st.subheader(f"📄 {doc_actual['Archivo']}")
                    mostrar_visor_pdf(doc_actual["ID_Drive"])
                
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
                            
                            st.session_state.indice_seleccionado = None
                            st.success("Aprobado exitosamente.")
                            st.rerun()
                            
                        if btn_rechazar:
                            enviar_a_papelera(drive_service, doc_actual["ID_Drive"])
                            st.session_state.indice_seleccionado = None
                            st.warning("Documento enviado a la papelera.")
                            st.rerun()
            else:
                with col_visor:
                    st.info("👈 Selecciona un documento de la lista.")

    # ==========================================
    # PESTAÑA 2: DUPLICADOS
    # ==========================================
    with tab_duplicados:
        if not lista_duplicados:
            st.info("No se detectaron conflictos de patentes.")
        else:
            col_lista_dup, col_resolucion = st.columns([1.5, 3.5])
            
            with col_lista_dup:
                st.subheader("Conflictos Detectados")
                with st.container(height=550):
                    for idx, doc in enumerate(lista_duplicados):
                        texto_fila = f"⚠️ {doc['Patente']} | {doc['Titular'][:15]}"
                        tipo_boton = "primary" if st.session_state.indice_dup_seleccionado == idx else "secondary"
                        
                        if st.button(texto_fila, key=f"btn_dup_{idx}", use_container_width=True, type=tipo_boton):
                            st.session_state.indice_dup_seleccionado = idx
                            st.rerun()

            if st.session_state.indice_dup_seleccionado is not None and st.session_state.indice_dup_seleccionado < len(lista_duplicados):
                with col_resolucion:
                    doc_nuevo = lista_duplicados[st.session_state.indice_dup_seleccionado]
                    patente_conflicto = doc_nuevo["Patente"]
                    
                    fila_excel_vieja, datos_excel_viejos = patentes_existentes[patente_conflicto]
                    id_drive_viejo = datos_excel_viejos.get('ID_DRIVE')
                    
                    st.subheader(f"⚖️ Resolución: Dominio {patente_conflicto}")
                    
                    c_pdf_viejo, c_data_vieja, c_data_nueva, c_pdf_nuevo = st.columns(4)
                    
                    with c_pdf_viejo:
                        st.caption("📄 PDF Anterior")
                        if id_drive_viejo:
                            mostrar_visor_pdf(id_drive_viejo, height=450)
                        else:
                            st.error("No hallado.")
                    
                    with c_data_vieja:
                        st.caption("🗄️ Datos Guardados")
                        st.info(f"**Titular:** {datos_excel_viejos.get('TITULAR', '')}\n\n**Chasis:** {datos_excel_viejos.get('NRO_CHASIS', '')}")
                        
                    with c_data_nueva:
                        st.caption("🆕 Nuevos Datos")
                        datos_ia = doc_nuevo["Data_Raw"]
                        st.success(f"**Titular:** {datos_ia.get('titular', '')}\n\n**Chasis:** {datos_ia.get('nro_chasis', '')}")
                        
                    with c_pdf_nuevo:
                        st.caption("📄 PDF Nuevo")
                        mostrar_visor_pdf(doc_nuevo["ID_Drive"], height=450)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.button("🔄 Reemplazar Documento Anterior", type="primary", use_container_width=True):
                            with st.spinner("Reemplazando..."):
                                if id_drive_viejo:
                                    try:
                                        enviar_a_papelera(drive_service, id_drive_viejo)
                                    except:
                                        pass 
                                
                                fila_nueva = preparar_fila_excel(doc_nuevo["ID_Drive"], doc_nuevo["Archivo"], datos_ia, "Reemplazado")
                                rango = f"A{fila_excel_vieja}:O{fila_excel_vieja}"
                                hoja.update(values=[fila_nueva], range_name=rango)
                                mover_archivo_aprobados(drive_service, doc_nuevo["ID_Drive"], id_origen, id_destino)
                                
                            st.session_state.indice_dup_seleccionado = None
                            st.success("Reemplazo exitoso.")
                            st.rerun()
                            
                    with col_btn2:
                        if st.button("🗑️ Descartar Documento Nuevo", use_container_width=True):
                            enviar_a_papelera(drive_service, doc_nuevo["ID_Drive"])
                            st.session_state.indice_dup_seleccionado = None
                            st.warning("Documento nuevo descartado.")
                            st.rerun()
