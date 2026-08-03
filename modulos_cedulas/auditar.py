import streamlit as st
import pandas as pd
from datetime import datetime
import io
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pypdf import PdfReader, PdfWriter

# --- FUNCIONES AUXILIARES DE DRIVE Y PDFs ---

def obtener_datos_sheets_cedulas(sheets_client, SHEET_ID):
    try:
        hoja = sheets_client.open_by_key(SHEET_ID).worksheet("Cedulas")
        registros = hoja.get_all_records()
        return hoja, registros
    except Exception as e:
        st.error(f"⚠️ Error al conectar con Google Sheets (Pestaña 'Cedulas'). Detalles: {e}")
        return None, []

def mostrar_visor_pdf(file_id, height=600):
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
    except Exception:
        return None

def unificar_pdfs_en_drive(drive_service, id_frente, id_dorso, id_destino, nombre_final):
    """Descarga el frente y el dorso, los une en un solo PDF y lo sube a Aprobados."""
    bytes_frente = descargar_pdf_bytes(drive_service, id_frente)
    bytes_dorso = descargar_pdf_bytes(drive_service, id_dorso)
    
    escritor = PdfWriter()
    
    # Agregamos las páginas del Frente
    if bytes_frente:
        lector_f = PdfReader(io.BytesIO(bytes_frente))
        for page in lector_f.pages:
            escritor.add_page(page)
            
    # Agregamos las páginas del Dorso
    if bytes_dorso:
        lector_d = PdfReader(io.BytesIO(bytes_dorso))
        for page in lector_d.pages:
            escritor.add_page(page)
            
    b = io.BytesIO()
    escritor.write(b)
    pdf_unificado = b.getvalue()
    
    # Subir el archivo nuevo unificado
    file_metadata = {'name': nombre_final, 'parents': [id_destino]}
    media = MediaIoBaseUpload(io.BytesIO(pdf_unificado), mimetype='application/pdf', resumable=True)
    archivo_creado = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute(num_retries=3)
    
    return archivo_creado['id']

def mover_archivo_aprobados(drive_service, file_id, id_origen, id_destino):
    drive_service.files().update(
        fileId=file_id, addParents=id_destino, removeParents=id_origen, fields='id, parents'
    ).execute(num_retries=3)

def enviar_a_papelera(drive_service, file_id):
    drive_service.files().update(fileId=file_id, body={'trashed': True}).execute(num_retries=3)

def preparar_filas_excel_cedulas(id_drive, nombre, lista_patentes, tipo_cara, estado="Aprobado"):
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    filas = []
    if not lista_patentes:
        lista_patentes = ["SIN PATENTE"]
        
    for pat in lista_patentes:
        filas.append([id_drive, nombre, str(pat).upper().strip(), tipo_cara, estado, fecha_hoy])
    return filas

# --- MÓDULO PRINCIPAL ---

