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

def mostrar_visor_pdf(file_id, height=700):
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

    # Barra de búsqueda
    col_busqueda, col_vacia = st.columns([1, 2])
    with col_busqueda:
        patente_input = st.text_input("Ingrese la Patente a buscar:", placeholder="Ej. AG871VL").strip().upper()

    if patente_input:
        with st.spinner("Buscando en la base de datos..."):
            registros_bd = obtener_datos_sheets(sheets_client, SHEET_ID)
            
            # Buscar coincidencia exacta
            registro_encontrado = None
            for reg in registros_bd:
                if str(reg.get('PATENTE', '')).strip().upper() == patente_input:
                    registro_encontrado = reg
                    break

        if registro_encontrado:
            st.success(f"✅ Título encontrado para la patente: **{patente_input}**")
            
            id_drive = registro_encontrado.get('ID_DRIVE')
            
            # Layout de resultados
            col_info, col_visor = st.columns([1, 2])
            
            with col_info:
                st.subheader("Datos del Vehículo")
                st.info(f"""
                **Titular:** {registro_encontrado.get('TITULAR', 'N/A')}
                **Marca:** {registro_encontrado.get('MARCA', 'N/A')}
                **Modelo:** {registro_encontrado.get('MODELO', 'N/A')}
                **Chasis:** {registro_encontrado.get('NRO_CHASIS', 'N/A')}
                **Motor:** {registro_encontrado.get('NRO_MOTOR', 'N/A')}
                **Radicación:** {registro_encontrado.get('LUGAR_RADICACION', 'N/A')}
                """)
                
                st.divider()
                st.subheader("Acciones Rápidas")
                
                if id_drive:
                    # 1. Botón de Descarga
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
                    
                    # 2. Enviar por Email (mailto link)
                    asunto = urllib.parse.quote(f"Título del Vehículo - Patente {patente_input}")
                    cuerpo = urllib.parse.quote(f"Adjunto información del vehículo patente {patente_input}.\n\nMarca: {registro_encontrado.get('MARCA')}\nModelo: {registro_encontrado.get('MODELO')}")
                    mailto_link = f"mailto:?subject={asunto}&body={cuerpo}"
                    
                    st.markdown(
                        f"""
                        <a href="{mailto_link}" style="display: block; text-align: center; text-decoration: none; color: white; background-color: #4CAF50; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 10px;">
                            ✉️ Enviar por Correo Electrónico
                        </a>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    # 3. Imprimir
                    st.caption("🖨️ *Para imprimir, utiliza el ícono de la impresora en la esquina superior derecha del visor del PDF.*")
                else:
                    st.error("El registro no tiene un ID de archivo asociado válido.")

            with col_visor:
                st.subheader("Vista Previa")
                if id_drive:
                    mostrar_visor_pdf(id_drive)
                
        else:
            st.warning(f"No se encontraron registros para la patente: **{patente_input}**")
