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
