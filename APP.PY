import streamlit as st
import base64

# Configuración básica de la página
st.set_page_config(page_title="Gestión de Flota Vehicular", page_icon="🚚", layout="wide")

# --- BARRA LATERAL (MENÚ) ---
st.sidebar.title("Menú Principal")
menu = st.sidebar.radio("Selecciona un módulo:", ["Dashboard", "Títulos de Propiedad"])

# --- MÓDULO 1: DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Dashboard Principal")
    st.write("Bienvenido al sistema de gestión de flota de la empresa.")
    
    # Aquí en el futuro pondremos gráficos conectados a Google Sheets
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Total Vehículos", value="0")
    col2.metric(label="Títulos Procesados", value="0")
    col3.metric(label="Pendientes de Auditoría", value="0")

# --- MÓDULO 2: TÍTULOS DE PROPIEDAD ---
elif menu == "Títulos de Propiedad":
    st.title("📄 Gestión de Títulos de Propiedad")
    
    # Submódulos usando pestañas (Tabs)
    tab_carga, tab_procesar, tab_auditar = st.tabs(["1️⃣ Carga", "2️⃣ Procesar (IA)", "3️⃣ Auditar"])
    
    # 1. CARGA
    with tab_carga:
        st.header("Carga de Documento")
        st.write("Sube el PDF del Título de Propiedad. El sistema lo guardará en Google Drive.")
        
        uploaded_file = st.file_uploader("Selecciona el archivo PDF", type=["pdf"])
        
        if uploaded_file is not None:
            st.success(f"Archivo '{uploaded_file.name}' cargado en memoria.")
            if st.button("Guardar en Google Drive"):
                # Aquí irá el código de Google Drive API
                st.info("Simulando guardado... (El código de GDrive se conectará aquí en la próxima fase).")
    
    # 2. PROCESAR (IA)
    with tab_procesar:
        st.header("Procesamiento Inteligente")
        st.write("La Inteligencia Artificial leerá el documento en Drive y extraerá los datos clave (Patente, Motor, Chasis).")
        
        if st.button("Extraer datos con IA"):
            # Aquí irá la conexión con la API de OpenAI o Gemini
            st.info("Ejecutando IA... simulando extracción.")
            st.success("¡Datos extraídos con éxito! Ve a la pestaña 'Auditar' para revisarlos.")
            
    # 3. AUDITAR
    with tab_auditar:
        st.header("Auditoría Humana")
        st.write("Revisa que los datos extraídos por la IA coincidan con el documento original.")
        
        # Dividimos la pantalla en 2 columnas: Izquierda (PDF) y Derecha (Formulario)
        col_pdf, col_datos = st.columns([1, 1])
        
        with col_pdf:
            st.subheader("Vista Previa del Documento")
            # Esto es un visualizador de PDF (por ahora es un placeholder)
            st.caption("Aquí se mostrará el PDF cargado para que el auditor pueda leerlo.")
            st.container(height=400, border=True) # Simulamos el espacio del PDF
            
        with col_datos:
            st.subheader("Datos Extraídos (Confirmación)")
            # Formulario para que el humano corrija si la IA se equivocó
            with st.form("formulario_auditoria"):
                patente = st.text_input("Dominio (Patente)", value="AB123CD") # Valores simulados que traería la IA
                marca = st.text_input("Marca / Modelo", value="Ford Ranger")
                chasis = st.text_input("Nro. de Chasis", value="8AW339...")
                motor = st.text_input("Nro. de Motor", value="MTR991...")
                
                guardar = st.form_submit_button("✅ Aprobar y Guardar en Google Sheets")
                
                if guardar:
                    # Aquí irá la conexión con Google Sheets API (gspread)
                    st.success(f"El vehículo patente {patente} fue registrado en la base de datos.")
