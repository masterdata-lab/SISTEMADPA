import streamlit as st
import pandas as pd
from datetime import datetime

# --- FUNCIONES AUXILIARES ---

def obtener_datos_sheets_cedulas(sheets_client, SHEET_ID):
    """Se conecta específicamente a la pestaña 'Cedulas'."""
    try:
        hoja = sheets_client.open_by_key(SHEET_ID).worksheet("Cedulas")
        registros = hoja.get_all_records()
        return hoja, registros
    except Exception as e:
        st.error(f"⚠️ Error al conectar con Google Sheets. Asegúrate de haber creado una pestaña llamada exactamente 'Cedulas'. Detalles: {e}")
        return None, []

def mostrar_visor_pdf(file_id, height=600):
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

def preparar_filas_excel_cedulas(id_drive, nombre, lista_patentes, tipo_cara, estado="Aprobado"):
    """
    Genera una lista de filas (una por cada patente). 
    Si la lista está vacía (ej. Dorso puro), genera una fila con "SIN PATENTE".
    """
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    filas = []
    
    if not lista_patentes:
        lista_patentes = ["SIN PATENTE"]
        
    for pat in lista_patentes:
        patente_limpia = str(pat).upper().strip()
        # Estructura para la pestaña Cédulas: ID, Archivo, Patente, Tipo_Cara, Estado, Fecha
        filas.append([id_drive, nombre, patente_limpia, tipo_cara, estado, fecha_hoy])
        
    return filas

# --- MÓDULO PRINCIPAL ---

