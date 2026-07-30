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

def mostrar_visor_pdf(file_id, height=750): # Aumenté un poco la altura del visor para compensar los nuevos campos
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

# --- MÓDULO PRINCIPAL ---

def modulo_buscar(drive_service, sheets_client, SHEET_ID):
    st.header("🔍 Buscar y Editar Documento")
    st.divider()

    # Inicializamos el estado de edición si no existe
    if "modo_edicion" not in st.session_state:
        st.session_state.modo_edicion = False

    # 1. Cargamos la base de datos y la hoja (necesaria para editar)
    with st.spinner("Cargando base de datos..."):
        hoja, registros_bd = obtener_hoja_y_datos(sheets_client, SHEET_ID)
        
    if hoja is None:
        return

    # Extraemos solo las patentes para el buscador
    lista_patentes = sorted(list(set([str(reg.get('PATENTE', '')).strip().upper() for reg in registros_bd if reg.get('PATENTE')])))

    # 2. Barra de búsqueda
    col_busqueda, col_vacia = st.columns([1, 2])
    with col_busqueda:
        # Si cambiamos de patente en el buscador, salimos del modo edición por seguridad
        patente_input = st.selectbox(
            "Seleccione o escriba la Patente a buscar:", 
            options=lista_patentes,
            index=None,
            placeholder="Ej. AG871VL",
            on_change=lambda: st.session_state.update(modo_edicion=False)
        )

    # 3. Mostrar resultados
    if patente_input:
        # Buscamos el registro exacto y guardamos su índice
        # Le sumamos 2 al índice porque Google Sheets empieza en la fila 1 y la fila 1 es el encabezado.
        fila_indice = next((i for i, reg in enumerate(registros_bd) if str(reg.get('PATENTE', '')).strip().upper() == patente_input), None)
        
        if fila_indice is not None:
            registro_encontrado = registros_bd[fila_indice]
            fila_real_sheets = fila_indice + 2 
            
            st.success(f"✅ Documento cargado: **{patente_input}**")
            id_drive = registro_encontrado.get('ID_DRIVE')
            
            # Layout [4, 3]
            col_visor, col_datos = st.columns([4, 3])
            
            with col_visor:
                st.subheader("Vista Previa")
                if id_drive:
                    mostrar_visor_pdf(id_drive)
                else:
                    st.error("El registro no tiene un documento asociado para visualizar.")

            with col_datos:
                # --- CABECERA DE DATOS Y BOTÓN DE EDICIÓN ---
                c_tit, c_btn = st.columns([2, 1])
                c_tit.subheader("Datos del Vehículo")
                
                # Botón para activar modo edición
                if not st.session_state.modo_edicion:
                    if c_btn.button("✏️ Editar", use_container_width=True):
                        st.session_state.modo_edicion = True
                        st.rerun()

                # --- LÓGICA DE VISTA vs EDICIÓN ---
                if not st.session_state.modo_edicion:
                    # MODO LECTURA (Deshabilitado)
                    # He agrupado visualmente los campos para que no sea una lista interminable
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
                    # MODO EDICIÓN (Formulario habilitado)
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
                                # Descargamos la fila original
                                fila_original = hoja.row_values(fila_real_sheets)
                                
                                # Asegurarnos de que la fila tenga al menos 15 elementos para cubrir todas las columnas
                                while len(fila_original) < 15:
                                    fila_original.append("")
                                
                                # Actualizamos columnas (índices basados en tu estructura de auditar.py)
                                # A=0(ID), B=1(Nombre), C=2(Pat), D=3(Mar), E=4(Mod), F=5(Tip), G=6(Cha), H=7(Mot), 
                                # I=8(Tit), J=9(Cuit), K=10(Lug), L=11(Prov), M=12(Fec), N=13(Est), O=14(FechaAud)
                                
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
                                
                                # Enviamos la fila completa actualizada a Sheets
                                hoja.update(values=[fila_original], range_name=f"A{fila_real_sheets}:O{fila_real_sheets}")
                                
                            st.session_state.modo_edicion = False
                            st.toast("✅ Datos actualizados correctamente")
                            st.rerun()
                
                # --- ACCIONES (Solo visibles en modo lectura) ---
                if not st.session_state.modo_edicion:
                    st.divider()
                    st.subheader("Acciones Rápidas")
                    
                    if id_drive:
                        pdf_bytes = descargar_pdf_bytes(drive_service, id_drive)
                        if pdf_bytes:
                            st.download_button(
                                label="📥 Descargar PDF",
                                data=pdf_bytes,
                                file_name=f"Titulo_{patente_input}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                type="primary"
                            )
                        
                        url_drive = f"https://drive.google.com/file/d/{id_drive}/view"
                        asunto = urllib.parse.quote(f"Título del Vehículo - Patente {patente_input}")
                        cuerpo = urllib.parse.quote(f"Hola,\n\nTe comparto la información y el documento del vehículo patente {patente_input}.\n\nMarca: {registro_encontrado.get('MARCA')}\nModelo: {registro_encontrado.get('MODELO')}\nChasis: {registro_encontrado.get('NRO_CHASIS')}\n\n📄 Ver documento (Google Drive): {url_drive}")
                        gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&su={asunto}&body={cuerpo}"
                        
                        st.markdown(
                            f"""
                            <a href="{gmail_link}" target="_blank" style="display: block; text-align: center; text-decoration: none; color: white; background-color: #EA4335; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 10px;">
                                ✉️ Redactar en Gmail
                            </a>
                            """, 
                            unsafe_allow_html=True
                        )
        else:
            st.warning(f"Ocurrió un error al cargar los datos de: **{patente_input}**")
