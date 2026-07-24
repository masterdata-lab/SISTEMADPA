import streamlit as st
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import gspread

@st.cache_resource
def conectar_google():
    try:
        # Cargar el nuevo token de usuario desde los secretos de Streamlit
        token_json = json.loads(st.secrets["google_token_json"])
        
        # Crear credenciales usando el Refresh Token (para que no caduque)
        creds = Credentials.from_authorized_user_info(token_json)
        
        # Conectar a Drive y a Sheets en tu nombre
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_client = gspread.authorize(creds)
        
        return drive_service, sheets_client
    except Exception as e:
        st.error(f"Error conectando a Google: {e}")
        return None, None
        
def obtener_o_crear_carpeta(drive_service, nombre_carpeta, parent_id):
    """
    Busca una carpeta por nombre dentro de un parent_id. 
    Si no existe, la crea y devuelve el nuevo ID.
    """
    # 1. Buscar si la carpeta ya existe
    query = f"mimeType='application/vnd.google-apps.folder' and name='{nombre_carpeta}' and '{parent_id}' in parents and trashed=false"
    resultados = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    carpetas = resultados.get('files', [])

    if carpetas:
        # Si existe, devolvemos el ID de la primera que encuentre
        return carpetas[0].get('id')
    else:
        # 2. Si no existe, la creamos
        metadata = {
            'name': nombre_carpeta,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        carpeta_creada = drive_service.files().create(body=metadata, fields='id').execute()
        return carpeta_creada.get('id')