def modulo_auditar(drive_service, sheets_client, TIPO_DOC, SHEET_ID):
    st.header(f"Auditoría de {TIPO_DOC}")
    
    id_origen = st.session_state.get(f"id_auditar_{TIPO_DOC}")
    id_destino = st.session_state.get(f"id_aprobados_{TIPO_DOC}")
    
    if not id_origen or not id_destino:
        st.error("Error con las carpetas de Drive. Por favor, ve a la pestaña 'Carga' primero.")
        return

    if "indice_seleccionado_cedulas" not in st.session_state:
        st.session_state.indice_seleccionado_cedulas = None
    if "indice_dup_seleccionado_cedulas" not in st.session_state:
        st.session_state.indice_dup_seleccionado_cedulas = None

    # 1. Obtener base de datos de CÉDULAS
    hoja, registros_bd = obtener_datos_sheets_cedulas(sheets_client, SHEET_ID)
    if hoja is None:
        return

    patentes_existentes = {str(reg.get('PATENTE', '')).upper(): (i + 2, reg) for i, reg in enumerate(registros_bd) if reg.get('PATENTE')}

    # 2. Escanear pendientes
    with st.spinner("Escaneando cédulas pendientes..."):
        query = f"'{id_origen}' in parents and trashed=false"
        resultados = drive_service.files().list(q=query, fields="files(id, name, appProperties)").execute(num_retries=3)
        archivos_pendientes = resultados.get('files', [])

    if not archivos_pendientes:
        st.success("🎉 No hay cédulas pendientes de auditar.")
        return

    lista_nuevos = []
    lista_duplicados = []
    
    for arch in archivos_pendientes:
        props = arch.get('appProperties', {})
        
        # Parsear las patentes que guardamos como string separado por comas
        patentes_raw = props.get('patentes', '')
        patentes_lista = [p.strip().upper() for p in patentes_raw.split(',')] if patentes_raw else []
        tipo_cara = props.get('tipo_cara', 'DESCONOCIDO')
        
        diccionario_datos = {
            "ID_Drive": arch['id'],
            "Archivo": arch['name'],
            "Patentes_Lista": patentes_lista,
            "Tipo_Cara": tipo_cara
        }
        
        # Si ALGUNA de las patentes ya existe, va a duplicados
        tiene_duplicado = any(p in patentes_existentes for p in patentes_lista if p != "SIN PATENTE")
        
        if tiene_duplicado:
            lista_duplicados.append(diccionario_datos)
        else:
            lista_nuevos.append(diccionario_datos)

    tab_nuevos, tab_duplicados = st.tabs([f"🟢 Nuevos ({len(lista_nuevos)})", f"🟠 Conflictos ({len(lista_duplicados)})"])

    # ==========================================
    # PESTAÑA 1: NUEVOS
    # ==========================================
    with tab_nuevos:
        if not lista_nuevos:
            st.info("No hay documentos nuevos.")
        else:
            col_lista, col_visor, col_datos = st.columns([2, 4, 3])
            
            with col_lista:
                st.subheader("Lista de Documentos")
                with st.container(height=550):
                    for idx, doc in enumerate(lista_nuevos):
                        pats_str = ", ".join(doc['Patentes_Lista']) if doc['Patentes_Lista'] else "DORSO (Sin Patente)"
                        texto_fila = f"📄 {doc['Archivo'][:15]} | 🔑 {pats_str[:15]}"
                        tipo_boton = "primary" if st.session_state.indice_seleccionado_cedulas == idx else "secondary"
                        
                        if st.button(texto_fila, key=f"btn_doc_ced_{idx}", use_container_width=True, type=tipo_boton):
                            st.session_state.indice_seleccionado_cedulas = idx
                            st.rerun()

            # --- VALIDAR SI HAY UNA FILA SELECCIONADA ---
            if st.session_state.indice_seleccionado_cedulas is not None and st.session_state.indice_seleccionado_cedulas < len(lista_nuevos):
                doc_actual = lista_nuevos[st.session_state.indice_seleccionado_cedulas]
                
                with col_visor:
                    st.subheader(f"Vista Previa")
                    mostrar_visor_pdf(doc_actual["ID_Drive"])
                
                with col_datos:
                    st.subheader("Auditoría de Cédula(s)")
                    st.info("💡 Puedes editar las patentes separándolas por coma.")
                    
                    with st.form("form_auditoria_cedulas"):
                        patentes_str_input = ", ".join(doc_actual["Patentes_Lista"])
                        
                        pat_input = st.text_input("Patentes detectadas (separadas por coma)", value=patentes_str_input)
                        cara_input = st.selectbox("Tipo de Cara", options=["FRENTE", "DORSO", "FRENTE_Y_DORSO", "DESCONOCIDO"], index=["FRENTE", "DORSO", "FRENTE_Y_DORSO", "DESCONOCIDO"].index(doc_actual["Tipo_Cara"]))
                        
                        btn_aprobar = st.form_submit_button("✅ Aprobar e Insertar Filas", type="primary", use_container_width=True)
                        btn_rechazar = st.form_submit_button("🗑️ Descartar (Papelera)", use_container_width=True)
                        
                        if btn_aprobar:
                            # Convertir el string editado de nuevo a lista
                            nuevas_patentes = [p.strip().upper() for p in pat_input.split(',')] if pat_input.strip() else []
                            
                            filas_a_insertar = preparar_filas_excel_cedulas(doc_actual["ID_Drive"], doc_actual["Archivo"], nuevas_patentes, cara_input)
                            
                            # Insertar múltiples filas de golpe
                            hoja.append_rows(filas_a_insertar)
                            mover_archivo_aprobados(drive_service, doc_actual["ID_Drive"], id_origen, id_destino)
                            
                            st.session_state.indice_seleccionado_cedulas = None
                            st.success(f"Se insertaron {len(filas_a_insertar)} filas exitosamente.")
                            st.rerun()
                            
                        if btn_rechazar:
                            enviar_a_papelera(drive_service, doc_actual["ID_Drive"])
                            st.session_state.indice_seleccionado_cedulas = None
                            st.warning("Documento descartado.")
                            st.rerun()
            else:
                with col_visor:
                    st.info("👈 Selecciona un documento de la lista.")

    # ==========================================
    # PESTAÑA 2: CONFLICTOS / DUPLICADOS
    # ==========================================
    with tab_duplicados:
        if not lista_duplicados:
            st.info("No se detectaron conflictos de patentes.")
        else:
            st.warning("⚠️ Los siguientes documentos contienen al menos una patente que ya existe en la base de datos de Cédulas. En esta versión, se recomienda revisarlos manualmente o descartarlos.")
            
            for idx, doc in enumerate(lista_duplicados):
                pats_str = ", ".join(doc['Patentes_Lista'])
                with st.expander(f"📄 {doc['Archivo']} | Patentes: {pats_str}"):
                    col_pdf, col_acc = st.columns([2, 1])
                    with col_pdf:
                        mostrar_visor_pdf(doc["ID_Drive"], height=300)
                    with col_acc:
                        st.write("**Patentes extraídas:**", pats_str)
                        st.write("**Tipo:**", doc["Tipo_Cara"])
                        
                        if st.button("🗑️ Enviar a Papelera", key=f"btn_trash_{idx}", use_container_width=True):
                            enviar_a_papelera(drive_service, doc["ID_Drive"])
                            st.success("Enviado a papelera.")
                            st.rerun()
