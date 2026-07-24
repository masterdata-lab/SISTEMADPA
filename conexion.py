import streamlit as st
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread

@st.cache_resource
def conectar_google():
    try:
        # Cargar las credenciales desde los secretos de Streamlit
        creds_json = json.loads(st.secrets["google_credentials_json"])
        scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ]
        creds = service_account.Credentials.from_service_account_info(creds_json, scopes=scopes)
        
        # Conectar a Drive y a Sheets
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_client = gspread.authorize(creds)
        
        return drive_service, sheets_client
    except Exception as e:
        st.error(f"Error conectando a Google: {e}")
        return None, None
