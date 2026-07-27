import streamlit as st
import io
import json
from googleapiclient.http import MediaIoBaseDownload
from google import genai
from google.genai import types

def procesar_con_ia_y_reintentos(pdf_bytes, status_text_ui, nombre_archivo):
    """
    Se conecta a la API de Gemini con reintentos y actualiza la UI en vivo.
    Utiliza los nombres exactos de los modelos configurados en los secretos.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)
        
        # Leemos los IDs exactos de los modelos desde los secretos
        modelo_principal = st.secrets.get("MODELO_IA_PRINCIPAL", "gemini-3.1-flash-lite")
        modelo_secundario = st.secrets.get("MODELO_IA_SECUNDARIO", "gemini-3.5-flash")
        
    except KeyError:
        raise Exception("Falta la variable GEMINI_API_KEY en los secretos de Streamlit.")

    prompt = """Eres un asistente experto en auditoría documental automotor en Argentina. 
    Analiza el documento PDF adjunto y extrae la información requerida.
    
    REGLAS ESTRICTAS:
    1. Determina si el documento es un 'TÍTULO DEL AUTOMOTOR'. Si no lo es, 'es_titulo_valido' debe ser false y el resto null.
    2. Si solo se indica el 'Lugar de Radicación', deduce la 'Provincia de Radicación' correspondiente.
    3. Extrae la 'Marca' exacta indicada (no Mca. Motor o Mca. Chasis).
    4. El 'Titular' suele encontrarse bajo 'Razón Social' o 'Titular'.
    5. Fechas en formato DD/MM/YYYY. Textos en MAYÚSCULAS."""

    documento_pdf = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    esquema_json = {
        "type": "OBJECT",
        "properties": {
            "es_titulo_valido": {"type": "BOOLEAN"},
            "patente": {"type": "STRING"},
            "lugar_radicacion": {"type": "STRING"},
            "provincia_radicacion": {"type": "STRING"},
            "fecha_inscripcion_inicial": {"type": "STRING", "description": "Formato DD/MM/YYYY"},
            "marca": {"type": "STRING"},
            "modelo": {"type": "STRING"},
            "tipo": {"type": "STRING"},
            "nro_motor": {"type": "STRING"},
            "nro_chasis": {"type": "STRING"},
            "titular": {"type": "STRING"},
            "cuit": {"type": "STRING"}
        }
    }

    configuracion_ia = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=esquema_json,
        temperature=0.0 
    )

    try:
        # INTENTO 1
        status_text_ui.info(f"🔄 `{nombre_archivo}`: Consultando modelo principal ({modelo_principal})...")
        respuesta = client.models.generate_content(
            model=modelo_principal,
            contents=[prompt, documento_pdf],
            config=configuracion_ia
        )
        return json.loads(respuesta.text)
    
    except Exception as error_principal:
        status_text_ui.warning(f"⚠️ `{nombre_archivo}`: Falló modelo principal. Ejecutando failover a {modelo_secundario}...")
        try:
            # INTENTO 2
            respuesta_failover = client.models.generate_content(
                model=modelo_secundario,
                contents=[prompt, documento_pdf],
                config=configuracion_ia
            )
            return json.loads(respuesta_failover.text)
        except Exception as error_failover:
            raise Exception(f"TIMEOUT_GLOBAL: Ambos modelos se encuentran saturados o devolvieron error. Intente más tarde. Detalles: {error_failover}")


def mover_archivo_drive(drive_service, file_id, id_origen, id_destino, datos_extraidos):
    """
    Mueve el archivo entre carpetas y guarda los datos de la IA como propiedades individuales.
    Se agrega num_retries=3 para evitar cortes de conexión SSL.
    """
    propiedades_app = {}
    for clave, valor in datos_extraidos.items():
        if valor is not None:
            valor_str = str(valor)
            if len(valor_str) > 100:
                valor_str = valor_str[:100]
            propiedades_app[clave] = valor_str

    drive_service.files().update(
        fileId=file_id,
        addParents=id_destino,
        removeParents=id_origen,
        body={"appProperties": propiedades_app},
        fields='id, parents'
    ).execute(num_retries=3)


def modulo_procesar(drive_service, TIPO_DOC):
    st.markdown(f"## ⚙️ Motor de Procesamiento (IA) - {TIPO_DOC}")
    st.divider()
    
    id_origen = st.session_state.get(f"id_pendientes_{TIPO_DOC}")
    id_destino = st.session_state.get(f"id_auditar_{TIPO_DOC}")
    
    if not id_origen or not id_destino:
        st.error("Error: No se encontraron los IDs de las carpetas. Ve a la pestaña 'Carga' primero.")
        return

    st.info("Buscando archivos en la bandeja '1_Pendientes'...")
    
    query = f"'{id_origen}' in parents and trashed=false"
    
    # Tolerancia a fallos de red al listar archivos
    resultados = drive_service.files().list(q=query, fields="files(id, name)").execute(num_retries=3)
    archivos = resultados.get('files', [])
    
    if not archivos:
        st.success("🎉 ¡Bandeja limpia! No hay documentos pendientes de procesar.")
        return
        
    st.write(f"Se encontraron **{len(archivos)}** documento(s) pendientes.")
    
    # --- CONTROL DE ESTADO PARA EL BUCLE ---
    if "procesando_ia" not in st.session_state:
        st.session_state.procesando_ia = False
    if "detener_proceso" not in st.session_state:
        st.session_state.detener_proceso = False

    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🚀 Iniciar Procesamiento", use_container_width=True, disabled=st.session_state.procesando_ia):
            st.session_state.procesando_ia = True
            st.session_state.detener_proceso = False
            st.rerun()
            
    with col2:
        if st.session_state.procesando_ia:
            if st.button("🛑 Detener Procesamiento", type="primary", use_container_width=True):
                st.session_state.detener_proceso = True
                st.rerun()

    # --- LÓGICA DE PROCESAMIENTO ---
    if st.session_state.procesando_ia:
        barra_progreso = st.progress(0)
        status_text_ui = st.empty()
        
        archivos_exitosos = 0
        archivos_fallidos = 0
        lista_errores = []

        for i, archivo in enumerate(archivos):
            if st.session_state.detener_proceso:
                status_text_ui.warning("⚠️ Procesamiento detenido por el usuario.")
                break
            
            try:
                request = drive_service.files().get_media(fileId=archivo['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                pdf_bytes = fh.getvalue()
                
                # Procesamiento con IA
                datos_json = procesar_con_ia_y_reintentos(pdf_bytes, status_text_ui, archivo['name'])
                
                # Mover en Drive
                mover_archivo_drive(drive_service, archivo['id'], id_origen, id_destino, datos_json)
                
                archivos_exitosos += 1
                
            except Exception as e:
                archivos_fallidos += 1
                lista_errores.append(f"**{archivo['name']}**: {e}")
                
            barra_progreso.progress((i + 1) / len(archivos))
            
        # --- RESUMEN FINAL ---
        st.session_state.procesando_ia = False
        st.session_state.detener_proceso = False
        
        status_text_ui.empty() 
        
        st.markdown("---")
        st.subheader("📊 Resumen del Procesamiento")
        st.success(f"✅ Procesados y movidos: **{archivos_exitosos}**")
        
        if archivos_fallidos > 0:
            st.error(f"❌ Fallidos (Siguen en pendientes): **{archivos_fallidos}**")
            with st.expander("Ver detalle de los errores"):
                for err in lista_errores:
                    st.write(err)
        
        if st.button("Actualizar Bandeja"):
            st.rerun()
