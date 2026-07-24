import streamlit as st
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread

# Configuración básica de la página
st.set_page_config(page_title="Gestión de Flota Vehicular", page_icon="🚚", layout="wide")

### --- NUEVO: FUNCIÓN PARA CONECTAR A GOOGLE --- ###
@st.cache_resource
def conectar_google():
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

# Inicializar conexión (esto falla si los secretos no están bien configurados)
try:
    drive_service, sheets_client = conectar_google()
    conexion_exitosa = True
except Exception as e:
    st.error(f"Error conectando a Google: {e}")
    conexion_exitosa = False

# --- CONSTANTES ---
# ID de tu carpeta de Drive (SISTEMA DPA) extraído de tu link
CARPETA_DRIVE_ID = "1ps5FF0fkJ7utOpvbqPWfAs9IAOH6aoNU" 
# ID de tu Google Sheet extraído de tu link
SHEET_ID = "1_ncJgZrP5Jvks3nE-tBVrMmuSA7pbZiEmH9ExvHD_Uk"

# --- BARRA LATERAL (MENÚ) ---
st.sidebar.title("Menú Principal")
menu = st.sidebar.radio("Selecciona un módulo:", ["Dashboard", "Títulos de Propiedad"])

if menu == "Dashboard":
    st.title("📊 Dashboard Principal")
    st.write("Bienvenido al sistema de gestión de flota.")
    
elif menu == "Títulos de Propiedad" and conexion_exitosa:
    st.title("📄 Gestión de Títulos de Propiedad")
    
    tab_carga, tab_procesar, tab_auditar = st.tabs(["1️⃣ Carga", "2️⃣ Procesar (IA)", "3️⃣ Auditar"])
    
    with tab_carga:
        st.header("Carga de Documento")
        uploaded_file = st.file_uploader("Selecciona el archivo PDF", type=["pdf"])
        patente_temp = st.text_input("Ingresa la patente para renombrar el archivo (ej. AB123CD)")
        
        if uploaded_file and patente_temp:
            if st.button("Guardar en Google Drive"):
                with st.spinner("Subiendo a Drive..."):
                    nuevo_nombre = f"TITULO_{patente_temp.upper()}.pdf"
                    file_metadata = {
                        'name': nuevo_nombre,
                        'parents': [CARPETA_DRIVE_ID]
                    }
                    media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), mimetype='application/pdf')
                    archivo_guardado = drive_service.files().create(
                        body=file_metadata, 
                        media_body=media, 
                        fields='id'
                    ).execute()
                    
                    st.success(f"✅ Archivo guardado correctamente en Drive como: {nuevo_nombre}")
    
    with tab_procesar:
        st.header("Procesamiento Inteligente")
        st.write("En la próxima fase conectaremos Gemini / OpenAI aquí.")
            
    with tab_auditar:
        st.header("Auditoría Humana")
        st.write("Revisa los datos y guárdalos en Google Sheets.")
        
        with st.form("formulario_auditoria"):
            patente = st.text_input("Dominio (Patente)", value="AB123CD")
            marca = st.text_input("Marca / Modelo", value="Ford Ranger")
            chasis = st.text_input("Nro. de Chasis", value="8AW339...")
            motor = st.text_input("Nro. de Motor", value="MTR991...")
            
            guardar = st.form_submit_button("✅ Aprobar y Guardar en Google Sheets")
            
            if guardar:
                with st.spinner("Guardando en la base de datos..."):
                    try:
                        # Conecta directamente usando el ID de tu URL
                        hoja = sheets_client.open_by_key(SHEET_ID).sheet1
                        # Inserta una nueva fila al final del Excel
                        hoja.append_row([patente, marca, chasis, motor])
                        st.success(f"✅ El vehículo {patente} fue registrado en Google Sheets.")
                    except Exception as e:
                        st.error(f"Error al guardar en Sheets: Asegúrate de haberle dado acceso de 'Editor' al email del robot. Error: {e}")
