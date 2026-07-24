import streamlit as st

# Configuración básica de la página principal
st.set_page_config(page_title="Gestión de Flota", page_icon="🚚", layout="wide")

st.title("📊 Dashboard Principal")
st.write("Bienvenido al sistema central de gestión de flota de la empresa.")

# Indicación visual para el usuario
st.info("👈 Usa el menú lateral para navegar por los diferentes módulos del sistema.")

# --- Aquí armaremos el Dashboard en el futuro ---
st.markdown("### Resumen Rápido")
col1, col2, col3 = st.columns(3)
col1.metric(label="Total Vehículos", value="0")
col2.metric(label="Títulos Procesados", value="0")
col3.metric(label="Pendientes de Auditoría", value="0")