def modulo_auditar(drive_service, sheets_client, TIPO_DOC, SHEET_ID):
    st.header(f"Auditoría de {TIPO_DOC}")
    
    id_origen = st.session_state.get(f"id_auditar_{TIPO_DOC}")
    id_destino = st.session_state.get(f"id_aprobados_{TIPO_DOC}")
    
    if not id_origen or not id_destino:
        st.error("Error con las carpetas de Drive. Por favor, ve a la pestaña 'Carga' primero.")
        return

    # Manejo de estado
    if "idx_ced_nuevo" not in st.session_state: st.session_state.idx_ced_nuevo = None
    if "idx_ced_unif" not in st.session_state: st.session_state.idx_ced_unif = None
    if "idx_ced_dup" not in st.session_state: st.session_state.idx_ced_dup = None

    hoja, registros_bd = obtener_datos_sheets_cedulas(sheets_client, SHEET_ID)
    if hoja is None:
        return

    # Mapeo: PATENTE -> (fila_excel, registro_dict)
    patentes_existentes = {str(reg.get('PATENTE', '')).upper(): (i + 2, reg) for i, reg in enumerate(registros_bd) if reg.get('PATENTE')}

    with st.spinner("Escaneando cédulas pendientes..."):
        query = f"'{id_origen}' in parents and trashed=false"
        resultados = drive_service.files().list(q=query, fields="files(id, name, appProperties)").execute(num_retries=3)
        archivos_pendientes = resultados.get('files', [])

    if not archivos_pendientes:
        st.success("🎉 No hay cédulas pendientes de auditar.")
        return

    lista_nuevos = []
    lista_unificaciones = []
    lista_duplicados = []
    
    for arch in archivos_pendientes:
        props = arch.get('appProperties', {})
        pat_raw = props.get('patentes', '')
        patentes_lista = [p.strip().upper() for p in pat_raw.split(',')] if pat_raw else []
        tipo_cara = str(props.get('tipo_cara', 'DESCONOCIDO')).upper()
        
        doc_data = {
            "ID_Drive": arch['id'],
            "Archivo": arch['name'],
            "Patentes_Lista": patentes_lista,
            "Tipo_Cara": tipo_cara
        }
        
        # Categorización Inteligente: Nuevo vs Unificación vs Conflicto
        categoria = "NUEVO"
        for p in patentes_lista:
            if p in patentes_existentes and p != "SIN PATENTE":
                cara_existente = str(patentes_existentes[p][1].get('TIPO_CARA', '')).upper()
                
                # Si las caras son IGUALES o ya está unificada, es un CONFLICTO (Duplicado)
                if tipo_cara == cara_existente or cara_existente == "FRENTE_Y_DORSO" or tipo_cara == "DESCONOCIDO":
                    categoria = "CONFLICTO"
                    break # Un solo conflicto manda todo el archivo a la pestaña duplicados
                
                # Si las caras son OPUESTAS, es una UNIFICACIÓN
                elif (tipo_cara == "FRENTE" and cara_existente == "DORSO") or (tipo_cara == "DORSO" and cara_existente == "FRENTE"):
                    if categoria != "CONFLICTO":
                        categoria = "UNIFICACION"
                        
        if categoria == "CONFLICTO":
            lista_duplicados.append(doc_data)
        elif categoria == "UNIFICACION":
            lista_unificaciones.append(doc_data)
        else:
            lista_nuevos.append(doc_data)

    # CREACIÓN DE 3 PESTAÑAS
    tab_nuevos, tab_unif, tab_dup = st.tabs([
        f"🟢 Nuevos ({len(lista_nuevos)})", 
        f"🔵 Para Unificar ({len(lista_unificaciones)})", 
        f"🟠 Conflictos ({len(lista_duplicados)})"
    ])

    # ==========================================
    # PESTAÑA 1: NUEVOS
    # ==========================================
    with tab_nuevos:
        if not lista_nuevos:
            st.info("No hay documentos totalmente nuevos.")
        else:
            col_lista, col_visor, col_datos = st.columns([2, 4, 3])
            with col_lista:
                st.subheader("Lista de Documentos")
                with st.container(height=550):
                    for idx, doc in enumerate(lista_nuevos):
                        pats_str = ", ".join(doc['Patentes_Lista']) if doc['Patentes_Lista'] else "DORSO"
                        texto = f"📄 {doc['Archivo'][:15]} | 🔑 {pats_str[:15]}"
                        btn_type = "primary" if st.session_state.idx_ced_nuevo == idx else "secondary"
                        if st.button(texto, key=f"n_{idx}", use_container_width=True, type=btn_type):
                            st.session_state.idx_ced_nuevo = idx
                            st.rerun()

            if st.session_state.idx_ced_nuevo is not None and st.session_state.idx_ced_nuevo < len(lista_nuevos):
                doc = lista_nuevos[st.session_state.idx_ced_nuevo]
                with col_visor:
                    st.subheader("Vista Previa")
                    mostrar_visor_pdf(doc["ID_Drive"])
                with col_datos:
                    st.subheader("Auditoría")
                    with st.form("form_nuevo"):
                        pat_input = st.text_input("Patentes (separadas por coma)", value=", ".join(doc["Patentes_Lista"]))
                        cara_input = st.selectbox("Tipo", ["FRENTE", "DORSO"], index=0 if doc["Tipo_Cara"]=="FRENTE" else 1)
                        if st.form_submit_button("✅ Aprobar e Insertar", type="primary", use_container_width=True):
                            nuevas_patentes = [p.strip().upper() for p in pat_input.split(',')] if pat_input.strip() else []
                            filas = preparar_filas_excel_cedulas(doc["ID_Drive"], doc["Archivo"], nuevas_patentes, cara_input)
                            hoja.append_rows(filas)
                            mover_archivo_aprobados(drive_service, doc["ID_Drive"], id_origen, id_destino)
                            st.session_state.idx_ced_nuevo = None
                            st.rerun()
                        if st.form_submit_button("🗑️ Descartar", use_container_width=True):
                            enviar_a_papelera(drive_service, doc["ID_Drive"])
                            st.session_state.idx_ced_nuevo = None
                            st.rerun()

    # ==========================================
    # PESTAÑA 2: UNIFICACIONES (FRENTE + DORSO)
    # ==========================================
    with tab_unif:
        if not lista_unificaciones:
            st.info("No se encontraron complementos para unificar.")
        else:
            col_lista_u, col_res_u = st.columns([1, 5]) # Formato Wide
            with col_lista_u:
                st.subheader("Complementos")
                with st.container(height=550):
                    for idx, doc in enumerate(lista_unificaciones):
                        pats_str = ", ".join(doc['Patentes_Lista'])
                        btn_type = "primary" if st.session_state.idx_ced_unif == idx else "secondary"
                        if st.button(f"🔗 {pats_str}", key=f"u_{idx}", use_container_width=True, type=btn_type):
                            st.session_state.idx_ced_unif = idx
                            st.rerun()

            if st.session_state.idx_ced_unif is not None and st.session_state.idx_ced_unif < len(lista_unificaciones):
                with col_res_u:
                    doc = lista_unificaciones[st.session_state.idx_ced_unif]
                    patente_principal = doc['Patentes_Lista'][0]
                    fila_bd, datos_bd = patentes_existentes[patente_principal]
                    id_guardado = datos_bd.get("ID_DRIVE")
                    cara_guardada = datos_bd.get("TIPO_CARA")
                    
                    st.subheader(f"🤝 Unificación Encontrada: Dominio {patente_principal}")
                    st.success(f"El sistema ha detectado que tienes el **{cara_guardada}** guardado y estás subiendo el **{doc['Tipo_Cara']}**. Al unificarlos, se crearán un único archivo PDF de 2 páginas.")
                    
                    c_old, c_new = st.columns(2)
                    with c_old:
                        st.caption(f"📁 Documento Guardado ({cara_guardada})")
                        mostrar_visor_pdf(id_guardado, height=400)
                    with c_new:
                        st.caption(f"🆕 Documento Nuevo ({doc['Tipo_Cara']})")
                        mostrar_visor_pdf(doc["ID_Drive"], height=400)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_b1, col_b2 = st.columns(2)
                    
                    with col_b1:
                        if st.button("🔗 Fusionar y Unificar PDFs", type="primary", use_container_width=True):
                            with st.spinner("Fusionando documentos..."):
                                id_frente = id_guardado if cara_guardada == "FRENTE" else doc["ID_Drive"]
                                id_dorso = doc["ID_Drive"] if cara_guardada == "FRENTE" else id_guardado
                                
                                nombre_unificado = f"Cedula_Unificada_{patente_principal}.pdf"
                                nuevo_id = unificar_pdfs_en_drive(drive_service, id_frente, id_dorso, id_destino, nombre_unificado)
                                
                                # Actualizar la base de datos
                                fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                for p in doc["Patentes_Lista"]:
                                    if p in patentes_existentes:
                                        f_bd = patentes_existentes[p][0]
                                        fila_act = [nuevo_id, nombre_unificado, p, "FRENTE_Y_DORSO", "Aprobado", fecha_hoy]
                                        hoja.update(values=[fila_act], range_name=f"A{f_bd}:F{f_bd}")
                                    else:
                                        # Si había otra patente en la hoja que no estaba en BD, la agregamos
                                        hoja.append_row([nuevo_id, nombre_unificado, p, "FRENTE_Y_DORSO", "Aprobado", fecha_hoy])
                                
                                # Enviar archivos originales fragmentados a la papelera
                                try: enviar_a_papelera(drive_service, id_guardado)
                                except: pass
                                try: enviar_a_papelera(drive_service, doc["ID_Drive"])
                                except: pass
                                
                            st.session_state.idx_ced_unif = None
                            st.success("¡Documentos fusionados exitosamente!")
                            st.rerun()
                            
                    with col_b2:
                        if st.button("🗑️ Descartar Nuevo Documento", use_container_width=True):
                            enviar_a_papelera(drive_service, doc["ID_Drive"])
                            st.session_state.idx_ced_unif = None
                            st.rerun()

    # ==========================================
    # PESTAÑA 3: CONFLICTOS / DUPLICADOS
    # ==========================================
    with tab_dup:
        if not lista_duplicados:
            st.info("No se detectaron conflictos.")
        else:
            col_lista_d, col_res_d = st.columns([1, 5]) # Formato Wide Replicado
            with col_lista_d:
                st.subheader("Conflictos")
                with st.container(height=550):
                    for idx, doc in enumerate(lista_duplicados):
                        pats_str = ", ".join(doc['Patentes_Lista'])
                        btn_type = "primary" if st.session_state.idx_ced_dup == idx else "secondary"
                        if st.button(f"⚠️ {pats_str}", key=f"d_{idx}", use_container_width=True, type=btn_type):
                            st.session_state.idx_ced_dup = idx
                            st.rerun()

            if st.session_state.idx_ced_dup is not None and st.session_state.idx_ced_dup < len(lista_duplicados):
                with col_res_d:
                    doc = lista_duplicados[st.session_state.idx_ced_dup]
                    patente_principal = doc['Patentes_Lista'][0]
                    fila_bd, datos_bd = patentes_existentes[patente_principal]
                    id_viejo = datos_bd.get('ID_DRIVE')
                    
                    st.subheader(f"⚖️ Conflicto de Duplicidad: Dominio {patente_principal}")
                    st.warning("⚠️ Ya existe una cara de este tipo registrada en el sistema. Selecciona cuál versión deseas conservar.")
                    
                    c_old, c_new = st.columns(2)
                    with c_old:
                        st.caption(f"📄 Guardado ({datos_bd.get('TIPO_CARA')})")
                        if id_viejo: mostrar_visor_pdf(id_viejo, height=450)
                    with c_new:
                        st.caption(f"🆕 Nuevo ({doc['Tipo_Cara']})")
                        mostrar_visor_pdf(doc["ID_Drive"], height=450)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    cb1, cb2 = st.columns(2)
                    with cb1:
                        if st.button("🔄 Reemplazar por el Nuevo", type="primary", use_container_width=True):
                            with st.spinner("Reemplazando..."):
                                if id_viejo:
                                    try: enviar_a_papelera(drive_service, id_viejo)
                                    except: pass
                                
                                fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                fila_act = [doc["ID_Drive"], doc["Archivo"], patente_principal, doc["Tipo_Cara"], "Reemplazado", fecha_hoy]
                                hoja.update(values=[fila_act], range_name=f"A{fila_bd}:F{fila_bd}")
                                mover_archivo_aprobados(drive_service, doc["ID_Drive"], id_origen, id_destino)
                                
                            st.session_state.idx_ced_dup = None
                            st.rerun()
                    with cb2:
                        if st.button("🗑️ Descartar y Conservar Original", use_container_width=True):
                            enviar_a_papelera(drive_service, doc["ID_Drive"])
                            st.session_state.idx_ced_dup = None
                            st.rerun()
