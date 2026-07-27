import streamlit as st
import io
import json
from googleapiclient.http import MediaIoBaseDownload
from google import genai
from google.genai import types

def procesar_con_ia(pdf_bytes):
    """
    Se conecta a la API de Gemini usando los modelos configurados en secrets
    y extrae los datos estructurados usando el esquema JSON requerido.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)
        
        # Obtenemos los modelos desde los secretos (con valores de respaldo)
        modelo_principal = st.secrets.get("MODELO_IA_PRINCIPAL", "3.1-Flash-Lite")
        modelo_secundario = st.secrets.get("MODELO_IA_SECUNDARIO", "3.5-Flash")
        
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
        # INTENTO 1: Modelo Principal (Desde Secrets)
        respuesta = client.models.generate_content(
            model=modelo_principal,
            contents=[prompt, documento_pdf],
            config=configuracion_ia
        )
        return json.loads(respuesta.text)
    
    except Exception as error_principal:
        st.warning(f"⚠️ Falló {modelo_principal}, intentando failover a {modelo_secundario}... (Error: {error_principal})")
        try:
            # INTENTO 2: Failover (Desde Secrets)
            respuesta_failover = client.models.generate_content(
                model=modelo_secundario,
                contents=[prompt, documento_pdf],
                config=configuracion_ia
            )
            return json.loads(respuesta_failover.text)
        except Exception as error_failover:
            raise Exception(f"Ambos modelos ({modelo_principal} y {modelo_secundario}) fallaron. Detalles: {error_failover}")

def mover_archivo_drive(drive_service, file_id, id_origen, id_destino, datos_extraidos):
    """
    Mueve el archivo entre carpetas y guarda los datos de la IA
    como propiedades individuales para respetar los límites de la API de Drive.
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
    ).execute()

def modulo_procesar(drive_service, TIPO_DOC):
    st.header(f"Procesamiento Inteligente de {TIPO_DOC}")
    
    id_origen = st.session_state.get(f"id_pendientes_{TIPO_DOC}")
    id_destino = st.session_state.get(f"id_auditar_{TIPO_DOC}")
    
    if not id_origen or not id_destino:
        st.error("Error: No se encontraron los IDs de las carpetas. Ve a la pestaña 'Carga' primero.")
        return

    st.info(f"Buscando archivos en la bandeja '1_Pendientes'...")
    
    query = f"'{id_origen}' in parents and trashed=false"
    resultados = drive_service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultados.get('files', [])
    
    if not archivos:
        st.success("🎉 ¡Bandeja limpia! No hay documentos pendientes de procesar.")
        return
        
    st.write(f"Se encontraron **{len(archivos)}** documento(s) pendientes.")
    
    if st.button("🚀 Iniciar Procesamiento con IA"):
        barra_progreso = st.progress(0)
        estado_texto = st.empty()
        
        for i, archivo in enumerate(archivos):
            estado_texto.write(f"Procesando con IA: `{archivo['name']}`...")
            
            try:
                request = drive_service.files().get_media(fileId=archivo['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                pdf_bytes = fh.getvalue()
                datos_json = procesar_con_ia(pdf_bytes)
                mover_archivo_drive(drive_service, archivo['id'], id_origen, id_destino, datos_json)
                
            except Exception as e:
                st.error(f"❌ Error al procesar '{archivo['name']}': {e}")
                
            barra_progreso.progress((i + 1) / len(archivos))
            
        estado_texto.success("✅ Procesamiento completado. Los archivos ya están en la bandeja de Auditoría listos para revisión humana.")
        st.rerun()
