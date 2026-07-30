import streamlit as st
import io
import json
from googleapiclient.http import MediaIoBaseDownload
from google import genai
from google.genai import types

def procesar_cedula_con_ia(pdf_bytes, status_text_ui, nombre_archivo):
    """
    Analiza un PDF de Cédulas Verdes usando la IA.
    Devuelve un JSON estructurado con la lista de patentes halladas y el tipo de cara.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)
        modelo_principal = st.secrets.get("MODELO_IA_PRINCIPAL", "gemini-2.5-pro") # Usando la versión más capaz
        modelo_secundario = st.secrets.get("MODELO_IA_SECUNDARIO", "gemini-2.5-flash")
    except KeyError:
        raise Exception("Falta la variable GEMINI_API_KEY en los secretos de Streamlit.")

    prompt = """Eres un experto en auditoría de Cédulas de Identificación de Vehículos (Cédula Verde) en Argentina.
    Analiza el documento PDF adjunto (que puede contener una o varias cédulas en la misma hoja) y extrae la información.

    REGLAS ESTRICTAS:
    1. 'es_cedula_valida': true si el documento corresponde a una o más Cédulas Verdes.
    2. 'tipo_cara': Indica si la imagen representa 'FRENTE', 'DORSO' o 'FRENTE_Y_DORSO' (si tiene 2 páginas).
    3. 'patentes': Lista (ARRAY) de todas las patentes/dominios encontrados.
       - Si es un FRENTE con 3 cédulas, extrae las 3 patentes en el array (ej. ["A192BBQ", "A192BBS", "A192BBO"]).
       - Si es EXCLUSIVAMENTE un DORSO y no figura ninguna patente, el array debe quedar vacío [].
    4. Devuelve todas las patentes en MAYÚSCULAS y sin guiones ni espacios."""

    documento_pdf = types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')

    esquema_json = {
        "type": "OBJECT",
        "properties": {
            "es_cedula_valida": {"type": "BOOLEAN"},
            "tipo_cara": {
                "type": "STRING", 
                "enum": ["FRENTE", "DORSO", "FRENTE_Y_DORSO", "DESCONOCIDO"]
            },
            "patentes": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Lista de dominios/patentes extraídas del documento"
            }
        },
        "required": ["es_cedula_valida", "tipo_cara", "patentes"]
    }

    configuracion_ia = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=esquema_json,
        temperature=0.0
    )

    try:
        status_text_ui.info(f"🔄 `{nombre_archivo}`: Analizando Cédula(s) con IA...")
        respuesta = client.models.generate_content(
            model=modelo_principal,
            contents=[prompt, documento_pdf],
            config=configuracion_ia
        )
        return json.loads(respuesta.text)
    
    except Exception as error_principal:
        status_text_ui.warning(f"⚠️ `{nombre_archivo}`: Failover al modelo secundario...")
        try:
            respuesta_failover = client.models.generate_content(
                model=modelo_secundario,
                contents=[prompt, documento_pdf],
                config=configuracion_ia
            )
            return json.loads(respuesta_failover.text)
        except Exception as error_failover:
            raise Exception(f"Error procesando Cédula: {error_failover}")

def mover_archivo_drive(drive_service, file_id, id_origen, id_destino, datos_extraidos):
    """Mueve el archivo a la carpeta de auditoría y guarda las patentes como metadata."""
    patentes_list = datos_extraidos.get('patentes', [])
    # Convertimos la lista de patentes en un string separado por comas para guardarlo en Drive
    patentes_str = ",".join(patentes_list) if isinstance(patentes_list, list) else str(patentes_list)
    
    propiedades_app = {
        "es_cedula_valida": str(datos_extraidos.get("es_cedula_valida", True)),
        "tipo_cara": str(datos_extraidos.get("tipo_cara", "FRENTE")),
        "patentes": patentes_str
    }

    drive_service.files().update(
        fileId=file_id,
        addParents=id_destino,
        removeParents=id_origen,
        body={"appProperties": propiedades_app},
        fields='id, parents'
    ).execute(num_retries=3)

def revertir_archivo_drive(drive_service, file_id, id_actual, id_original):
    drive_service.files().update(
        fileId=file_id,
        addParents=id_original,
        removeParents=id_actual,
        fields='id, parents'
    ).execute(num_retries=3)

# --- CALLBACKS PARA MANEJO SEGURO DE ESTADO ---
def iniciar_proceso():
    st.session_state.procesando_ia_cedulas = True
    st.session_state.detener_proceso_cedulas = False
    st.session_state.acciones_rollback_cedulas = []

def cancelar_proceso():
    st.session_state.detener_proceso_cedulas = True
    st.session_state.procesando_ia_cedulas = False

# --- MÓDULO PRINCIPAL ---
def modulo_procesar(drive_service, TIPO_DOC):
    st.markdown(f"## ⚙️ Motor de Procesamiento (IA) - {TIPO_DOC}")
    st.divider()
    
    id_origen = st.session_state.get(f"id_pendientes_{TIPO_DOC}")
    id_destino = st.session_state.get(f"id_auditar_{TIPO_DOC}")
    
    if not id_origen or not id_destino:
        st.error("Error: No se encontraron los IDs de las carpetas. Ve a la pestaña 'Carga' primero.")
        return

    if "procesando_ia_cedulas" not in st.session_state:
        st.session_state.procesando_ia_cedulas = False
    if "detener_proceso_cedulas" not in st.session_state:
        st.session_state.detener_proceso_cedulas = False
    if "acciones_rollback_cedulas" not in st.session_state:
        st.session_state.acciones_rollback_cedulas = []

    # --- BLOQUE DE INTERCEPCIÓN Y ROLLBACK ---
    if st.session_state.detener_proceso_cedulas:
        st.warning("⚠️ Procesamiento cancelado por el usuario. Ejecutando protocolo de seguridad (Rollback)...")
        acciones = st.session_state.acciones_rollback_cedulas
        
        if acciones:
            barra_rollback = st.progress(0)
            for i, accion in enumerate(reversed(acciones)):
                try:
                    if accion["tipo"] == "move":
                        revertir_archivo_drive(drive_service, accion["file_id"], accion["destino"], accion["origen"])
                except Exception:
                    pass
                barra_rollback.progress((i + 1) / len(acciones))
            st.success("✅ Rollback completado: El sistema volvió a su estado original.")
        else:
            st.info("No se había movido ningún documento. Nada que revertir.")
            
        st.session_state.detener_proceso_cedulas = False
        st.session_state.acciones_rollback_cedulas = []
        
        if st.button("Aceptar y Volver", type="primary"):
            st.rerun()
        return

    # --- FLUJO NORMAL DE LA INTERFAZ ---
    st.info("Buscando archivos en la bandeja '1_Pendientes'...")
    resultados = drive_service.files().list(q=f"'{id_origen}' in parents and trashed=false", fields="files(id, name)").execute(num_retries=3)
    archivos = resultados.get('files', [])
    
    if not archivos:
        st.success("🎉 ¡Bandeja limpia! No hay cédulas pendientes de procesar.")
        return
        
    st.write(f"Se encontraron **{len(archivos)}** documento(s) pendientes.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("🚀 Iniciar Procesamiento", use_container_width=True, disabled=st.session_state.procesando_ia_cedulas, on_click=iniciar_proceso)
    with col2:
        if st.session_state.procesando_ia_cedulas:
            st.button("🛑 Detener Procesamiento", type="primary", use_container_width=True, on_click=cancelar_proceso)

    # --- LÓGICA DE PROCESAMIENTO ---
    if st.session_state.procesando_ia_cedulas:
        barra_progreso = st.progress(0)
        status_text_ui = st.empty()
        
        archivos_exitosos = 0
        archivos_fallidos = 0
        lista_errores = []

        for i, archivo in enumerate(archivos):
            try:
                # 1. Descargar documento
                request = drive_service.files().get_media(fileId=archivo['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    _, done = downloader.next_chunk()
                
                pdf_bytes = fh.getvalue()

                # 2. Procesar el documento completo (sin recortar)
                datos_json = procesar_cedula_con_ia(pdf_bytes, status_text_ui, archivo['name'])
                
                # 3. Mover a la carpeta de auditoría
                st.session_state.acciones_rollback_cedulas.append({"tipo": "move", "file_id": archivo['id'], "origen": id_origen, "destino": id_destino})
                mover_archivo_drive(drive_service, archivo['id'], id_origen, id_destino, datos_json)
                archivos_exitosos += 1

            except Exception as e:
                archivos_fallidos += 1
                lista_errores.append(f"**{archivo['name']}**: {e}")
                
            barra_progreso.progress((i + 1) / len(archivos))
            
            if st.session_state.detener_proceso_cedulas:
                break
            
        # --- RESUMEN FINAL ---
        st.session_state.procesando_ia_cedulas = False
        st.session_state.acciones_rollback_cedulas = []
        status_text_ui.empty() 
        
        st.markdown("---")
        st.subheader("📊 Resumen del Procesamiento")
        st.success(f"✅ Archivos procesados exitosamente: **{archivos_exitosos}**")
        
        if archivos_fallidos > 0:
            st.error(f"❌ Fallidos (Siguen en pendientes): **{archivos_fallidos}**")
            with st.expander("Ver detalle de los errores"):
                for err in lista_errores:
                    st.write(err)
        
        if st.button("Actualizar Bandeja"):
            st.rerun()
