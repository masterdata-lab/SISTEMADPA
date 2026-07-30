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
    """Descarga el PDF y lo muestra usando st.markdown para evitar bloqueos de Chrome."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        
        base64_pdf = base64.b64encode(fh.getvalue()).decode('utf-8')
        # Inyectamos el visor nativo directamente saltando el sandbox del componente
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="{height}" type="application/pdf" style="border: none;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
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
    
    # Manejamos los datos previendo que puedan estar vacíos (None o string vacío)
    def limpiar(texto):
        return str(texto).upper().strip() if texto else ""

    return [
        id_drive,
        nombre,
        limpiar(datos.get('patente')),
        limpiar(datos.get('marca')),
        limpiar(datos.get('modelo')),
        limpiar(datos.get('tipo')),
        limpiar(datos.get('nro_chasis')),
        limpiar(datos.get('nro_motor')),
        limpiar(datos.get('titular')),
        limpiar(datos.get('cuit')),
        limpiar(datos.get('lugar_radicacion')),
        limpiar(datos.get('provincia_radicacion')),
        limpiar(datos.get('fecha_inscripcion_inicial')),
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

    patentes_existentes = {str(reg.get('PATENTE', '')).upper(): (i + 2, reg) for i, reg in enumerate(registros_bd) if reg.get('PATENTE')}

    with st.spinner("Escaneando documentos pendientes..."):
        query = f"'{id_origen}' in parents and trashed=false"
        resultados = drive_service.files().list(q=query, fields="files(id, name, appProperties)").execute(num_retries=3)
        archivos_pendientes = resultados.get('files', [])

    if not archivos_pendientes:
        st.success("🎉 No hay documentos pendientes de auditar.")
        return

    # Listas en Python puro (para no perder la estructura del diccionario)
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
            "Chasis": props.get('nro_chasis', ''),
            "Data_Raw": props # Guardamos el diccionario intacto
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
            col_lista, col_visor, col_datos = st.columns([1.5, 2, 1.5])
            
            with col_lista:
                st.subheader("Lista de Documentos")
                # Creamos el DataFrame pero SOLO con lo que queremos mostrar
                df_mostrar = pd.DataFrame(lista_nuevos)[["Patente", "Archivo", "Titular", "Chasis"]]
                
                # Nueva forma de selección nativa de Streamlit (haciendo clic en la fila)
                evento_seleccion = st.dataframe(
                    df_mostrar,
                    on_select="rerun",
                    selection_mode="multi",
                    use_container_width=True,
                    hide_index=True
                )
                
                indices_seleccionados = evento_seleccion.selection.rows

            # --- SI SELECCIONÓ EXACTAMENTE UNO ---
            if len(indices_seleccionados) == 1:
                # Buscamos en nuestra lista Python original para evitar el AttributeError
                doc_actual = lista_nuevos[indices_seleccionados[0]]
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

            # --- SI SELECCIONÓ VARIOS (APROBACIÓN MASIVA) ---
            elif len(indices_seleccionados) > 1:
                with col_visor:
                    st.info(f"Seleccionaste {len(indices_seleccionados)} documentos para aprobación masiva.")
                    if st.button("🚀 Aprobar Lote Seleccionado", type="primary", use_container_width=True):
                        barra = st.progress(0)
                        for i, idx in enumerate(indices_seleccionados):
                            doc_actual = lista_nuevos[idx]
                            fila = preparar_fila_excel(doc_actual["ID_Drive"], doc_actual["Archivo"], doc_actual["Data_Raw"])
                            hoja.append_row(fila)
                            mover_archivo_aprobados(drive_service, doc_actual["ID_Drive"], id_origen, id_destino)
                            barra.progress((i + 1) / len(indices_seleccionados))
                        st.success("Lote aprobado exitosamente.")
                        st.rerun()
            else:
                with col_visor:
                    st.write("👈 Haz clic en cualquier documento de la lista para auditarlo.")

    # ==========================================
    # PESTAÑA 2: DUPLICADOS
    # ==========================================
    with tab_duplicados:
        if not lista_duplicados:
            st.info("No se detectaron conflictos de patentes.")
        else:
            df_mostrar_dup = pd.DataFrame(lista_duplicados)[["Patente", "Archivo", "Titular", "Chasis"]]
            st.write("Haz clic en una fila para resolver el conflicto.")
            
            evento_seleccion_dup = st.dataframe(
                df_mostrar_dup,
                on_select="rerun",
                selection_mode="single", # Forzamos a que solo puedan elegir de a uno
                use_container_width=True,
                hide_index=True
            )
            
            indices_dup = evento_seleccion_dup.selection.rows
            
            if len(indices_dup) == 1:
                doc_nuevo = lista_duplicados[indices_dup[0]]
                patente_conflicto = doc_nuevo["Patente"]
                
                fila_excel_vieja, datos_excel_viejos = patentes_existentes[patente_conflicto]
                id_drive_viejo = datos_excel_viejos.get('ID_DRIVE')
                
                st.markdown("---")
                st.subheader(f"⚖️ Resolución de Conflicto: Dominio {patente_conflicto}")
                
                c_pdf_viejo, c_data_vieja, c_data_nueva, c_pdf_nuevo = st.columns(4)
                
                with c_pdf_viejo:
                    st.caption("📄 PDF Aprobado Anteriormente")
                    if id_drive_viejo:
                        mostrar_visor_pdf(drive_service, id_drive_viejo, height=450)
                    else:
                        st.error("No se encontró el archivo anterior en Drive.")
                
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
                            if id_drive_viejo:
                                try:
                                    enviar_a_papelera(drive_service, id_drive_viejo)
                                except:
                                    pass 
                            
                            fila_nueva = preparar_fila_excel(doc_nuevo["ID_Drive"], doc_nuevo["Archivo"], datos_ia, "Reemplazado")
                            rango = f"A{fila_excel_vieja}:O{fila_excel_vieja}"
                            hoja.update(values=[fila_nueva], range_name=rango)
                            mover_archivo_aprobados(drive_service, doc_nuevo["ID_Drive"], id_origen, id_destino)
                            
                        st.success("Reemplazo exitoso.")
                        st.rerun()
                        
                with col_btn2:
                    if st.button("🗑️ Descartar Documento Nuevo", use_container_width=True):
                        enviar_a_papelera(drive_service, doc_nuevo["ID_Drive"])
                        st.warning("Documento nuevo descartado.")
                        st.rerun()
