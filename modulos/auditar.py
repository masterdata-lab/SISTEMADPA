import streamlit as st

def modulo_auditar(drive_service, sheets_client, TIPO_DOC, SHEET_ID):
    st.header(f"Auditoría Humana de {TIPO_DOC}")
    
    id_origen = st.session_state.get(f"id_auditar_{TIPO_DOC}", "No encontrado")
    id_destino = st.session_state.get(f"id_aprobados_{TIPO_DOC}", "No encontrado")
    
    st.write(f"Revisa los datos. Al aprobar, los archivos se moverán a '3_Aprobados' (ID: `{id_destino}`) y se guardarán en Sheets.")
    
    with st.form(f"formulario_auditoria_{TIPO_DOC}"):
        patente = st.text_input("Dominio (Patente)", value="AB123CD")
        marca = st.text_input("Marca / Modelo", value="Ford Ranger")
        chasis = st.text_input("Nro. de Chasis", value="8AW339...")
        motor = st.text_input("Nro. de Motor", value="MTR991...")
        
        guardar = st.form_submit_button("✅ Aprobar y Guardar en Google Sheets")
        
        if guardar:
            with st.spinner("Guardando en la base de datos..."):
                try:
                    hoja = sheets_client.open_by_key(SHEET_ID).sheet1
                    hoja.append_row([patente, marca, chasis, motor])
                    st.success(f"✅ El vehículo {patente} fue registrado en Google Sheets.")
                except Exception as e:
                    st.error(f"Error al guardar en Sheets: {e}")
