import streamlit as st
import io
import urllib.parse
from googleapiclient.http import MediaIoBaseDownload

# --- FUNCIONES AUXILIARES ---

def obtener_datos_sheets(sheets_client, SHEET_ID):
    try:
        hoja = sheets_client.open_by_key(SHEET_ID).sheet1
        return hoja.get_all_records()
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return []

def mostrar_visor_pdf(file_id, height=600):
    url_preview = f"https://drive.google.com/file/d/{file_id}/preview"
    st.markdown(
        f'<iframe src="{url_preview}" width="100%" height="{height}px" style="border: none; border-radius: 8px;"></iframe>', 
        unsafe_allow_html=True
    )

def descargar_pdf_bytes(drive_service, file_id):
    """Descarga los bytes del PDF directamente de Drive para el botón de descarga."""
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
    st.header("🔍 Buscar Documento")
    st.divider()

    # 1. Cargamos la base de datos PRIMERO para poder llenar el desplegable
    with st.spinner("Cargando patentes disponibles..."):
        registros_bd = obtener_datos_sheets(sheets_client, SHEET_ID)
        
    # Extraemos solo las patentes, eliminamos vacíos, y las ordenamos alfabéticamente
    lista_patentes = sorted(list(set([str(reg.get('PATENTE', '')).strip().upper() for reg in registros_bd if reg.get('PATENTE')])))

    # 2. Barra de búsqueda con autocompletado
    col_busqueda, col_vacia = st.columns([1, 2])
    with col_busqueda:
        patente_input = st.selectbox(
            "Seleccione o escriba la Patente a buscar:", 
            options=lista_patentes,
            index=None,
            placeholder="Ej. AG871VL"
        )

    # 3. Si el usuario seleccionó/escribió algo, mostramos los datos
    if patente_input:
        # Buscamos el registro exacto en la base
        registro_encontrado = next((reg for reg in registros_bd if str(reg.get('PATENTE', '')).strip().upper() == patente_input), None)

        if registro_encontrado:
            st.success(f"✅ Título encontrado para la patente: **{patente_input}**")
            
            id_drive = registro_encontrado.get('ID_DRIVE')
            
            # Replicamos el layout de auditoría: Visor [4] a la izquierda, Datos [3] a la derecha
            col_visor, col_datos = st.columns([4, 3])
            
            with col_visor:
                st.subheader("Vista Previa")
                if id_drive:
                    mostrar_visor_pdf(id_drive)
                else:
                    st.error("El registro no tiene un documento asociado para visualizar.")

            with col_datos:
                st.subheader("Datos del Vehículo")
                
                # Usamos un contenedor con borde para simular el aspecto de un "form", 
                # pero con st.text_input deshabilitados para evitar edición.
                with st.container(border=True):
                    st.text_input("Patente", value=patente_input, disabled=True)
                    st.text_input("Marca", value=registro_encontrado.get('MARCA', ''), disabled=True)
                    st.text_input("Modelo", value=registro_encontrado.get('MODELO', ''), disabled=True)
                    st.text_input("Chasis", value=registro_encontrado.get('NRO_CHASIS', ''), disabled=True)
                    st.text_input("Motor", value=registro_encontrado.get('NRO_MOTOR', ''), disabled=True)
                    st.text_input("Titular", value=registro_encontrado.get('TITULAR', ''), disabled=True)
                    st.text_input("Radicación", value=registro_encontrado.get('LUGAR_RADICACION', ''), disabled=True)
                
                st.divider()
                st.subheader("Acciones Rápidas")
                
                if id_drive:
                    # Acción 1: Botón de Descarga
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
                    
                    # Acción 2: Enviar por Gmail (Enlace a Drive)
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
