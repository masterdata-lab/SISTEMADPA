import streamlit as st
import io
import urllib.parse
from googleapiclient.http import MediaIoBaseDownload

# --- FUNCIONES AUXILIARES ---

def obtener_hoja_y_datos_cedulas(sheets_client, SHEET_ID):
    """Devuelve el objeto de la hoja 'Cedulas' y los registros."""
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

# --- MÓDULO PRINCIPAL ---

def modulo_buscar(drive_service, sheets_client, SHEET_ID):
    st.header("🔍 Buscar y Visualizar Cédulas")
    st.divider()

    # 1. Cargamos la base de datos de Cédulas
    with st.spinner("Cargando base de datos..."):
        hoja, registros_bd = obtener_hoja_y_datos_cedulas(sheets_client, SHEET_ID)
        
    if hoja is None:
        return

    # Extraemos solo las patentes válidas para el buscador (ignorando "SIN PATENTE" o vacíos)
    lista_patentes = sorted(list(set([
        str(reg.get('PATENTE', '')).strip().upper() 
        for reg in registros_bd 
        if reg.get('PATENTE') and str(reg.get('PATENTE')).strip().upper() != "SIN PATENTE"
    ])))

    # 2. Barra de búsqueda
    col_busqueda, col_vacia = st.columns([1, 2])
    with col_busqueda:
        patente_input = st.selectbox(
            "Seleccione o escriba la Patente a buscar:", 
            options=lista_patentes,
            index=None,
            placeholder="Ej. AG871VL"
        )

    # 3. Mostrar resultados
    if patente_input:
        # A diferencia de Títulos, aquí buscamos TODOS los registros que coincidan con la patente
        # (ya que podría haber un archivo para el Frente y otro para el Dorso)
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
                                file_name=f"Cedula_{patente_input}_{tipo_cara}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                type="primary",
                                key=f"btn_dl_{idx}"
                            )
